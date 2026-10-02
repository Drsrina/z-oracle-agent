#!/usr/bin/env python3
"""
pipeline_vetorizacao.py — AEGIS-REBOT Knowledge Base Vectorizer
================================================================
Pipeline completo em uma única execução:
  1. Lê um CSV com artigos da base de conhecimento
  2. Limpa conteúdo JSONB aninhado extraindo texto puro
  3. Gera embeddings com SentenceTransformer (all-MiniLM-L6-v2, 384d)
  4. Salva CSV vetorizado + SQL de UPDATE para pgvector/Supabase

Modelo: all-MiniLM-L6-v2 — mesmo utilizado no router.py e agent.py,
garantindo que a busca semântica da KB e o roteador vivam no mesmo espaço vetorial.

USO:
    pip install -r requirements.txt
    python pipeline_vetorizacao.py --input minha_base.csv --output saida/

FORMATO DO CSV DE ENTRADA (colunas mínimas):
    articleId, title, category, content (JSONB string), phrasing, phrasing_1 ... phrasing_N
"""

import re
import json
import argparse
import os
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

# ── Configurações padrão ──────────────────────────────────────────────────────
MODEL_NAME  = "all-MiniLM-L6-v2"   # 384 dims — compatível com LlamaIndex HuggingFaceEmbedding
BATCH_SIZE  = 32
TABLE_NAME  = "base_conhecimento"   # Nome da tabela no PostgreSQL/Supabase
VEC_COLUMN  = "vecs1"              # Coluna do tipo vector(384) na tabela


# ── Funções utilitárias ───────────────────────────────────────────────────────

def extrair_texto_jsonb(content: str) -> str:
    """
    Extrai texto puro de blocos JSONB aninhados (formato rich-text/CMS).
    Percorre recursivamente o objeto procurando chaves "text" do tipo string.

    Args:
        content: String JSON representando o conteúdo rico do artigo.

    Returns:
        Texto concatenado, limpo de markdown básico e espaços extras.
    """
    partes = []

    def _extrair(obj):
        if isinstance(obj, dict):
            if "text" in obj and isinstance(obj["text"], str):
                partes.append(obj["text"])
            for val in obj.values():
                _extrair(val)
        elif isinstance(obj, list):
            for item in obj:
                _extrair(item)

    try:
        _extrair(json.loads(content))
    except (json.JSONDecodeError, TypeError):
        return ""

    texto = " ".join(partes)
    texto = re.sub(r"[*_#]+", "", texto)        # Remove markdown simples
    texto = re.sub(r"\s+", " ", texto).strip()  # Normaliza espaços
    return texto


def preparar_texto_embedding(row: pd.Series) -> str:
    """
    Combina título, categoria, conteúdo e phrasings em um único texto
    otimizado para geração de embedding.

    Estratégia: Título e categoria recebem mais peso posicional (ficam no início),
    pois o modelo transformer valoriza tokens iniciais.
    """
    phrasing_cols = [c for c in row.index if "phrasing" in c.lower()]
    phrasings = [
        str(row[c]) for c in phrasing_cols
        if pd.notna(row[c]) and str(row[c]).lower() not in ("nan", "null", "")
    ]
    return " | ".join(filter(None, [
        str(row.get("title", "")),
        str(row.get("category", "")),
        str(row.get("content_texto", "")),
        " ".join(phrasings),
    ]))


def gerar_sql_update(df: pd.DataFrame, output_path: str):
    """
    Gera arquivo SQL com UPDATE statements para inserir os vetores
    na coluna pgvector do Supabase/PostgreSQL.

    Formato compatível com pgvector: '[0.1, 0.2, ...]'::vector
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"-- Vetores gerados por pipeline_vetorizacao.py\n")
        f.write(f"-- Modelo: {MODEL_NAME} ({df['vecs1'].iloc[0].count(',') + 1} dims)\n\n")
        for _, row in df.iterrows():
            vec_str = row[VEC_COLUMN]
            art_id  = str(row["articleId"]).replace("'", "''")
            f.write(
                f"UPDATE \"{TABLE_NAME}\" "
                f"SET \"{VEC_COLUMN}\" = '{vec_str}' "
                f"WHERE \"articleId\" = '{art_id}';\n"
            )


# ── Pipeline principal ────────────────────────────────────────────────────────

def main(input_csv: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)

    # 1. Carregar dados
    print(f"📖 Lendo: {input_csv}")
    df = pd.read_csv(input_csv)
    print(f"   → {len(df)} artigos encontrados")

    # 2. Extrair texto do JSONB
    if "content" in df.columns:
        print("🔍 Extraindo texto dos blocos JSONB...")
        df["content_texto"] = df["content"].apply(extrair_texto_jsonb)
    elif "content_texto" not in df.columns:
        raise ValueError("CSV precisa ter coluna 'content' (JSONB) ou 'content_texto' (texto puro).")

    # 3. Montar texto de embedding
    print("✍️  Preparando textos para vetorização...")
    df["texto_completo"] = df.apply(preparar_texto_embedding, axis=1)

    # 4. Carregar modelo e gerar embeddings
    print(f"⏳ Carregando modelo {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    dim   = model.get_sentence_embedding_dimension()
    print(f"   → Dimensão: {dim}")

    print(f"🧠 Gerando embeddings (batch_size={BATCH_SIZE})...")
    embeddings = model.encode(
        df["texto_completo"].tolist(),
        normalize_embeddings=True,   # Normalizado → dot product = cosine similarity
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
    )

    assert embeddings.shape == (len(df), dim), f"Shape inesperado: {embeddings.shape}"

    # 5. Serializar vetores
    df[VEC_COLUMN] = [json.dumps(emb.tolist()) for emb in embeddings]

    # 6. Salvar CSV
    csv_path = os.path.join(output_dir, "base_vetorizada.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"💾 CSV salvo: {csv_path}")

    # 7. Gerar SQL
    sql_path = os.path.join(output_dir, "update_vetores.sql")
    gerar_sql_update(df, sql_path)
    print(f"💾 SQL salvo: {sql_path}")

    # 8. Teste de busca semântica (smoke test)
    print("\n🔍 Smoke test — busca semântica:")
    queries = [
        "como realizar um saque",
        "minha conta foi bloqueada",
        "quero falar com atendente humano",
    ]
    for q in queries:
        q_vec  = model.encode([q], normalize_embeddings=True)[0]
        scores = embeddings @ q_vec
        top3   = np.argsort(scores)[-3:][::-1]
        print(f"\n  Query: \"{q}\"")
        for idx in top3:
            print(f"    [{scores[idx]:.3f}] {df.iloc[idx]['title']}")

    print(f"\n✅ Pipeline completo — {len(df)} artigos vetorizados ({dim} dimensões).")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AEGIS Knowledge Base Vectorizer")
    parser.add_argument("--input",  required=True, help="CSV de entrada (artigos da KB)")
    parser.add_argument("--output", default="output/", help="Diretório de saída")
    args = parser.parse_args()
    main(args.input, args.output)
