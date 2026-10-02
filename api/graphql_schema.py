import time
import asyncio
import logging
import json
import strawberry
from strawberry.extensions import SchemaExtension
from typing import List, Optional, Any
from strawberry.fastapi import GraphQLRouter

from infrastructure.redis_client import obter_estado, guardar_estado, EstadoConversa
from core.guardrail import verificar_seguranca
from core.router import classificar_rota, Rota, classificar_cynefin
from core.agent import processar_mensagem_llm
from core.clarificador import (
    calcular_probabilidades_caminhos,
    avaliar_necessidade_clarificacao,
    acumular_intencao,
    calcular_intencao_acumulada,
    extrair_nome,
    gerar_eco,
    processar_resposta_eco,
    verificar_gate_diagnostico,
    extrair_veredicto_expandido
)
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger("betagent_graphql")

class GraphQLDetailedLogging(SchemaExtension):
    def on_operation(self):
        self.start_time = time.time()
        query_snippet = str(self.execution_context.query)[:150].replace('\n', ' ')
        logger.info(f"[GraphQL] [INÍCIO] Operação recebida: {query_snippet}...")
        if self.execution_context.variables:
            logger.info(f"[GraphQL] [INÍCIO] Variáveis: {self.execution_context.variables}")
        yield
        duration = (time.time() - self.start_time) * 1000
        logger.info(f"[GraphQL] [FIM] Operação concluída. Duração TOTAL: {duration:.2f}ms")

    def on_parse(self):
        start = time.time()
        yield
        duration = (time.time() - start) * 1000
        logger.info(f"[GraphQL] [TRACE] Parsing concluído em {duration:.2f}ms")

    def on_validate(self):
        start = time.time()
        yield
        duration = (time.time() - start) * 1000
        logger.info(f"[GraphQL] [TRACE] Validação concluída em {duration:.2f}ms")

    def on_execute(self):
        start = time.time()
        yield
        duration = (time.time() - start) * 1000
        logger.info(f"[GraphQL] [TRACE] Execução dos resolvers concluída em {duration:.2f}ms")

@strawberry.type
class MensagemHistorico:
    role: str
    content: str
    confianca: Optional[str] = None
    motivo: Optional[str] = None
    model: Optional[str] = None
    route_score: Optional[float] = None
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    latency_route: Optional[int] = None
    probabilidades: Optional[str] = None  # JSON string com % de cada caminho
    log_guardrail: Optional[str] = None
    log_roteamento: Optional[str] = None
    log_rag: Optional[str] = None
    log_geracao: Optional[str] = None
    
    @strawberry.field
    def papel(self) -> str:
        return self.role
        
    @strawberry.field
    def conteudo(self) -> str:
        return self.content

@strawberry.type
class EnviarMensagemResponse:
    status: str
    mensagem: str
    aguarde: bool

async def debounce_e_processar(telefone: str, timestamp_task: float):
    """
    Aguarda 2 segundos. Se o timestamp_task ainda for igual ao ultimo_timestamp
    do estado no Redis, processamos todas as mensagens agrupadas.
    """
    await asyncio.sleep(2)
    estado = obter_estado(telefone)
    if not estado:
        return
        
    # Verifica se o usuário não digitou mais nada
    if estado.ultimo_timestamp == timestamp_task:
        # Buffer consolidado
        if not estado.buffer_pendente:
            return
            
        mensagem_unificada = "\n".join(estado.buffer_pendente)
        estado.buffer_pendente = [] # Limpamos o buffer
        guardar_estado(telefone, estado) # Salva a limpeza antes do processamento
        
        logger.info(f"[{telefone}] Buffer unificado acionado: '{mensagem_unificada[:50]}...'")
        
        try:
            # ---------------------------------------------------------
            # STEP 0: EXTRAÇÃO DE NOME (Memória de Identidade)
            # ---------------------------------------------------------
            nome_detectado = extrair_nome(mensagem_unificada)
            if nome_detectado and not estado.nome_usuario:
                estado.registar_nome(nome_detectado)
                logger.info(f"[{telefone}] Nome do cliente capturado: {nome_detectado}")

            # ---------------------------------------------------------
            # FLUXO PRINCIPAL COM CLARIFICAÇÃO INTELIGENTE
            # ---------------------------------------------------------
            is_seguro, mensagem_sanitizada = await run_in_threadpool(verificar_seguranca, mensagem_unificada)
            
            estado.ultimo_log_guardrail = {
                "safe": is_seguro,
                "piiMasked": mensagem_unificada != mensagem_sanitizada,
                "maskedText": mensagem_sanitizada,
                "reason": "Permitido" if is_seguro else "Violou regra de segurança"
            }
            
            if not is_seguro:
                estado.adicionar_mensagem("user", mensagem_unificada)
                estado.adicionar_mensagem("assistant", "Desculpe, não posso processar esse tipo de instrução.")
                guardar_estado(telefone, estado)
                return
                
            rota_info = await run_in_threadpool(classificar_rota, mensagem_sanitizada)
            rota_sugerida = rota_info.get("route", Rota.DUVIDA_TECNICA) if isinstance(rota_info, dict) else rota_info
            route_score = rota_info.get("route_score", 0.0) if isinstance(rota_info, dict) else 0.0
            route_latency = rota_info.get("latency", 0) if isinstance(rota_info, dict) else 0

            from core.router import classificar_sentimento
            sent_info = await run_in_threadpool(classificar_sentimento, mensagem_sanitizada)
            sentimento_str = sent_info.get("sentiment", "Neutro") if isinstance(sent_info, dict) else sent_info
            sentiment_score = sent_info.get("sentiment_score", 0.0) if isinstance(sent_info, dict) else 0.0

            # ---------------------------------------------------------
            # STEP 1: CÁLCULO DE PROBABILIDADES DE CAMINHOS (%)
            # ---------------------------------------------------------
            probabilidades = await run_in_threadpool(calcular_probabilidades_caminhos, mensagem_sanitizada)
            prob_json = str(probabilidades)  # Para log/metadata
            logger.info(f"[{telefone}] Probabilidades: {probabilidades}")

            # ---------------------------------------------------------
            # STEP 2: ACUMULAÇÃO DE INTENÇÕES (Cross-Turn)
            # ---------------------------------------------------------
            rota_str = rota_sugerida.value if hasattr(rota_sugerida, 'value') else str(rota_sugerida)
            estado.historico_intencoes = acumular_intencao(
                estado.historico_intencoes, rota_info, probabilidades
            )

            # Verifica se a intenção acumulada aponta para uma rota diferente
            intencao_acumulada = calcular_intencao_acumulada(estado.historico_intencoes)
            if intencao_acumulada and route_score < 0.65:
                # A intenção acumulada tem precedência se o score individual é baixo
                rota_sugerida = Rota(intencao_acumulada)
                route_score = 0.70  # Boost de confiança por consistência cross-turn
                logger.info(f"[{telefone}] Intenção acumulada aplicada: {intencao_acumulada} (boost para 0.70)")

            # ---------------------------------------------------------
            # STEP 2.5: INICIALIZAR/ATUALIZAR QUESTION PATH (Fim da Rota Preguiçosa)
            # ---------------------------------------------------------
            # Mapa de campos necessários por rota para detectar mudanças
            ROTA_CAMPOS = {
                "DUVIDA_TECNICA": ["nome", "problema_descricao"],
                "TRANSACAO_FINANCEIRA": ["nome", "cpf", "tipo_transacao", "valor"],
                "PROBLEMA": ["nome", "problema_descricao", "tentativas_anteriores"],
                "COLETA_DADOS": ["nome", "cpf"],
                "BATE_PAPO": ["nome"],
                "ESCALAR": ["nome", "problema_descricao"],
            }
            campos_alvo = ROTA_CAMPOS.get(rota_str, ["nome"])

            # Se a rota mudou significativamente ou nunca foi iniciada, atualizamos o path
            if estado.question_path.get('required') != campos_alvo:
                estado.iniciar_question_path(rota_str)
                logger.info(f"[{telefone}] Question path atualizado para rota {rota_str}: {estado.question_path}")

            # ---------------------------------------------------------
            # STEP 2.6: REGISTRO DO PROBLEMA ORIGINAL (Anti-Drift)
            # ---------------------------------------------------------
            if not estado.problema_original and rota_str in ['DUVIDA_TECNICA', 'PROBLEMA', 'ESCALAR']:
                estado.registar_problema_original(mensagem_sanitizada)

            # Atualiza sentimento e classifica domínio Cynefin
            estado.perfil_sentimental = sentimento_str
            estado.cynefin_domain = classificar_cynefin(
                rota_str, sentimento_str, estado.tentativas_resolucao
            )
            estado.recalcular_confianca()
            logger.info(f"[{telefone}] Cynefin: {estado.cynefin_domain} | Confiança: {estado.confianca}%")
            
            # Popula log de Roteamento agora que temos cynefin_domain
            estado.ultimo_log_roteamento = {
                "route": rota_str,
                "routeScore": route_score,
                "sentiment": sentimento_str,
                "sentimentScore": sentiment_score,
                "cynefinDomain": estado.cynefin_domain,
                "latency": route_latency,
                "reason": rota_info.get("reason", "") if isinstance(rota_info, dict) else ""
            }

            # ---------------------------------------------------------
            # STEP 3: VERIFICAÇÃO DE ECO BLOQUEANTE
            # ---------------------------------------------------------
            # Se estamos em ECO_PENDENTE, processa a resposta do eco
            if estado.etapa == 'ECO_PENDENTE':
                eco_confirmado = processar_resposta_eco(mensagem_sanitizada)
                if eco_confirmado:
                    estado.eco_confirmado = True
                    estado.etapa = 'DIAGNOSTICO'
                    estado.recalcular_confianca()
                    logger.info(f"[{telefone}] Eco CONFIRMADO. Confiança recalculada: {estado.confianca}%")
                else:
                    # Usuário corrigiu — re-inicia coleta
                    estado.eco_buffer = None
                    estado.eco_confirmado = False
                    estado.etapa = 'COLETA'
                    logger.info(f"[{telefone}] Eco REJEITADO. Voltando para COLETA.")

            # ---------------------------------------------------------
            # STEP 4: AVALIAÇÃO DE CLARIFICAÇÃO
            # ---------------------------------------------------------
            precisa_clarificar, instrucao_sugerida = avaliar_necessidade_clarificacao(
                route_score=route_score,
                rota_sugerida=rota_str,
                probabilidades=probabilidades,
                perguntas_feitas=estado.perguntas_clarificacao,
                etapa_atual=estado.etapa,
                turnos_conversa=len(estado.mensagens_recentes)
            )

            resposta = ""
            ferramentas = []
            confianca = None
            motivo = None
            modelo_usado = None
            veredicto_dict = {} # FIX: Inicialização antecipada evita UnboundLocalError
            
            if precisa_clarificar and instrucao_sugerida:
                estado.perguntas_clarificacao += 1
                logger.info(f"[{telefone}] Instrução clarificadora invisível acionada (#{estado.perguntas_clarificacao})")
                
                rtup = await processar_mensagem_llm(estado, mensagem_sanitizada, ferramentas_permitidas=[], instrucao_extra=instrucao_sugerida)
                if len(rtup) >= 4:
                    resposta, ferramentas, veredicto_dict, modelo_usado = rtup
                    confianca = str(veredicto_dict.get("confianca", "100")) + "%"
                    motivo = veredicto_dict.get("motivo", "Ambiguidade - Pergunta Contextual Formulada")
                else:
                    resposta, ferramentas = rtup[:2]
            else:
                # Reseta o contador de clarificação ao agir
                estado.resetar_clarificacao()

                # ---------------------------------------------------------
                # FLUXO NORMAL DE PROCESSAMENTO (com tools)
                # ---------------------------------------------------------
                if rota_sugerida == Rota.COLETA_DADOS and estado.etapa != "RESOLUCAO":
                    if estado.tentar_registar_cpf_da_mensagem(mensagem_sanitizada):
                        resposta = f"Obrigado! O seu CPF (***{estado.cpf[-4:]}) foi validado."
                    else:
                        resposta = "Não consegui validar o CPF. Pode enviar novamente?"
                elif rota_sugerida == Rota.BATE_PAPO:
                    rtup = await processar_mensagem_llm(estado, mensagem_sanitizada, ferramentas_permitidas=[])
                    if len(rtup) >= 4:
                        resposta, ferramentas, veredicto_dict, modelo_usado = rtup
                        confianca = str(veredicto_dict.get("confianca", "100")) + "%"
                        motivo = veredicto_dict.get("motivo", "Bate-papo")
                    else:
                        resposta, ferramentas = rtup[:2]
                else:
                    if rota_sugerida == Rota.DUVIDA_TECNICA:
                        ferramentas.append("consultar_manual")
                    elif rota_sugerida in [Rota.PROBLEMA, Rota.ESCALAR]:
                        ferramentas.append("transferir_para_humano")
                    elif rota_sugerida == Rota.TRANSACAO_FINANCEIRA:
                        ferramentas.extend(["consultar_manual", "realizar_deposito", "realizar_saque"])
                    
                    # Log diagnóstico ANTES da chamada LLM (rastrear falhas silenciosas)
                    campos_faltantes_log = [c for c in estado.question_path.get('required', []) if c not in estado.question_path.get('collected', [])]
                    logger.info(
                        f"[{telefone}] 🧠 Chamando LLM | Rota: {rota_sugerida} | "
                        f"Coverage: {estado.question_path.get('coverage_percent', 0)}% | "
                        f"Confiança: {estado.confianca}% | "
                        f"Cynefin: {estado.cynefin_domain}"
                    )
                    
                    rtup = await processar_mensagem_llm(estado, mensagem_sanitizada, ferramentas_permitidas=ferramentas)
                    if len(rtup) >= 4:
                        resposta, ferramentas, veredicto_dict, modelo_usado = rtup
                        confianca = str(veredicto_dict.get("confianca", "100")) + "%"
                        motivo = veredicto_dict.get("motivo", "Processado")
                    else:
                        resposta, ferramentas = rtup[:2]

            # ---------------------------------------------------------
            # EXTRAÇÃO DE NOME DA RESPOSTA DO USUÁRIO (pós-processamento)
            # ---------------------------------------------------------
            if not estado.nome_usuario:
                nome_pos = extrair_nome(mensagem_sanitizada)
                if nome_pos:
                    estado.registar_nome(nome_pos)

            # ---------------------------------------------------------
            # FIX: FALLBACK PARA RESPOSTA VAZIA
            # Se o LLM retornou vazio, timeout, ou o veredicto consumiu 100% da resposta,
            # garante que o usuário SEMPRE recebe alguma mensagem.
            # ---------------------------------------------------------
            if not resposta or not resposta.strip():
                resposta = "Desculpe, estou processando sua solicitação. Pode repetir de outra forma?"
                logger.warning(f"[{telefone}] ⚠️ Resposta vazia detectada — fallback ativado. Rota: {rota_sugerida}, Confiança: {estado.confianca}%, Cynefin: {estado.cynefin_domain}")
                if not motivo:
                    motivo = "Resposta vazia — fallback"

            estado.adicionar_mensagem("user", mensagem_sanitizada)
            estado.adicionar_mensagem(
                "assistant", 
                resposta,
                confianca=confianca,
                motivo=motivo,
                model=modelo_usado,
                route_score=route_score,
                sentiment=sentimento_str,
                sentiment_score=sentiment_score,
                latency_route=route_latency,
                probabilidades=prob_json,
                log_guardrail=json.dumps(estado.ultimo_log_guardrail) if estado.ultimo_log_guardrail else None,
                log_roteamento=json.dumps(getattr(estado, "ultimo_log_roteamento", None)) if getattr(estado, "ultimo_log_roteamento", None) else None,
                log_rag=json.dumps(estado.ultimo_log_rag) if estado.ultimo_log_rag else None,
                log_geracao=json.dumps(estado.ultimo_log_geracao) if estado.ultimo_log_geracao else None
            )
            
            # Limpa logs do estado atual após consolidar no histórico
            estado.ultimo_log_guardrail = None
            if hasattr(estado, "ultimo_log_roteamento"):
                estado.ultimo_log_roteamento = None
            estado.ultimo_log_rag = None
            estado.ultimo_log_geracao = None
            guardar_estado(telefone, estado)
            
            payload_log = {
                "telefone": telefone,
                "rota": rota_sugerida,
                "input": mensagem_sanitizada,
                "resposta": resposta,
                "tools": ferramentas,
                "confianca": confianca,
                "motivo": motivo,
                "model": modelo_usado,
                "route_score": route_score,
                "sentiment": sentimento_str,
                "sentiment_score": sentiment_score,
                "latency_route": route_latency,
                "probabilidades": prob_json,
            }
            from infrastructure.supabase_logger import registar_log_assincrono, registar_historico_assincrono
            
            # ---------------------------------------------------------
            # SINCRONIZAÇÃO DE ESTADO (Cérebro IA -> Redis)
            # ---------------------------------------------------------
            if veredicto_dict:
                for campo in veredicto_dict.get("campos_coletados", []):
                    estado.marcar_campo_coletado(campo)
                
                eco_status = veredicto_dict.get("eco_status", "NAO_INICIADO")
                if eco_status == "PENDENTE":
                    estado.etapa = "ECO_PENDENTE"
                    logger.info(f"[{telefone}] Máquina de Estados: Movida para ECO_PENDENTE")
                elif eco_status == "CONFIRMADO":
                    estado.eco_confirmado = True
                    estado.etapa = "DIAGNOSTICO"

            # ---------------------------------------------------------
            # TAREFAS DE BACKGROUND (Sumarização, DB de Sessão, Logs)
            # ---------------------------------------------------------
            # Fazemos bind das variáveis locais para o closure assíncrono
            async def background_tasks(tel=telefone, st_dump=estado.model_dump() if hasattr(estado, "model_dump") else estado.__dict__, msg=mensagem_sanitizada, resp=resposta, p_log=payload_log, est=estado):
                try:
                    # 1. Sumariza se necessário (evita bloquear resposta)
                    if est.precisa_sumarizar():
                        logger.info(f"[{tel}] Iniciando compressão de memória (Rolling Summary)...")
                        await run_in_threadpool(est.executar_sumarizacao_llm)
                        guardar_estado(tel, est)

                    # 2. Registo Persistente de Histórico no Supabase (sessoes, mensagens)
                    sessao_id = await registar_historico_assincrono(tel, st_dump, msg, resp)
                    
                    # 3. Registo de Logs vinculando a FK sessao_id se existir
                    if sessao_id:
                        p_log["sessao_id"] = sessao_id
                    await registar_log_assincrono(p_log)
                except Exception as e:
                    logger.error(f"[{tel}] Erro nas background tasks do banco: {str(e)}")

            asyncio.create_task(background_tasks())
            
            logger.info(f"[{telefone}] Resumo processado. A aguardar front-end consumir.")
        except Exception as e:
            logger.error(f"[{telefone}] Erro crítico na task de debounce_e_processar: {str(e)}", exc_info=True)
            # FIX: Garante que o usuário recebe feedback mesmo em caso de crash do pipeline
            try:
                estado.adicionar_mensagem("user", mensagem_unificada)
                estado.adicionar_mensagem(
                    "assistant",
                    "Desculpe, tive uma dificuldade técnica momentânea. Pode reformular sua pergunta?",
                    motivo=f"Erro pipeline: {str(e)[:100]}"
                )
                guardar_estado(telefone, estado)
                logger.info(f"[{telefone}] Fallback de erro persistido com sucesso.")
            except Exception as fallback_err:
                logger.error(f"[{telefone}] Falha até no fallback de erro: {fallback_err}")

@strawberry.type
class Query:
    @strawberry.field
    def obter_historico(self, telefone: str) -> List[MensagemHistorico]:
        estado = obter_estado(telefone)
        if not estado:
            estado = EstadoConversa(session_id=telefone)
            guardar_estado(telefone, estado)
        return [
            MensagemHistorico(
                role=m.role, 
                content=m.content,
                confianca=m.confianca,
                motivo=m.motivo,
                model=m.model,
                route_score=m.route_score,
                sentiment=m.sentiment,
                sentiment_score=m.sentiment_score,
                latency_route=m.latency_route,
                probabilidades=m.probabilidades,
                log_guardrail=m.log_guardrail,
                log_roteamento=m.log_roteamento,
                log_rag=m.log_rag,
                log_geracao=m.log_geracao
            ) for m in estado.mensagens_recentes
        ]

    @strawberry.field
    def historico(self, sessionId: str) -> List[MensagemHistorico]:
        estado = obter_estado(sessionId)
        if not estado:
            estado = EstadoConversa(session_id=sessionId)
            guardar_estado(sessionId, estado)
        return [
            MensagemHistorico(
                role=m.role, 
                content=m.content,
                confianca=m.confianca,
                motivo=m.motivo,
                model=m.model,
                route_score=m.route_score,
                sentiment=m.sentiment,
                sentiment_score=m.sentiment_score,
                latency_route=m.latency_route,
                probabilidades=m.probabilidades,
                log_guardrail=m.log_guardrail,
                log_roteamento=m.log_roteamento,
                log_rag=m.log_rag,
                log_geracao=m.log_geracao
            ) for m in estado.mensagens_recentes
        ]

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def enviar_mensagem(self, telefone: Optional[str] = None, texto: Optional[str] = None, sessionId: Optional[str] = None, mensagem: Optional[str] = None) -> EnviarMensagemResponse:
        telefone_final = telefone or sessionId
        texto_final = texto or mensagem
        
        if not telefone_final or not texto_final:
            return EnviarMensagemResponse(status="erro", mensagem="Parâmetros de telefone/sessionId e texto/mensagem são obrigatórios.", aguarde=False)

        estado = obter_estado(telefone_final)
        if not estado:
            estado = EstadoConversa(session_id=telefone_final)
            
        agora = time.time()
        estado.buffer_pendente.append(texto_final.strip())
        estado.ultimo_timestamp = agora
        
        guardar_estado(telefone_final, estado)
        
        # Dispara o debounce em background
        asyncio.create_task(debounce_e_processar(telefone_final, agora))
        
        return EnviarMensagemResponse(status="sucesso", mensagem="Mensagem em buffer. Aguardando processamento (2s debounce).", aguarde=True)

schema = strawberry.Schema(query=Query, mutation=Mutation, extensions=[GraphQLDetailedLogging])
graphql_app = GraphQLRouter(schema)
