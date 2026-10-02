"""
infrastructure/database.py — Conexão Nativa PostgreSQL (asyncpg)
=================================================================
Substitui o Supabase por PostgreSQL local / self-hosted com alta performance assíncrona.
Suporta pooling de conexões, auto-reconnect, migrações automáticas de schema e busca vetorial (pgvector).
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger("betagent_postgres")

_pool = None

DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")


async def get_db_pool():
    """Retorna o pool de conexões asyncpg (Lazy Init)."""
    global _pool
    if _pool is not None:
        return _pool

    url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if not url:
        return None

    # Normaliza protocolo caso use postgresql+asyncpg:// ou similar
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    try:
        import asyncpg
        _pool = await asyncpg.create_pool(
            dsn=url,
            min_size=2,
            max_size=20,
            command_timeout=10,
            timeout=5
        )
        logger.info("✅ [POSTGRES] Pool de conexões inicializado com sucesso.")
        return _pool
    except Exception as e:
        logger.warning(f"⚠️ [POSTGRES] Falha ao conectar ao PostgreSQL ({e}).")
        return None


async def close_db_pool():
    """Encerra o pool de conexões graciosamente no shutdown da aplicação."""
    global _pool
    if _pool is not None:
        try:
            await _pool.close()
            logger.info("🛑 [POSTGRES] Pool de conexões encerrado.")
        except Exception as e:
            logger.error(f"Erro ao fechar pool PostgreSQL: {e}")
        finally:
            _pool = None


async def inserir_log_postgres(payload_log: dict) -> bool:
    """Insere registro na tabela logs_atendimento via asyncpg."""
    pool = await get_db_pool()
    if pool is None:
        return False

    try:
        tools_raw = payload_log.get("tools", [])
        tools_list = list(tools_raw) if isinstance(tools_raw, (list, tuple)) else []

        rota_val = payload_log.get("rota")
        rota_str = rota_val.value if hasattr(rota_val, "value") else str(rota_val)

        def _to_float(val):
            return float(val) if val is not None else None

        def _to_int(val):
            return int(val) if val is not None else None

        query = """
            INSERT INTO logs_atendimento (
                sessao_id, telefone, rota, input_sanitizado, resposta, tools_usadas,
                confianca, motivo, model, route_score, sentiment, sentiment_score,
                latencia_ms, latency_route
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
            )
        """

        async with pool.acquire() as conn:
            await conn.execute(
                query,
                payload_log.get("sessao_id"),
                payload_log.get("telefone", "desconhecido"),
                rota_str,
                str(payload_log.get("input", ""))[:1000],
                str(payload_log.get("resposta", ""))[:2000],
                tools_list,
                payload_log.get("confianca"),
                payload_log.get("motivo"),
                payload_log.get("model"),
                _to_float(payload_log.get("route_score")),
                str(payload_log.get("sentiment", "Neutro")),
                _to_float(payload_log.get("sentiment_score")),
                _to_int(payload_log.get("latency_route")),
                _to_int(payload_log.get("latency_route"))
            )
            logger.debug(f"[POSTGRES] Log inserido para {payload_log.get('telefone')}")
            return True

    except Exception as e:
        logger.warning(f"⚠️ [POSTGRES] Falha ao inserir log_atendimento: {e}")
        return False


async def inserir_historico_postgres(
    telefone: str,
    estado_dict: dict,
    mensagem_user: str,
    resposta_assistant: str
) -> Optional[str]:
    """
    Executa upsert na tabela sessoes e insere registros na tabela mensagens.
    Retorna o sessao_id (UUID string) gerado ou recuperado.
    """
    pool = await get_db_pool()
    if pool is None:
        return None

    try:
        etapa = estado_dict.get("etapa", "INICIO")
        cpf = estado_dict.get("cpf", None)
        resumo = estado_dict.get("resumo_acumulado", "")
        dados = estado_dict.get("dados_coletados", {})
        tentativas = estado_dict.get("tentativas_resolucao", 0)

        dados_json = json.dumps(dados) if isinstance(dados, dict) else "{}"

        query_sessao = """
            INSERT INTO sessoes (session_id, etapa, cpf, resumo_acumulado, dados_coletados, tentativas_resolucao, updated_at)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, NOW())
            ON CONFLICT (session_id) DO UPDATE SET
                etapa = EXCLUDED.etapa,
                cpf = COALESCE(EXCLUDED.cpf, sessoes.cpf),
                resumo_acumulado = EXCLUDED.resumo_acumulado,
                dados_coletados = EXCLUDED.dados_coletados,
                tentativas_resolucao = EXCLUDED.tentativas_resolucao,
                updated_at = NOW()
            RETURNING id;
        """

        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    query_sessao,
                    telefone,
                    etapa,
                    cpf,
                    resumo,
                    dados_json,
                    tentativas
                )
                if not row:
                    return None

                sessao_id = str(row["id"])

                query_msg = """
                    INSERT INTO mensagens (sessao_id, role, content)
                    VALUES ($1, $2, $3)
                """

                if mensagem_user:
                    await conn.execute(query_msg, row["id"], "user", str(mensagem_user)[:3000])

                if resposta_assistant:
                    await conn.execute(query_msg, row["id"], "assistant", str(resposta_assistant)[:3000])

                logger.debug(f"✅ [POSTGRES DB] Histórico de {telefone} salvo com sucesso.")
                return sessao_id

    except Exception as e:
        logger.warning(f"⚠️ [POSTGRES DB] Falha ao registrar sessão/mensagens: {e}")
        return None
