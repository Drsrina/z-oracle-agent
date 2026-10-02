import time
import logging
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import os
from dotenv import load_dotenv

# Carrega variáveis ambiente (GEMINI_API_KEY)
load_dotenv()

# ==========================================
# IMPORTAÇÕES DA ARQUITETURA INTERNA (Core & Infra)
# ==========================================
# Nota: Estas são chamadas modulares que você implementará nos outros ficheiros.
# O main.py apenas orquestra, não processa IA diretamente.
from core.router import classificar_rota, Rota
from core.guardrail import verificar_seguranca
from core.agent import processar_mensagem_llm
from infrastructure.redis_client import obter_estado, guardar_estado, EstadoConversa, redis_db
from infrastructure.supabase_logger import registar_log_assincrono, registar_historico_assincrono
from infrastructure.database import get_db_pool, close_db_pool
from api.graphql_schema import graphql_app
from starlette.concurrency import run_in_threadpool

# ==========================================
# CONFIGURAÇÃO DE LOGGING & APP
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("betagent_agent")

app = FastAPI(
    title="Z-Oracle Atendee API",
    description="API de atendimento cognitivo com roteamento semântico e RAG",
    version="5.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Monta a rota GraphQL
app.include_router(graphql_app, prefix="/graphql")

# ==========================================
# SCHEMAS PYDANTIC (Validação de Entrada/Saída)
# ==========================================
class WebhookPayload(BaseModel):
    """Esquema de entrada padrão (A adaptar conforme a documentação da Green API/Evolution API)"""
    telefone: str = Field(..., description="Número de telefone do remetente (ID da sessão)")
    mensagem: str = Field(..., description="Texto enviado pelo utilizador")
    nome_usuario: Optional[str] = Field(default="Cliente")

class WebhookResponse(BaseModel):
    status: str
    resposta_enviada: str

class IngestaoPayload(BaseModel):
    texto_conhecimento: str

class SimulacaoPagamentoPayload(BaseModel):
    telefone: str
    valor: float
    tipo: str = "deposito"

# ==========================================
# FUNÇÕES DE BACKGROUND (Resolver o Problema de Latência)
# ==========================================
async def tarefas_pos_processamento(estado: EstadoConversa, telefone: str, payload_log: dict, msg_user: str, msg_ast: str):
    """
    Executado em BACKGROUND após a API já ter respondido ao cliente.
    Resolve o 'Problema da Armadilha de Latência' da V4.
    """
    try:
        # 1. Sumarização Síncrona -> Assíncrona via threadpool (impede bloqueio do event loop)
        if estado.precisa_sumarizar():
            logger.info(f"[{telefone}] Iniciando compressão de memória (Rolling Summary)...")
            await run_in_threadpool(estado.executar_sumarizacao_llm) # Usa a thread correta pra I/O bloqueante
            guardar_estado(telefone, estado)  # Atualiza o Redis com a memória limpa
        
        # 2. Registo Persistente de Histórico no Supabase (sessoes = parent, mensagens = child)
        estado_dict = estado.model_dump() if hasattr(estado, "model_dump") else estado.__dict__
        sessao_id = await registar_historico_assincrono(telefone, estado_dict, msg_user, msg_ast)
        
        # 3. Registo de Logs em DB analítico conectado à Foreign Key (caso extraída no Passo 2)
        if sessao_id:
            payload_log["sessao_id"] = sessao_id
            
        await registar_log_assincrono(payload_log)
    except Exception as e:
        logger.error(f"[{telefone}] Erro nas tarefas de background: {str(e)}")

# ==========================================
# ENDPOINTS
# ==========================================

@app.on_event("startup")
async def startup_event():
    """Inicializa conexões com banco de dados PostgreSQL e recursos assíncronos."""
    await get_db_pool()

@app.on_event("shutdown")
async def shutdown_event():
    """Fecha conexões de banco de dados graciosamente."""
    await close_db_pool()

@app.get("/health", tags=["Infraestrutura"])
async def health_check():
    """Endpoint vital para Kubernetes/Docker saberem se a API e seus bancos estão vivos."""
    db_pool = await get_db_pool()
    redis_ok = False
    if redis_db:
        try:
            redis_ok = bool(redis_db.ping())
        except Exception:
            redis_ok = False

    return {
        "status": "online",
        "timestamp": time.time(),
        "services": {
            "redis": "connected" if redis_ok else "fallback_in_memory",
            "postgres": "connected" if db_pool is not None else "supabase_or_console_fallback"
        }
    }


@app.post("/api/ingerir", tags=["Admin"])
async def ingerir_texto(payload: IngestaoPayload):
    """Endpoint para atualizar o cérebro do bot via interface."""
    from core.agent import ingerir_conhecimento_dinamico
    try:
        ingerir_conhecimento_dinamico(payload.texto_conhecimento)
        return {"status": "sucesso", "mensagem": "Conhecimento atualizado!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/simular_webhook_pagamento", tags=["Admin"])
async def simular_webhook_pagamento(payload: SimulacaoPagamentoPayload, bg_tasks: BackgroundTasks):
    """
    Simula uma notificação de um sistema bancário externo avisando que o PIX caiu.
    Acorda o Agente MOCK para falar com o cliente sozinho.
    """
    estado = obter_estado(payload.telefone)
    if not estado:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
        
    async def notificar_llm_assincrono(estado_atual):
        logger.info(f"[{payload.telefone}] Executando aviso proativo de pagamento...")
        instrucao = f"[SISTEMA INVISÍVEL]: O {payload.tipo} no valor de R${payload.valor} do cliente acabou de cair e ser aprovado pelo gateway bancário! Envie uma única mensagem proativa, alegre e ultra-humana avisando que o dinheiro já está na conta! Pode usar emojis."
        
        # Chamamos o LLM forçando a instrução sem que o cliente tenha digitado
        result_tuple = await processar_mensagem_llm(estado_atual, instrucao, ferramentas_permitidas=[])
        if len(result_tuple) >= 4:
            resposta, _, veredicto, modelo_usado = result_tuple
        else:
            resposta, _ = result_tuple[:2]
        
        estado_atual.adicionar_mensagem("assistant", resposta)
        guardar_estado(payload.telefone, estado_atual)
        logger.info(f"[{payload.telefone}] Sucesso: LLM gerou notificação proativa.")

    bg_tasks.add_task(notificar_llm_assincrono, estado)
    return {"status": "sucesso", "mensagem": "Webhook recebido. O LLM notificará o cliente em breve."}


# Endpoint de Webhook Adormecido (Desativado temporariamente para uso do GraphQL Chat)
@app.post("/webhook_adormecido", response_model=WebhookResponse, tags=["Atendimento"])
async def receber_mensagem_whatsapp_inativo(payload: WebhookPayload, bg_tasks: BackgroundTasks):
    """
    Endpoint principal. Recebe a mensagem, orquestra o estado, RAG e ferramentas.
    """
    telefone = payload.telefone
    mensagem_usuario = payload.mensagem.strip()
    
    # type: ignore
    logger.info(f"[{telefone}] Nova mensagem recebida: '{str(mensagem_usuario)[:50]}...'")

    try:
        # ---------------------------------------------------------
        # PASSO 1: RECUPERAR ESTADO PERSISTENTE (Fim da amnésia do Jupyter)
        # ---------------------------------------------------------
        estado = obter_estado(telefone)
        if not estado:
            estado = EstadoConversa(session_id=telefone)
            logger.info(f"[{telefone}] Nova sessão criada no Redis.")

        # ---------------------------------------------------------
        # PASSO 2: SEGURANÇA E SANITIZAÇÃO (Fim da Regex cosmética)
        # ---------------------------------------------------------
        is_seguro, mensagem_sanitizada = await run_in_threadpool(verificar_seguranca, mensagem_usuario)
        if not is_seguro:
            logger.warning(f"[{telefone}] Tentativa de Prompt Injection detetada.")
            resposta = "Desculpe, não posso processar esse tipo de instrução. Como posso ajudar com os serviços da BetAgent?"
            
            # Atualiza histórico e envia
            estado.adicionar_mensagem("user", mensagem_usuario)
            estado.adicionar_mensagem("assistant", resposta)
            guardar_estado(telefone, estado)
            return {"status": "sucesso", "resposta_enviada": resposta}

        # ---------------------------------------------------------
        # PASSO 3: ROTEAMENTO SEMÂNTICO (Fim do "RAG Cego" e Cérebro Dividido)
        # ---------------------------------------------------------
        rota_info = await run_in_threadpool(classificar_rota, mensagem_sanitizada)
        rota_sugerida = rota_info.get("route", Rota.DUVIDA_TECNICA) if isinstance(rota_info, dict) else rota_info
        route_score = rota_info.get("route_score", 0.0) if isinstance(rota_info, dict) else 0.0
        route_latency = rota_info.get("latency", 0) if isinstance(rota_info, dict) else 0

        # Captura Sentimento novo
        from core.router import classificar_sentimento
        sent_info = await run_in_threadpool(classificar_sentimento, mensagem_sanitizada)
        sentimento_str = sent_info.get("sentiment", "Neutro") if isinstance(sent_info, dict) else sent_info
        sentiment_score = sent_info.get("sentiment_score", 0.0) if isinstance(sent_info, dict) else 0.0
        
        logger.info(f"[{telefone}] Rota classificada: {rota_sugerida}")

        resposta = ""
        tools_usadas = []
        confianca = None
        motivo = None
        modelo_usado = None

        # ---------------------------------------------------------
        # PASSO 4: EXECUÇÃO BASEADA EM ROTA
        # ---------------------------------------------------------
        
        # ROTA A: Determinística Pura (Código, zero LLM)
        if rota_sugerida == Rota.COLETA_DADOS and estado.etapa != "RESOLUCAO":
            # Aqui processamos CPF puramente com Regex + validate_docbr
            cpf_valido = estado.tentar_registar_cpf_da_mensagem(mensagem_sanitizada)
            if cpf_valido:
                resposta = f"Obrigado! O seu CPF (***{estado.cpf[-4:]}) foi validado. O que deseja fazer agora?"
            else:
                resposta = "Não consegui validar o CPF. Pode enviar novamente com os 11 dígitos corretos?"
        
        # ROTA B: Bate-papo (Respostas estáticas ou LLM sem ferramentas)
        elif rota_sugerida == Rota.BATE_PAPO:
            # Processa via LLM, mas BLOQUEIA o acesso à base de dados de regras
            result_tuple = await processar_mensagem_llm(estado, mensagem_sanitizada, ferramentas_permitidas=[])
            if len(result_tuple) >= 4:
                resposta, tools_usadas, veredicto, modelo_usado = result_tuple
                confianca = str(veredicto.get("confianca", "100")) + "%" if veredicto else None
                motivo = veredicto.get("motivo") if veredicto else None
            else:
                resposta, tools_usadas = result_tuple[:2]

        # ROTA C: IA Orquestrada (Tool Calling Dinâmico)
        else:
            # Injeta ferramentas ESTritamente baseadas na rota
            ferramentas = []
            if rota_sugerida == Rota.DUVIDA_TECNICA:
                ferramentas.append("consultar_manual")
            elif rota_sugerida == Rota.PROBLEMA or rota_sugerida == Rota.ESCALAR:
                ferramentas.append("transferir_para_humano")
            
            # O Agente (llama-index) assume o controlo aqui
            result_tuple = await processar_mensagem_llm(
                estado=estado, 
                mensagem=mensagem_sanitizada, 
                ferramentas_permitidas=ferramentas
            )
            if len(result_tuple) >= 4:
                resposta, tools_usadas, veredicto, modelo_usado = result_tuple
                confianca = str(veredicto.get("confianca", "100")) + "%" if veredicto else None
                motivo = veredicto.get("motivo") if veredicto else None
            else:
                resposta, tools_usadas = result_tuple[:2]

        # ---------------------------------------------------------
        # PASSO 5: ATUALIZAÇÃO DE ESTADO E PERSISTÊNCIA
        # ---------------------------------------------------------
        estado.adicionar_mensagem("user", mensagem_sanitizada)
        estado.adicionar_mensagem("assistant", resposta)
        
        # Guarda no Redis IMEDIATAMENTE antes da API fechar a conexão
        guardar_estado(telefone, estado)

        # ---------------------------------------------------------
        # PASSO 6: TAREFAS ASSÍNCRONAS (Delegar peso para Background)
        # ---------------------------------------------------------
        payload_log = {
            "telefone": telefone,
            "rota": rota_sugerida,
            "input": mensagem_sanitizada, # O guardrail já mascarou dados sensíveis aqui
            "resposta": resposta,
            "tools": tools_usadas,
            "confianca": confianca,
            "motivo": motivo,
            "model": modelo_usado,
            "route_score": route_score,
            "sentiment": sentimento_str,
            "sentiment_score": sentiment_score,
            "latency_route": route_latency,
        }
        # Adiciona à fila do FastAPI para processar DEPOIS do return
        bg_tasks.add_task(tarefas_pos_processamento, estado, telefone, payload_log, mensagem_sanitizada, resposta)

        # ---------------------------------------------------------
        # PASSO 7: RETORNO (Para a API do WhatsApp enviar ao cliente)
        # ---------------------------------------------------------
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "processado", "resposta_enviada": resposta}
        )

    except Exception as e:
        # Tratamento global de erros: Nunca deixamos o WhatsApp em vácuo
        logger.error(f"[{telefone}] ERRO CRÍTICO NO WEBHOOK: {str(e)}", exc_info=True)
        
        # Devolvemos 200 OK com mensagem de fallback para o utilizador, 
        # caso contrário o provedor do Webhook pode tentar reenviar a mensagem em loop
        mensagem_fallback = "Desculpe, a nossa plataforma está a passar por uma instabilidade técnica momentânea. Por favor, tente novamente em alguns minutos."
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "erro_interno", "resposta_enviada": mensagem_fallback}
        )

# Para correr a API localmente durante o desenvolvimento:
# uvicorn api.main:app --reload --port 8000