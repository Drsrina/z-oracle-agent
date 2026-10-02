import re
import logging
import numpy as np
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger("betagent_router")

# ==========================================
# 1. DEFINIÇÃO ESTRITA DE ROTAS (Contrato de API)
# ==========================================
class Rota(str, Enum):
    """
    Define as 'estradas' possíveis do sistema.
    O main.py usa isto para decidir que ferramentas entregar ao LLM.
    """
    BATE_PAPO = "BATE_PAPO"           # Saudações, interações sem necessidade de base de dados
    COLETA_DADOS = "COLETA_DADOS"     # O utilizador está a enviar um CPF ou dado estruturado
    DUVIDA_TECNICA = "DUVIDA_TECNICA" # Aciona o RAG (LlamaIndex + Manual)
    PROBLEMA = "PROBLEMA"             # Reclamações, falhas (Prepara Handoff)
    ESCALAR = "ESCALAR"               # Pedido explícito para falar com humano
    TRANSACAO_FINANCEIRA = "TRANSACAO_FINANCEIRA" # Saques, Depósitos e verificação de status

class Sentimento(str, Enum):
    """
    Define os sentimentos possíveis para detecção semântica.
    """
    IRRITADO = "Irritado"
    SATISFEITO = "Satisfeito"
    NEUTRO = "Neutro"

# ==========================================
# 2. DATASET DE INTENÇÕES (Knowledge Base do Router)
# N-grams, gírias, erros de digitação e contexto regional (Brasil)
# ==========================================
ROUTE_EXAMPLES: Dict[Rota, List[str]] = {
    Rota.BATE_PAPO: [
        "oi", "olá", "bom dia", "boa tarde", "tudo bem", "obrigado",
        "valeu", "tchau", "até logo", "ok", "sim", "não", "entendi",
        "beleza", "show", "perfeito", "legal", "obrigada", "top",
        "opa", "e ai", "fala", "tranquilo", "suave", "podes crer",
        "blz", "kkk", "ahah", "joia", "maravilha", "como vc tá"
    ],
    Rota.DUVIDA_TECNICA: [
        "qual a regra de aposta múltipla", "como apostar em futebol", 
        "quais as odds mínimas", "pode explicar as regras",
        "como funciona o bônus", "o que é cashout", "regras de apostas ao vivo",
        "o que significa handicap", "rollover como funciona", "como usar freebet",
        "aposta anulada o que acontece", "empate anula aposta", "quem ganha",
        "qual o limite de aposta", "tem cotação mínima", "como faz pra jogar",
        "não entendi essa regra", "como calcula o prêmio", "aposta dupla"
    ],
    Rota.TRANSACAO_FINANCEIRA: [
        "como funciona o saque", "quero fazer um depósito", "novo saque",
        "como funciona o depósito", "depositar 50 reais", "fazer deposito",
        "quanto tempo demora o saque", "solicitar saque", "ver status do depósito",
        "meu saque caiu?", "quero depositar via pix", "sacar meu saldo",
        "pix não caiu", "tempo de compensação", "qual o valor minimo de saque",
        "limite de deposito", "sacar dinheiro", "receber meus ganhos",
        "bota dinheiro na conta", "tirar dinheiro", "pagamento pix", "recebimento"
    ],
    Rota.PROBLEMA: [
        "não consigo sacar", "minha conta está bloqueada", "como recriar senha",
        "deu erro no depósito", "não recebi meu dinheiro", "deu ruim aqui",
        "o site não funciona", "minha aposta sumiu", "site fora do ar",
        "fui cobrado errado", "problema com pagamento", "login falhando",
        "erro 404", "app travando", "não entra na conta", "senha invalida",
        "tento sacar e da erro", "dinheiro sumiu da conta", "aposta sumiu do historico"
    ],
    Rota.ESCALAR: [
        "quero falar com um humano", "me transfira para atendente",
        "preciso de um supervisor", "quero reclamar com alguém",
        "não quero falar com robô", "atendente humano", "falar com pessoa",
        "me passa pra alguém de verdade", "roboa chato", "chama uma pessoa aí",
        "ninguém resolve", "vou no procon", "falar com o suporte real",
        "pode chamar um consultor"
    ],
}

# ==========================================
# 2.5 DATASET DE SENTIMENTOS (Psiquê e Frustração)
# Captura de sarcasmo, passivo-agressividade e espectros emocionais
# ==========================================
SENTIMENT_EXAMPLES: Dict[Sentimento, List[str]] = {
    Sentimento.IRRITADO: [
        "merda", "lixo", "bosta", "caralho", "porra", "demora", "raiva",
        "já é a quinta vez que tento", "não funciona", "quero meu dinheiro logo",
        "tá de sacanagem", "que lentidão", "lixo de sistema", "roubo", "pessimo",
        "ridículo", "não resolve nada", "estou perdendo a paciência", "palhaçada",
        "vocês são uma piada", "é a pior casa de aposta", "resolvam isso logo",
        "ninguém aí presta", "tô cansado disso", "já mandei mensagem mil vezes",
        "parecem que estão brincando com meu dinheiro", "vou processar vocês",
        "incrível como nada funciona", "parabéns pela incompetência" # Sarcasmo
    ],
    Sentimento.SATISFEITO: [
        "obrigado", "valeu", "perfeito", "ajudou muito", "muito bom", "show",
        "agora sim", "deu certo", "muito obrigado", "excelente", "ótimo atendimento",
        "você foi top", "nota 10", "rápido e fácil", "vocês são os melhores",
        "finalmente consegui", "que alívio", "maravilha", "tudo certinho",
        "sensacional", "melhor robô", "gostei do atendimento"
    ],
    Sentimento.NEUTRO: [
        "ok", "entendi", "bom dia", "quero sacar", "como faz", "qual a regra",
        "certo", "tá bom", "sim", "não", "pode ser", "vou ver", "eu acho",
        "qual o prazo", "tem limite?", "me passa o link", "como acesso",
        "estou lendo", "aguardando", "feito", "enviado"
    ]
}

# ==========================================
# 3. GESTOR DO MODELO (Lazy Loading & Singleton Pattern)
# ==========================================
# O modelo só será carregado para a memória RAM na PRIMEIRA mensagem que precisar dele,
# garantindo que o tempo de 'boot' do seu servidor FastAPI seja de 0.1 segundos.
class RouterEngine:
    _instance = None
    _encoder = None
    _route_embeddings: Dict[Rota, np.ndarray] = {}
    _sentiment_embeddings: Dict[Sentimento, np.ndarray] = {}

    @classmethod
    def get_encoder(cls):
        """Implementa Lazy Loading seguro do SentenceTransformer."""
        if cls._encoder is None:
            logger.info("⏳ Inicializando SentenceTransformer (Cold Start do Router)...")
            from sentence_transformers import SentenceTransformer
            
            # Mantemos o modelo leve. Em produção gigantesca, isto poderia ser uma API (OpenAI text-embedding-3-small)
            cls._encoder = SentenceTransformer("all-MiniLM-L6-v2")
            cls._precomputar_embeddings()
            logger.info("✅ SentenceTransformer carregado e embeddings pré-computados!")
        return cls._encoder

    @classmethod
    def _precomputar_embeddings(cls):
        """Transforma o texto num array NumPy otimizado UMA ÚNICA VEZ."""
        for rota, exemplos in ROUTE_EXAMPLES.items():
            # normalize_embeddings=True permite usar Dot Product (muito mais rápido que Cosine Similarity clássico)
            vecs = cls._encoder.encode(exemplos, normalize_embeddings=True)
            cls._route_embeddings[rota] = vecs
            
        for sentimento, exemplos in SENTIMENT_EXAMPLES.items():
            vecs = cls._encoder.encode(exemplos, normalize_embeddings=True)
            cls._sentiment_embeddings[sentimento] = vecs

    @classmethod
    def get_route_embeddings(cls) -> Dict[Rota, np.ndarray]:
        if not cls._route_embeddings:
            cls.get_encoder() # Força a inicialização
        return cls._route_embeddings

    @classmethod
    def get_sentiment_embeddings(cls) -> Dict[Sentimento, np.ndarray]:
        if not cls._sentiment_embeddings:
            cls.get_encoder() # Força a inicialização
        return cls._sentiment_embeddings


# ==========================================
# 4. MOTOR DE CLASSIFICAÇÃO (A Mágica)
# ==========================================
def classificar_rota(texto: str, threshold: float = 0.45) -> dict:
    """
    A função principal chamada pelo main.py.
    Analisa o texto e decide qual a Rota arquitetural em milissegundos.
    Retorna um dicionário com os metadados de observabilidade.
    """
    import time
    start_t = time.perf_counter()
    texto_limpo = texto.lower().strip()
    
    # ---------------------------------------------------------
    # FASE 1: ROTEAMENTO DETERMINÍSTICO (Custo 0, Latência 0ms)
    # ---------------------------------------------------------
    # Se o texto for muito curto, não gastamos CPU com a IA.
    if not texto_limpo:
        lat = int((time.perf_counter() - start_t) * 1000)
        return {"route": Rota.BATE_PAPO, "route_score": 1.0, "latency": lat, "reason": "Texto Vazio"}
        
    # Atalhos absolutos baseados em RegEx (Expressões Regulares)
    # Se detetarmos um CPF, forçamos a rota de COLETA_DADOS imediatamente.
    # Isto resolve a falha da V4 onde o RAG tentava ler o CPF.
    if re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", texto_limpo):
        logger.debug(f"[Router] CPF detetado via Regex. Rota: {Rota.COLETA_DADOS}")
        lat = int((time.perf_counter() - start_t) * 1000)
        return {"route": Rota.COLETA_DADOS, "route_score": 1.0, "latency": lat, "reason": "Regex CPF"}
        
    # Atalho para saudações estritas
    if texto_limpo in ["oi", "ola", "olá", "sim", "nao", "não", "ok", "obrigado", "obrigada"]:
        logger.debug(f"[Router] Saudação detetada via Exact Match. Rota: {Rota.BATE_PAPO}")
        lat = int((time.perf_counter() - start_t) * 1000)
        return {"route": Rota.BATE_PAPO, "route_score": 1.0, "latency": lat, "reason": "Regex Saudação"}

    # ---------------------------------------------------------
    # FASE 2: ROTEAMENTO SEMÂNTICO VETORIAL
    # ---------------------------------------------------------
    try:
        encoder = RouterEngine.get_encoder()
        route_embeddings = RouterEngine.get_route_embeddings()
        
        # Vetoriza a frase do utilizador
        query_vec = encoder.encode([texto_limpo], normalize_embeddings=True)[0]
        
        melhor_rota = Rota.DUVIDA_TECNICA # Fallback seguro (deixa o LLM lidar se tudo falhar)
        melhor_score = threshold

        # Matemática Otimizada: Em vez de loops complexos em Python, 
        # usamos operações matriciais NumPy (Dot Product) C-compiled. É absurdo de rápido.
        for rota, vecs in route_embeddings.items():
            similarities = vecs @ query_vec
            max_sim = float(similarities.max())
            
            if max_sim > melhor_score:
                melhor_score = max_sim
                melhor_rota = rota

        lat = int((time.perf_counter() - start_t) * 1000)
        logger.debug(f"[Router] Vetor resolveu -> {melhor_rota.value} (Score: {melhor_score:.2f}) em {lat}ms")
        return {"route": melhor_rota, "route_score": melhor_score, "latency": lat, "reason": "Classificação Vetorial"}

    except Exception as e:
        # Se a biblioteca matemática rebentar por falta de memória ou erro bizarro,
        # NUNCA derrubamos o servidor. Entregamos a bomba para o LlamaIndex (DUVIDA_TECNICA) resolver.
        logger.error(f"🚨 Falha no Semantic Router Vetorial: {e}. Aplicando Fallback de Segurança.")
        lat = int((time.perf_counter() - start_t) * 1000)
        return {"route": Rota.DUVIDA_TECNICA, "route_score": 0.0, "latency": lat, "reason": "Fallback Error"}

# ==========================================
# 5. MOTOR DE SENTIMENTO
# ==========================================
def classificar_sentimento(texto: str, threshold: float = 0.45) -> dict:
    """
    Classifica de forma vetorial o sentimento do utilizador.
    Substitui as Regex rígidas de palavrões por compreensão semântica da frustração.
    """
    import time
    start_t = time.perf_counter()
    texto_limpo = texto.lower().strip()
    if not texto_limpo:
        return {"sentiment": Sentimento.NEUTRO.value, "sentiment_score": 1.0}
        
    try:
        encoder = RouterEngine.get_encoder()
        sentiment_embeddings = RouterEngine.get_sentiment_embeddings()
        
        query_vec = encoder.encode([texto_limpo], normalize_embeddings=True)[0]
        
        melhor_sentimento = Sentimento.NEUTRO
        melhor_score = threshold

        for sentimento, vecs in sentiment_embeddings.items():
            similarities = vecs @ query_vec
            max_sim = float(similarities.max())
            
            if max_sim > melhor_score:
                melhor_score = max_sim
                melhor_sentimento = sentimento

        result = melhor_sentimento.value if isinstance(melhor_sentimento, Sentimento) else melhor_sentimento
        logger.debug(f"[Router Sentimento] Resolveu -> {result} (Score: {melhor_score:.2f})")
        return {"sentiment": result, "sentiment_score": melhor_score}

    except Exception as e:
        logger.error(f"🚨 Falha no Sentimento Vetorial: {e}. Aplicando Fallback Neutro.")
        return {"sentiment": Sentimento.NEUTRO.value, "sentiment_score": 0.0}


# ==========================================
# 4. CLASSIFICAÇÃO CYNEFIN
# ==========================================
def classificar_cynefin(rota: str, sentimento: str, tentativas: int) -> str:
    """
    Classifica o domínio do problema segundo o framework Cynefin.
    Determina o threshold de confiança necessário para diagnóstico.
    
    - CLARO: causa-efeito óbvio (dúvida simples, bate-papo) → threshold 60%
    - COMPLICADO: requer análise (problema técnico, transação) → threshold 75%
    - COMPLEXO: múltiplas variáveis, frustração (3+ tentativas + irritado) → threshold 85%
    - CAOTICO: urgência extrema, escalar imediato → handoff direto
    """
    if sentimento == "Urgente" or rota == "ESCALAR":
        return "CAOTICO"
    if tentativas >= 3 and sentimento == "Irritado":
        return "COMPLEXO"
    if rota in ["PROBLEMA", "TRANSACAO_FINANCEIRA"]:
        return "COMPLICADO"
    if rota == "DUVIDA_TECNICA":
        return "COMPLICADO"
    return "CLARO"