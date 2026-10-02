import os
import re
import json
import logging
from datetime import datetime
from typing import ClassVar, List, Dict, Optional, Any
from pydantic import BaseModel, Field, ValidationError

import redis
from validate_docbr import CPF
import google.generativeai as genai

# ==========================================
# CONFIGURAÇÃO E CONEXÃO REDIS (Connection Pooling)
# ==========================================
logger = logging.getLogger("betagent_redis")

# Usamos Connection Pool para não estourar as ligações ao Redis com muitos utilizadores
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
REDIS_TTL_SEGUNDOS = 86400  # 24 horas. Após 1 dia sem falar, a sessão do cliente expira.

_in_memory_db = {}

try:
    # Connection pool com TLS automático para URLs rediss:// (Upstash)
    # redis-py detecta o schema rediss:// e habilita SSL sozinho
    _pool = redis.ConnectionPool.from_url(
        REDIS_URL,
        max_connections=50,       # Aumentado de 20 para aguentar teste de carga
        socket_connect_timeout=3,
        socket_timeout=3,
        health_check_interval=30, # Desativa conexões mortas automaticamente
        decode_responses=True,
    )
    redis_db = redis.Redis(connection_pool=_pool)
    redis_db.ping()  # Valida conexão no boot — falha rápido se URL errada
    logger.info(f"✅ Redis conectado: {REDIS_URL.split('@')[-1]}")  # Loga host sem senha
except Exception as e:
    redis_db = None
    logger.warning(f"⚠️ Redis indisponível ({e}). Usando fallback in-memory (não use em produção).")


# ==========================================
# SCHEMAS DE ESTADO (Substitui o @dataclass frágil da V4)
# ==========================================
class MensagemChat(BaseModel):
    role: str
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # Metadados Analíticos (Novos campos Geração 6)
    confianca: Optional[str] = None
    motivo: Optional[str] = None
    model: Optional[str] = None
    route_score: Optional[float] = None
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    latency_route: Optional[int] = None
    probabilidades: Optional[str] = None  # JSON string com % de cada caminho decisório
    log_guardrail: Optional[str] = None
    log_roteamento: Optional[str] = None
    log_rag: Optional[str] = None
    log_geracao: Optional[str] = None

class EstadoConversa(BaseModel):
    """
    Modelo Pydantic que representa o estado exato da jornada de um utilizador.
    Altivamente tipado, impossível de guardar dados corrompidos.
    Alinhado com a spec TypeScript SessionState.
    """
    session_id: str
    cpf: Optional[str] = None
    intencao_confirmada: Optional[str] = None
    
    # Máquina de Estados Expandida
    # COLETA → ECO_PENDENTE → DIAGNOSTICO → AGUARDANDO_CONFIRMACAO → CONCLUIDO → ENCERRADO
    etapa: str = "COLETA"
    tentativas_resolucao: int = 0
    dados_coletados: Dict[str, Any] = Field(default_factory=dict)
    inicio: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # Memória Emocional e Human-in-the-Loop
    perfil_sentimental: str = "Neutro"
    dados_transacao_pendente: dict = Field(default_factory=dict)
    
    # Memória de Identidade (Nome do Cliente)
    nome_usuario: Optional[str] = None
    
    # Clarificação Inteligente (Funcionalidade #2)
    historico_intencoes: List[dict] = Field(default_factory=list)
    perguntas_clarificacao: int = 0
    
    # ========== NOVOS CAMPOS (Spec TypeScript) ==========
    
    # 2-Step Gate: rastreia % do caminho percorrido por rota
    question_path: Dict[str, Any] = Field(default_factory=lambda: {
        "required": [],      # campos obrigatórios para a rota atual
        "collected": [],     # campos já confirmados
        "coverage_percent": 0  # collected/required * 100
    })
    
    # Eco de Confirmação Bloqueante (genérica, não só transações)
    eco_buffer: Optional[str] = None       # resumo do problema a ser confirmado
    eco_confirmado: bool = False
    
    # Anti-Drift: ancora o problema original
    problema_original: Optional[str] = None
    turnos_sem_ancora: int = 0
    
    # Classificação Cynefin (domínio do problema)
    cynefin_domain: Optional[str] = None  # CLARO|COMPLICADO|COMPLEXO|CAOTICO
    
    # Régua de Confiança Progressiva (≠ LLM self-reported)
    confianca: int = 20                    # Começa SEMPRE em 20
    motivo_confianca: str = "Sessão iniciada"
    historico_confianca: List[int] = Field(default_factory=lambda: [20])
    
    # Gestão de Memória (Rolling Summary)
    resumo_acumulado: str = ""
    mensagens_recentes: List[MensagemChat] = Field(default_factory=lambda: [MensagemChat(role="assistant", content="Olá! Sou o assistente virtual da BetAgent. Como posso chamar você?")])
    MAX_MENSAGENS_RECENTES: int = Field(default=3, exclude=True)

    # Gestão de Buffer de Leitura (Debounce)
    buffer_pendente: List[str] = Field(default_factory=list)
    ultimo_timestamp: float = Field(default=0.0)
    ultima_interacao_usuario: float = Field(default_factory=lambda: datetime.now().timestamp())

    # Logs Analíticos da Interação Atual
    ultimo_log_guardrail: Optional[Dict[str, Any]] = None
    ultimo_log_roteamento: Optional[Dict[str, Any]] = None
    ultimo_log_rag: Optional[Dict[str, Any]] = None
    ultimo_log_geracao: Optional[Dict[str, Any]] = None

    def adicionar_mensagem(self, role: str, content: str, **kwargs):
        """Adiciona uma mensagem à janela deslizante de contexto com metadados opcionais."""
        self.mensagens_recentes.append(MensagemChat(role=role, content=content, **kwargs))
        # Incrementa contador anti-drift a cada turno
        self.turnos_sem_ancora += 1

    def registar_nome(self, nome: str):
        """Registra o nome do cliente de forma segura e persistente."""
        if nome and len(nome) >= 2:
            self.nome_usuario = nome
            self.dados_coletados["nome"] = nome
            self.marcar_campo_coletado("nome")
            logger.info(f"[{self.session_id}] Nome do cliente registrado: {nome}")

    def resetar_clarificacao(self):
        """Reseta o contador de perguntas clarificadoras após ação bem-sucedida."""
        self.perguntas_clarificacao = 0

    def marcar_campo_coletado(self, campo: str):
        """Marca um campo como coletado no question_path e recalcula cobertura."""
        if campo not in self.question_path["collected"]:
            self.question_path["collected"].append(campo)
        required = self.question_path.get("required", [])
        collected = self.question_path.get("collected", [])
        if required:
            matched = [c for c in collected if c in required]
            self.question_path["coverage_percent"] = round(
                (len(matched) / len(required)) * 100
            )
        self.recalcular_confianca()

    def iniciar_question_path(self, rota: str):
        """Inicializa os campos obrigatórios para uma rota específica."""
        ROTA_CAMPOS = {
            "DUVIDA_TECNICA": ["nome", "problema_descricao"],
            "TRANSACAO_FINANCEIRA": ["nome", "cpf", "tipo_transacao", "valor"],
            "PROBLEMA": ["nome", "problema_descricao", "tentativas_anteriores"],
            "COLETA_DADOS": ["nome", "cpf"],
            "BATE_PAPO": ["nome"],
            "ESCALAR": ["nome", "problema_descricao"],
        }
        campos = ROTA_CAMPOS.get(rota, ["nome"])
        # Preserva campos já coletados de rotas anteriores
        coletados_existentes = self.question_path.get("collected", [])
        self.question_path = {
            "required": campos,
            "collected": [c for c in coletados_existentes if c in campos],
            "coverage_percent": 0
        }
        # Recalcula imediatamente
        self.marcar_campo_coletado("__noop__")  # Trigger recalc sem adicionar
        self.question_path["collected"] = [c for c in self.question_path["collected"] if c != "__noop__"]

    def recalcular_confianca(self):
        """
        Régua Progressiva: confiança sobe por eventos verificáveis, não por intuição do LLM.
        Começa em 20 e sobe por ações concretas.
        """
        score = 20  # Base sempre baixa por design
        motivos = []

        # +10 por cada dado coletado e confirmado
        if self.nome_usuario:
            score += 10
            motivos.append("+10 nome")
        if self.cpf:
            score += 10
            motivos.append("+10 CPF")
        if self.problema_original:
            score += 5
            motivos.append("+5 problema_original")

        # +15 se o eco foi confirmado pelo usuário
        if self.eco_confirmado:
            score += 15
            motivos.append("+15 eco_confirmado")

        # +% proporcional ao caminho percorrido (2-step gate)
        coverage = self.question_path.get("coverage_percent", 0)
        gate_bonus = round((coverage / 100) * 30)
        if gate_bonus > 0:
            score += gate_bonus
            motivos.append(f"+{gate_bonus} cobertura({coverage}%)")

        # -10 se o sentimento é IRRITADO
        if self.perfil_sentimental == "Irritado":
            score -= 10
            motivos.append("-10 irritado")

        # -5 por tentativa de resolução falhada
        if self.tentativas_resolucao > 0:
            penalidade = self.tentativas_resolucao * 5
            score -= penalidade
            motivos.append(f"-{penalidade} tentativas({self.tentativas_resolucao})")

        self.confianca = max(10, min(100, score))
        self.motivo_confianca = " | ".join(motivos) if motivos else "Base 20"
        self.historico_confianca.append(self.confianca)
        # Limita histórico a 20 entradas
        if len(self.historico_confianca) > 20:
            self.historico_confianca = self.historico_confianca[-20:]

    # Threshold de diagnóstico por domínio Cynefin
    THRESHOLD_DIAGNOSTICO: ClassVar[Dict[str, int]] = {"CLARO": 60, "COMPLICADO": 75, "COMPLEXO": 85, "CAOTICO": 0}

    def pode_diagnosticar(self) -> bool:
        """
        GATE com threshold dinâmico por domínio Cynefin:
        CLARO=60%, COMPLICADO=75%, COMPLEXO=85%, CAÓTICO=handoff direto.
        """
        if self.cynefin_domain == "CAOTICO":
            return False  # Caótico vai direto para handoff, nunca diagnostica
        threshold = self.THRESHOLD_DIAGNOSTICO.get(self.cynefin_domain or "COMPLICADO", 75)
        return (
            self.eco_confirmado
            and self.question_path.get("coverage_percent", 0) >= 100
            and self.confianca >= threshold
        )

    def registar_problema_original(self, problema: str):
        """Registra o problema original para âncora anti-drift."""
        if not self.problema_original and problema and len(problema) > 10:
            self.problema_original = problema
            self.dados_coletados["problema_descricao"] = problema
            self.marcar_campo_coletado("problema_descricao")
            self.turnos_sem_ancora = 0
            logger.info(f"[{self.session_id}] Problema original ancorado: {problema[:50]}...")

    def precisa_sumarizar(self) -> bool:
        """Verifica se o limite da janela de contexto foi atingido."""
        return len(self.mensagens_recentes) > self.MAX_MENSAGENS_RECENTES

    def tentar_registar_cpf_da_mensagem(self, mensagem: str) -> bool:
        """
        Substitui o Fallback Silencioso da V4. 
        Se a lib validate_docbr não estiver presente, o sistema quebra em vez de aceitar lixo.
        """
        # Extrai apenas números
        cpf_numeros = re.sub(r"\D", "", mensagem)
        
        # Procura qualquer sequência de 11 dígitos
        matches = re.findall(r"\d{11}", cpf_numeros)
        if not matches:
            return False
            
        cpf_limpo = matches[0]
        
        # Validação Matemática Real (NÃO USAR FALLBACK AQUI EM PRODUÇÃO)
        validador = CPF()
        if validador.validate(cpf_limpo):
            self.cpf = cpf_limpo
            self.dados_coletados["cpf"] = cpf_limpo
            return True
            
        return False

    def executar_sumarizacao_llm(self):
        """
        Executado em Background Task (definido no main.py).
        Condensa mensagens antigas sem impactar a latência do utilizador.
        """
        if not self.precisa_sumarizar():
            return

        limite = int(self.MAX_MENSAGENS_RECENTES)
        msgs_antigas = self.mensagens_recentes[:-limite]  # type: ignore
        msgs_recentes = self.mensagens_recentes[-limite:]  # type: ignore

        texto_antigo = "\n".join([f"[{m.role.upper()}]: {m.content[:200]}" for m in msgs_antigas])
        contexto_anterior = f"Resumo anterior: {self.resumo_acumulado}\n\n" if self.resumo_acumulado else ""

        try:
            # Cliente isolado apenas para a sumarização (LLM rápido e barato)
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
            model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"temperature": 0.0, "max_output_tokens": 200})
            # Instrução reforçada: preservar nome e dados críticos na sumarização
            nome_instrucao = f"IMPORTANTE: O nome do cliente é '{self.nome_usuario}'. Preserve-o no resumo. " if self.nome_usuario else ""
            prompt_sumarizacao = (
                "Você é um engenheiro de dados resumindo logs de atendimento. "
                "Sintetize a conversa abaixo em NO MÁXIMO 3 frases objetivas. "
                f"{nome_instrucao}"
                "Foque na intenção do utilizador, problemas reportados e dados coletados (nome, CPF, valores). "
                "Responda APENAS com o resumo.\n\n"
                f"{contexto_anterior}Diálogo a resumir:\n{texto_antigo}"
            )
            
            resposta = model.generate_content(prompt_sumarizacao)
            novo_resumo = resposta.text.strip()
            self.resumo_acumulado = novo_resumo
            self.mensagens_recentes = msgs_recentes
            logger.info(f"[{self.session_id}] Sumarização concluída: {novo_resumo[:50]}...")
            
        except Exception as e:
            logger.error(f"[{self.session_id}] Falha ao sumarizar memória: {e}. Truncando à força para proteger token limit.")
            # Fallback programático defensivo: Mantém apenas as recentes para não estourar o limite de contexto
            self.mensagens_recentes = msgs_recentes


# ==========================================
# INTERFACE DE PERSISTÊNCIA (CRUD)
# ==========================================

def obter_estado(telefone: str) -> Optional[EstadoConversa]:
    """Busca o estado do cliente no Redis e reconstrói o modelo Pydantic."""
    try:
        if redis_db:
            dados_raw = redis_db.get(f"betagent:session:{telefone}")
        else:
            dados_raw = _in_memory_db.get(f"betagent:session:{telefone}")
            
        if not dados_raw:
            return None
            
        # Pydantic garante que a estrutura não foi corrompida entre deploys
        return EstadoConversa.model_validate_json(dados_raw)
        
    except ValidationError as e:
        logger.error(f"[{telefone}] Estado corrompido no BD. Resetando sessão. Detalhes: {e}")
        if redis_db:
            redis_db.delete(f"betagent:session:{telefone}") # Purga o lixo
        else:
            _in_memory_db.pop(f"betagent:session:{telefone}", None)
        return None
    except Exception as e:
        logger.error(f"[{telefone}] Erro de leitura no BD: {e}")
        # Retorna estado em memória vazio (graceful degradation)
        return EstadoConversa(**{"session_id": telefone})


def guardar_estado(telefone: str, estado: EstadoConversa) -> bool:
    """Serializa o modelo Pydantic e guarda no Redis (ou InMemory)."""
    try:
        # Serializa para JSON usando a sintaxe nativa do Pydantic v2
        json_estado = estado.model_dump_json()
        
        if redis_db:
            # SETEX (Set with Expiration) garante que a base não enche infinitamente
            redis_db.setex(
                name=f"betagent:session:{telefone}",
                time=REDIS_TTL_SEGUNDOS,
                value=json_estado
            )
        else:
            _in_memory_db[f"betagent:session:{telefone}"] = json_estado
            
        return True
    except Exception as e:
        logger.error(f"[{telefone}] Erro fatal ao guardar estado no BD: {e}")
        return False