import os
import logging
from typing import Optional
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger("betagent_supabase")

# ==========================================
# CLIENTE SUPABASE (Lazy Init)
# ==========================================
_supabase_client = None

def _get_client():
    """Retorna o cliente Supabase, inicializando na primeira chamada."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")

    if not url or not key:
        logger.warning("⚠️ [SUPABASE] Variáveis SUPABASE_URL / SUPABASE_ANON_KEY não definidas. Logger desativado.")
        return None

    try:
        from supabase import create_client
        _supabase_client = create_client(url, key)
        logger.info("✅ [SUPABASE] Cliente inicializado com sucesso.")
        return _supabase_client
    except Exception as e:
        logger.error(f"❌ [SUPABASE] Falha ao inicializar cliente: {e}")
        return None


# ==========================================
# INTERFACE PRINCIPAL
# ==========================================
async def registar_log_assincrono(payload_log: dict):
    """
    Insere um registo na tabela 'logs_atendimento' do Supabase.
    Se falhar (timeout, auth, etc.), apenas loga no console — nunca bloqueamos o fluxo.

    Schema esperado da tabela:
        logs_atendimento (
            id          uuid default gen_random_uuid() primary key,
            created_at  timestamptz default now(),
            telefone    text,
            rota        text,
            input       text,
            resposta    text,
            tools       text[],
            confianca   text,
            motivo      text,
            route_score float,
            sentiment   text,
            sentiment_score float,
            latency_route integer,
            model       text
        )
    """
    client = _get_client()

    if client is None:
        # Fallback: loga no console
        logger.info(f"📋 [LOG LOCAL] {payload_log}")
        return

    try:
        # Serializa a lista de tools para array de texto
        tools_raw = payload_log.get("tools", [])
        tools_list = list(tools_raw) if isinstance(tools_raw, (list, tuple)) else []

        # Converte o enum Rota para string se necessário
        rota_val = payload_log.get("rota")
        rota_str = rota_val.value if hasattr(rota_val, "value") else str(rota_val)

        # Tratar scores e latências para garantir tipagem correta ou none
        def _to_float(val): return float(val) if val is not None else None
        def _to_int(val): return int(val) if val is not None else None

        # Map payload to database column names matching logs_atendimento schema
        data = {
            "sessao_id": payload_log.get("sessao_id"),
            "telefone": payload_log.get("telefone", "desconhecido"),
            "rota": rota_str,
            "input_sanitizado": str(payload_log.get("input", ""))[:1000],   # truncate long texts
            "resposta": str(payload_log.get("resposta", ""))[:2000],
            "tools_usadas": tools_list,  # column name in DB
            # New analytical fields
            "confianca": payload_log.get("confianca"),
            "motivo": payload_log.get("motivo"),
            "model": payload_log.get("model"),
            "route_score": _to_float(payload_log.get("route_score")),
            "sentiment": str(payload_log.get("sentiment", "Neutro")),
            "sentiment_score": _to_float(payload_log.get("sentiment_score")),
            "latencia_ms": _to_int(payload_log.get("latency_route")),
            "latency_route": _to_int(payload_log.get("latency_route"))
        }

        # Remove chaves com None para evitar falhas no driver nativo do Supabase caso a coluna
        # tenha defaults ou não permita explícito null inesperado.
        data_clean = {k: v for k, v in data.items() if v is not None}

        await run_in_threadpool(lambda: client.table("logs_atendimento").insert(data_clean).execute())
        logger.debug(f"[SUPABASE] Log inserido para {data_clean['telefone']}")

    except Exception as e:
        # Nunca deixamos o logger derrubar o fluxo principal
        logger.warning(f"⚠️ [SUPABASE] Falha ao inserir log (non-critical): {e}")
        logger.info(f"📋 [LOG LOCAL FALLBACK] {payload_log}")

async def registar_historico_assincrono(telefone: str, estado_dict: dict, mensagem_user: str, resposta_assistant: str):
    """
    Insere na tabela 'sessoes' e 'mensagens' para manter histórico persistente além do Redis.
    Retorna o sessao_id (uuid) para vinculação de chaves estrangeiras.
    """
    client = _get_client()
    if client is None: return None

    try:
        etapa = estado_dict.get("etapa", "INICIO")
        cpf = estado_dict.get("cpf", None)
        resumo = estado_dict.get("resumo_acumulado", "")
        dados = estado_dict.get("dados_coletados", {})

        sessao_data = {
            "session_id": telefone,
            "etapa": etapa,
            "cpf": cpf,
            "resumo_acumulado": resumo,
            "dados_coletados": dados,
            "tentativas_resolucao": estado_dict.get("tentativas_resolucao", 0)
        }

        # Para funcionar tanto com on_conflict_resolution nativo do PostgreSQL Supabase.
        # Faz upsert na sessão (run_in_threadpool evita bloquear o event loop asyncio)
        sessao = await run_in_threadpool(
            lambda: client.table("sessoes").upsert(sessao_data, on_conflict="session_id").execute()
        )
        
        if sessao.data and len(sessao.data) > 0:
            sessao_id = sessao.data[0].get("id")
            
            mensagens_insert = []
            if mensagem_user:
                mensagens_insert.append({"sessao_id": sessao_id, "role": "user", "content": str(mensagem_user)[:3000]})
            if resposta_assistant:
                mensagens_insert.append({"sessao_id": sessao_id, "role": "assistant", "content": str(resposta_assistant)[:3000]})
                
            if mensagens_insert:
                await run_in_threadpool(lambda: client.table("mensagens").insert(mensagens_insert).execute())
                logger.debug(f"✅ [SUPABASE DB] Mensagens de {telefone} salvas com sucesso.")
            
            return sessao_id
            
    except Exception as e:
        logger.warning(f"⚠️ [SUPABASE DB] Falha ao gravar histórico em tabelas sessoes/mensagens: {e}")
        
    return None
