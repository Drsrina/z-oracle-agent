import os
import logging
from typing import Optional
from starlette.concurrency import run_in_threadpool

from infrastructure.database import (
    DATABASE_URL,
    get_db_pool,
    inserir_log_postgres,
    inserir_historico_postgres,
)

logger = logging.getLogger("betagent_db_logger")

# ==========================================
# CLIENTE SUPABASE (Fallback legado na nuvem)
# ==========================================
_supabase_client = None

def _get_supabase_client():
    """Retorna o cliente Supabase caso configurado, como fallback."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")

    if not url or not key:
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
# INTERFACE PRINCIPAL UNIFICADA (PostgreSQL / Supabase / Local)
# ==========================================
async def registar_log_assincrono(payload_log: dict):
    """
    Insere um registo na tabela 'logs_atendimento'.
    Prioridade:
      1. PostgreSQL nativo (DATABASE_URL / POSTGRES_URL)
      2. Supabase Cloud (SUPABASE_URL + SUPABASE_ANON_KEY)
      3. Fallback console local
    """
    # 1. Tenta PostgreSQL nativo
    if DATABASE_URL or os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL"):
        sucesso = await inserir_log_postgres(payload_log)
        if sucesso:
            return

    # 2. Tenta Supabase legado
    client = _get_supabase_client()
    if client is not None:
        try:
            tools_raw = payload_log.get("tools", [])
            tools_list = list(tools_raw) if isinstance(tools_raw, (list, tuple)) else []

            rota_val = payload_log.get("rota")
            rota_str = rota_val.value if hasattr(rota_val, "value") else str(rota_val)

            def _to_float(val): return float(val) if val is not None else None
            def _to_int(val): return int(val) if val is not None else None

            data = {
                "sessao_id": payload_log.get("sessao_id"),
                "telefone": payload_log.get("telefone", "desconhecido"),
                "rota": rota_str,
                "input_sanitizado": str(payload_log.get("input", ""))[:1000],
                "resposta": str(payload_log.get("resposta", ""))[:2000],
                "tools_usadas": tools_list,
                "confianca": payload_log.get("confianca"),
                "motivo": payload_log.get("motivo"),
                "model": payload_log.get("model"),
                "route_score": _to_float(payload_log.get("route_score")),
                "sentiment": str(payload_log.get("sentiment", "Neutro")),
                "sentiment_score": _to_float(payload_log.get("sentiment_score")),
                "latencia_ms": _to_int(payload_log.get("latency_route")),
                "latency_route": _to_int(payload_log.get("latency_route"))
            }

            data_clean = {k: v for k, v in data.items() if v is not None}
            await run_in_threadpool(lambda: client.table("logs_atendimento").insert(data_clean).execute())
            logger.debug(f"[SUPABASE] Log inserido para {data_clean['telefone']}")
            return
        except Exception as e:
            logger.warning(f"⚠️ [SUPABASE] Falha ao inserir log (non-critical): {e}")

    # 3. Fallback console local
    logger.info(f"📋 [LOG LOCAL] {payload_log}")


async def registar_historico_assincrono(
    telefone: str,
    estado_dict: dict,
    mensagem_user: str,
    resposta_assistant: str
) -> Optional[str]:
    """
    Insere na tabela 'sessoes' e 'mensagens' para manter histórico persistente.
    Retorna o sessao_id (uuid string).
    """
    # 1. Tenta PostgreSQL nativo
    if DATABASE_URL or os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL"):
        sessao_id = await inserir_historico_postgres(
            telefone, estado_dict, mensagem_user, resposta_assistant
        )
        if sessao_id:
            return sessao_id

    # 2. Tenta Supabase legado
    client = _get_supabase_client()
    if client is not None:
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
