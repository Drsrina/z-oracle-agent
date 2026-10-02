"""
Módulo de Clarificação Inteligente (Funcionalidade #2)
=====================================================
Responsável por:
1. Avaliar se a intenção do usuário está clara o suficiente para agir
2. Gerar perguntas clarificadoras quando o score de rota é ambíguo
3. Acumular intenções ao longo de turnos para construir confiança
4. Calcular probabilidades de caminhos decisórios em %
5. Extrair e preservar o nome do cliente da conversa
"""

import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("betagent_clarificador")

# ==========================================
# CONFIGURAÇÃO DE THRESHOLDS
# ==========================================
THRESHOLD_CONFIANCA_ALTA = 0.65   # Acima disso, age direto sem perguntar
THRESHOLD_CONFIANCA_MEDIA = 0.50  # Entre 0.50 e 0.65, pergunta 1 vez
MAX_PERGUNTAS_CLARIFICACAO = 2    # Máximo de perguntas antes de agir com melhor palpite

# ==========================================
# 1. CALCULADOR DE PROBABILIDADES (% por caminho)
# ==========================================
def calcular_probabilidades_caminhos(texto: str) -> Dict[str, float]:
    """
    Calcula a probabilidade (%) de cada rota para uma mensagem.
    Retorna um dicionário {rota: porcentagem} onde a soma = 100%.
    """
    from core.router import RouterEngine, ROUTE_EXAMPLES, Rota

    try:
        encoder = RouterEngine.get_encoder()
        route_embeddings = RouterEngine.get_route_embeddings()

        query_vec = encoder.encode([texto.lower().strip()], normalize_embeddings=True)[0]

        scores_brutos: Dict[str, float] = {}
        for rota, vecs in route_embeddings.items():
            similarities = vecs @ query_vec
            max_sim = float(similarities.max())
            # Clamp para evitar negativos (artefato matemático de dot-product)
            scores_brutos[rota.value] = max(max_sim, 0.0)

        # Normaliza para somar 100%
        soma_total = sum(scores_brutos.values())
        if soma_total == 0:
            # Distribui uniformemente se tudo for zero
            n = len(scores_brutos)
            return {k: round(100.0 / n, 1) for k in scores_brutos}

        probabilidades = {}
        for rota, score in scores_brutos.items():
            probabilidades[rota] = round((score / soma_total) * 100, 1)

        return probabilidades

    except Exception as e:
        logger.error(f"🚨 Falha ao calcular probabilidades: {e}")
        return {}


# ==========================================
# 2. MOTOR DE CLARIFICAÇÃO
# ==========================================
def avaliar_necessidade_clarificacao(
    route_score: float,
    rota_sugerida: str,
    probabilidades: Dict[str, float],
    perguntas_feitas: int,
    etapa_atual: str,
    turnos_conversa: int
) -> Tuple[bool, Optional[str]]:
    """
    Decide se o bot deve perguntar antes de agir.
    
    Retorna: (precisa_clarificar: bool, pergunta_sugerida: Optional[str])
    
    Lógica:
    - Score >= 0.65: age direto (confiança alta)
    - Score 0.50-0.65 e perguntas_feitas < MAX: pergunta 1 vez
    - Score < 0.50 e perguntas_feitas < MAX: pergunta (mais urgente)
    - perguntas_feitas >= MAX: age com melhor palpite (evita loop infinito)
    - Etapa AGUARDANDO_CONFIRMACAO: nunca interrompe confirmação transacional
    """
    # Nunca interrompe fluxo de confirmação de transação
    if etapa_atual == "AGUARDANDO_CONFIRMACAO":
        return False, None

    # Suprime clarificação mecânica no início da conversa para dar naturalidade
    if turnos_conversa <= 4:  # 1 do system prompt inicial + 3 do usuário/bot
        return False, None

    # Already asked enough questions — proceed with best guess
    if perguntas_feitas >= MAX_PERGUNTAS_CLARIFICACAO:
        logger.info(f"[Clarificador] Limite de {MAX_PERGUNTAS_CLARIFICACAO} perguntas atingido. Prosseguindo com melhor rota: {rota_sugerida}")
        return False, None

    # High confidence — go ahead
    if route_score >= THRESHOLD_CONFIANCA_ALTA:
        return False, None

    # Medium/low confidence — generate clarifying question
    pergunta = _gerar_pergunta_clarificadora(rota_sugerida, probabilidades, route_score)
    logger.info(f"[Clarificador] Score {route_score:.2f} < {THRESHOLD_CONFIANCA_ALTA}. Pergunta clarificadora gerada.")
    return True, pergunta


def _gerar_pergunta_clarificadora(
    rota_principal: str,
    probabilidades: Dict[str, float],
    score: float
) -> str:
    """
    Gera uma pergunta natural baseada nas rotas mais prováveis.
    Usa as top-2 rotas para formular uma pergunta que direcione o usuário.
    """
    # Ordena por probabilidade decrescente
    rotas_ordenadas = sorted(probabilidades.items(), key=lambda x: x[1], reverse=True)
    
    if len(rotas_ordenadas) < 2:
        return "Pode me explicar melhor o que você precisa? Assim consigo te ajudar da melhor forma! 😊"
    
    top1_rota, top1_pct = rotas_ordenadas[0]
    top2_rota, top2_pct = rotas_ordenadas[1]

    # Mapa de rotas para descrições amigáveis em português
    descricoes = {
        "BATE_PAPO": "conversar",
        "DUVIDA_TECNICA": "tirar uma dúvida sobre regras ou funcionamento",
        "TRANSACAO_FINANCEIRA": "fazer um depósito, saque ou verificar uma transação",
        "PROBLEMA": "resolver um problema técnico",
        "ESCALAR": "falar com um atendente humano",
        "COLETA_DADOS": "enviar seus dados cadastrais",
    }
    
    desc1 = descricoes.get(top1_rota, "ajudar")
    desc2 = descricoes.get(top2_rota, "outra coisa")

    # Em vez de retornar uma string fixa que vai pro usuário, retornamos uma INSTRUÇÃO DE SISTEMA invisível
    if abs(top1_pct - top2_pct) < 10:
        return (
            f"[INSTRUÇÃO DO SISTEMA: O utilizador fez uma pergunta ambígua. "
            f"O sistema está em dúvida se ele quer '{desc1}' ou '{desc2}'. "
            f"Como o assistente, crie uma resposta hiper natural, curta e gentil pedindo para ele "
            f"clarificar para que lado deseja seguir. Não use linguagem robótica. Pareça humano ajudando.]"
        )
    
    # Se há uma líder clara mas sem confiança total, confirma
    return (
        f"[INSTRUÇÃO DO SISTEMA: O sistema calculou que o cliente provavelmente quer '{desc1}', "
        f"mas a confiança não é 100%. Gere uma frase curta e super amigável perguntando se "
        f"é isso mesmo que ele quer fazer. Ex: 'Se entendi certo, você quer fazer X, certo?']"
    )


# ==========================================
# 3. ACUMULADOR DE INTENÇÕES
# ==========================================
def acumular_intencao(
    historico_intencoes: List[dict],
    rota_info: dict,
    probabilidades: Dict[str, float]
) -> List[dict]:
    """
    Adiciona a classificação do turno atual ao histórico de intenções.
    Limita a 5 turnos para não crescer infinitamente.
    """
    novo_registro = {
        "rota": rota_info.get("route", "DESCONHECIDO"),
        "score": rota_info.get("route_score", 0.0),
        "reason": rota_info.get("reason", ""),
        "probabilidades": probabilidades
    }
    
    # Converte enum para string se necessário
    if hasattr(novo_registro["rota"], "value"):
        novo_registro["rota"] = novo_registro["rota"].value
    
    historico_intencoes.append(novo_registro)
    
    # Mantém apenas os últimos 5 registros
    if len(historico_intencoes) > 5:
        historico_intencoes = historico_intencoes[-5:]
    
    return historico_intencoes


def calcular_intencao_acumulada(historico_intencoes: List[dict]) -> Optional[str]:
    """
    Analisa o histórico de intenções para determinar a rota dominante.
    Se a mesma rota aparece em 2+ turnos consecutivos, retorna essa rota.
    Útil quando scores individuais são baixos mas a direção é consistente.
    """
    if len(historico_intencoes) < 2:
        return None
    
    # Conta frequência das rotas nos últimos turnos
    contagem: Dict[str, int] = {}
    for registro in historico_intencoes[-3:]:  # Últimos 3 turnos
        rota = registro.get("rota", "")
        if rota and rota != "BATE_PAPO":  # Ignora bate-papo na acumulação
            contagem[rota] = contagem.get(rota, 0) + 1
    
    if not contagem:
        return None
    
    # Se alguma rota aparece 2+ vezes, é a intenção dominante
    rota_dominante = max(contagem, key=contagem.get)
    if contagem[rota_dominante] >= 2:
        logger.info(f"[Clarificador] Intenção acumulada detectada: {rota_dominante} ({contagem[rota_dominante]} turnos)")
        return rota_dominante
    
    return None


# ==========================================
# 4. EXTRATOR DE NOME DO CLIENTE
# ==========================================
def extrair_nome(texto: str) -> Optional[str]:
    """
    Extrai o nome do cliente de frases comuns em português brasileiro.
    Padrões capturados:
    - "meu nome é João"
    - "pode me chamar de Maria"
    - "sou o Pedro" / "sou a Ana"
    - "eu sou Lucas"
    - "me chamo Rafael"
    - "aqui é o Bruno"
    - Resposta direta a "Como posso chamar você?": "João" (palavra única capitalizada)
    """
    texto_limpo = texto.strip()
    
    # Padrões explícitos de apresentação
    padroes = [
        r"(?:meu nome (?:é|e)|me chamo)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)?)",
        r"(?:pode me chamar de|me chama de|chama de)\s+([A-ZÀ-Ú][a-zà-ú]+)",
        r"(?:sou (?:o|a)|eu sou (?:o|a)?)\s*([A-ZÀ-Ú][a-zà-ú]+)",
        r"(?:aqui (?:é|e) (?:o|a))\s+([A-ZÀ-Ú][a-zà-ú]+)",
    ]
    
    for padrao in padroes:
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match:
            nome = match.group(1).strip().title()
            logger.info(f"[Clarificador] Nome extraído via padrão: '{nome}'")
            return nome
    
    # Heurística: se a mensagem é curta (1-2 palavras) e começa com maiúscula,
    # provavelmente é uma resposta direta à pergunta "Como posso chamar você?"
    palavras = texto_limpo.split()
    if len(palavras) <= 2 and texto_limpo[0].isupper():
        # Verifica se não é uma saudação ou comando comum
        saudacoes = {"oi", "olá", "ola", "bom", "boa", "sim", "não", "nao", "ok", "obrigado", "obrigada", "valeu"}
        if palavras[0].lower() not in saudacoes:
            nome = texto_limpo.title()
            logger.info(f"[Clarificador] Nome extraído via heurística (resposta curta): '{nome}'")
            return nome
    
    return None


# ==========================================
# 5. ECO DE CONFIRMAÇÃO BLOQUEANTE
# ==========================================
def gerar_eco(nome_usuario: Optional[str], problema: str) -> str:
    """
    Gera o eco de confirmação antes de qualquer diagnóstico.
    O bot resume o problema e pede confirmação ao usuário.
    """
    nome = nome_usuario or "você"
    return (
        f"Só pra garantir que entendi corretamente, {nome}: "
        f"\"{problema}\" — é isso mesmo? "
        f"Pode falar sem problemas se eu errei algo."
    )


def processar_resposta_eco(resposta: str) -> bool:
    """
    Verifica se o usuário confirmou o eco.
    Retorna True se confirmou, False se corrigiu/negou.
    """
    resposta_lower = resposta.lower().strip()
    confirmacoes = [
        "sim", "isso", "exato", "correto", "isso mesmo", "é isso",
        "isso aí", "isso ai", "exatamente", "pode ser", "tá certo",
        "ta certo", "positivo", "afirmativo", "confirm", "yes",
        "é sim", "e sim", "certinho", "perfeito", "show"
    ]
    return any(c in resposta_lower for c in confirmacoes)


# ==========================================
# 6. ANTI-DRIFT: ÂNCORA DE PROBLEMA
# ==========================================
def construir_ancora_anti_drift(problema_original: Optional[str], turnos_sem_ancora: int) -> Optional[str]:
    """
    Se o problema original existe e já passaram 4+ turnos sem re-injeção,
    retorna o bloco de âncora para injetar no system prompt.
    """
    if not problema_original:
        return None
    
    if turnos_sem_ancora >= 4:
        logger.info(f"[Anti-Drift] Re-injetando âncora após {turnos_sem_ancora} turnos")
        return (
            f"\n[ÂNCORA DE CONTEXTO — CRÍTICO]\n"
            f"O problema ORIGINAL do usuário é: \"{problema_original}\".\n"
            f"Você DEVE retornar a este contexto. Não desvie para outros assuntos.\n"
            f"Sua única missão é resolver ou diagnosticar este problema específico.\n"
        )
    
    return None


# ==========================================
# 7. 2-STEP GATE: VERIFICAÇÃO DE COBERTURA
# ==========================================
def verificar_gate_diagnostico(
    eco_confirmado: bool,
    coverage_percent: int,
    confianca: int
) -> Tuple[bool, str]:
    """
    Verifica se o bot pode emitir um diagnóstico/resolução.
    Retorna (pode_diagnosticar, motivo).
    """
    if not eco_confirmado:
        return False, "Eco não confirmado — resuma o problema e aguarde confirmação"
    
    if coverage_percent < 100:
        return False, f"Cobertura de campos em {coverage_percent}% — colete os campos faltantes"
    
    if confianca < 70:
        return False, f"Confiança em {confianca}% — abaixo do threshold de 70% para diagnóstico"
    
    return True, "Gate aprovado — pode diagnosticar"


# ==========================================
# 8. EXTRATOR DE VEREDICTO EXPANDIDO
# ==========================================
def extrair_veredicto_expandido(raw_text: str) -> Tuple[str, Optional[dict]]:
    """
    Extrai o veredicto expandido do LLM com campos:
    - confianca (int 0-100)
    - delta_confianca (int)
    - campos_coletados (list[str])
    - eco_status (PENDENTE|CONFIRMADO|NAO_INICIADO)
    - drift_detectado (bool)
    - motivo (str)
    
    Retorna: (texto_limpo, veredicto_dict ou None)
    """
    # Tenta encontrar o bloco [VEREDICTO]...[/VEREDICTO] se existir
    match_bloco = re.search(r"\[VEREDICTO\](.*?)\[/VEREDICTO\]", raw_text, re.DOTALL)
    if match_bloco:
        json_str = match_bloco.group(1).strip()
        json_str = re.sub(r"```json\s*", "", json_str)
        json_str = re.sub(r"```\s*", "", json_str)
        texto_limpo = re.sub(r"\[VEREDICTO\].*?\[/VEREDICTO\]", "", raw_text, flags=re.DOTALL).strip()
    else:
        # Fallback: procura JSON inline com campo "confianca"
        match_json = re.search(r'\{[\s\S]*?"confianca"[\s\S]*?"motivo"[\s\S]*?\}', raw_text)
        if not match_json:
            return raw_text.strip(), None
        json_str = match_json.group(0)
        texto_limpo = raw_text.replace(json_str, "").strip()
    
    try:
        import json
        veredicto = json.loads(json_str)
        
        # Normaliza campos para o formato esperado
        resultado = {
            "confianca": veredicto.get("confianca", 20),
            "delta_confianca": veredicto.get("delta_confianca", 0),
            "campos_coletados": veredicto.get("campos_coletados", []),
            "eco_status": veredicto.get("eco_status", "NAO_INICIADO"),
            "drift_detectado": veredicto.get("drift_detectado", False),
            "motivo": veredicto.get("motivo", "Sem motivo informado")
        }
        
        # Converte confianca string "85%" para int 85
        if isinstance(resultado["confianca"], str):
            resultado["confianca"] = int(re.sub(r'[^0-9]', '', resultado["confianca"]) or "20")
        
        logger.debug(f"[Veredicto] Extraído: confianca={resultado['confianca']}%, "
                     f"campos={resultado['campos_coletados']}, eco={resultado['eco_status']}")
        
        return texto_limpo, resultado
        
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"[Veredicto] Falha ao decodificar JSON: {e}")
        return raw_text.strip(), None

