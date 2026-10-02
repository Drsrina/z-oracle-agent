# Knowledge Base Vectorizer

Pipeline de pré-processamento e vetorização da base de conhecimento do Z-Oracle Atendee.

Utiliza o mesmo modelo `all-MiniLM-L6-v2` empregado no `router.py` e `agent.py`, garantindo que a busca semântica da KB e o roteamento de intenções vivam no **mesmo espaço vetorial**.

## O que o pipeline faz

```
CSV com artigos (title, category, content JSONB, phrasings)
        │
        ▼ extrair_texto_jsonb()
   Texto puro extraído recursivamente dos blocos rich-text
        │
        ▼ preparar_texto_embedding()
   "Título | Categoria | Conteúdo | Phrasing 1 | Phrasing 2 ..."
        │
        ▼ SentenceTransformer.encode()
   Vetor normalizado 384 dimensões (dot product = cosine similarity)
        │
        ├──► base_vetorizada.csv
        └──► update_vetores.sql  (UPDATE para pgvector/Supabase)
```

## Uso

```bash
# Instalar dependências
pip install -r requirements.txt

# Rodar o pipeline
python pipeline_vetorizacao.py --input sua_base.csv --output saida/
```

## Formato do CSV de entrada

| Coluna | Obrigatória | Descrição |
|---|---|---|
| `articleId` | Sim | UUID do artigo |
| `title` | Sim | Título do artigo |
| `category` | Não | Categoria (ex: Saques, Depósito) |
| `content` | Sim* | Conteúdo em formato JSONB aninhado |
| `content_texto` | Sim* | Alternativa: texto já extraído |
| `phrasing`, `phrasing_1`... | Não | Variações de pergunta para busca |

*Forneça `content` (JSONB) **ou** `content_texto` (texto puro).

## Integração com o banco de dados

O SQL gerado é compatível com **pgvector** (Supabase/PostgreSQL). A coluna deve ser do tipo `vector(384)`:

```sql
-- Criar a coluna no banco (se não existir)
ALTER TABLE base_conhecimento ADD COLUMN vecs1 vector(384);

-- Criar índice para busca por similaridade
CREATE INDEX ON base_conhecimento USING ivfflat (vecs1 vector_cosine_ops);

-- Aplicar os vetores gerados
\i saida/update_vetores.sql
```

## Smoke test embutido

O script executa automaticamente 3 buscas semânticas ao final para validar a qualidade dos embeddings gerados.
