import streamlit as st
import requests
import uuid
import time
import os
from dotenv import load_dotenv

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

load_dotenv()

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Agente IA V6", page_icon="🤖", layout="wide")

# ================================================================
# ESTADO DA SESSÃO
# ================================================================
if "session_id" not in st.session_state:
    st.session_state.session_id = None

if not st.session_state.session_id:
    st.title("🔐 Acesso - BetAgent IA")
    telefone_input = st.text_input("Digite seu Telefone ou /start para teste automático:", placeholder="+5511999999999")
    if st.button("Entrar", type="primary"):
        if telefone_input:
            if telefone_input.strip() == "/start":
                st.session_state.session_id = f"+55119{uuid.uuid4().hex[:7].upper()}"
            else:
                st.session_state.session_id = telefone_input.strip()
            st.rerun()
    st.stop()

# Controla msgs locais enviadas pelo usuário antes do backend confirmar
if "msgs_locais_pendentes" not in st.session_state:
    st.session_state.msgs_locais_pendentes = []

# Último histórico vindo do backend (fonte da verdade)
if "historico_confirmado" not in st.session_state:
    st.session_state.historico_confirmado = []

# ================================================================
# FETCH DO HISTÓRICO (fonte da verdade = backend)
# ================================================================
def fetch_historico():
    query = """
    query ($telefone: String!) {
      obterHistorico(telefone: $telefone) {
        papel
        conteudo
        confianca
        motivo
        model
        routeScore
        sentiment
        routeScore
        sentiment
        sentimentScore
        latencyRoute
        probabilidades
        logGuardrail
        logRoteamento
        logRag
        logGeracao
      }
    }
    """
    try:
        r = requests.post(
            f"{API_URL}/graphql",
            json={"query": query, "variables": {"telefone": st.session_state.session_id}},
            timeout=5
        )
        if r.status_code == 200:
            return r.json().get("data", {}).get("obterHistorico", [])
    except Exception:
        pass
    return []

def stream_resposta(texto: str):
    """Simula a digitação com pausas dinâmicas."""
    delay_inicial = min(len(texto) * 0.004, 2.0)
    time.sleep(delay_inicial)
    for word in texto.split(" "):
        yield word + " "
        time.sleep(0.035)

# ================================================================
# SIDEBAR
# ================================================================
with st.sidebar:
    st.header("🧠 Cérebro Analítico")
    st.write("Sessão:", st.session_state.session_id)
    
    st.divider()
    if st.button("🆕 Iniciar Novo Chat", use_container_width=True):
        st.session_state.clear()
        st.rerun()
        
    if st.button("🚪 Sair (Logout)", use_container_width=True):
        st.session_state.clear()
        st.rerun()
    st.divider()
    texto_conhecimento = st.text_area("Novo Conhecimento:", height=200)
    if st.button("Aprender Texto", type="primary"):
        with st.spinner("Ingerindo em tempo real..."):
            try:
                requests.post(f"{API_URL}/api/ingerir", json={"texto_conhecimento": texto_conhecimento})
                st.success("Adicionado à memória RAM!")
            except:
                st.error("Erro ao contactar a API.")

# ================================================================
# CABEÇALHO
# ================================================================
st.title("💬 BetAgent IA (Humanized ✨)")
st.caption("Debounce de 15s ativo — mensagens agrupadas antes de processar.")

# ================================================================
# BUSCA HISTÓRICO DO BACKEND E DETECTA NOVAS MSGS DO ASSISTENTE
# ================================================================
historico_api = fetch_historico()

# Atualiza as mensagens confirmadas pelo backend
# Ao detectar novas msgs de assistente, aplica o stream
novas_do_backend = historico_api[len(st.session_state.historico_confirmado):]

# ================================================================
# FUNÇÃO PARA RENDERIZAR EXPANSOR RICO
# ================================================================
def render_expander_logs(msg):
    # Se houver os novos logs ou p. fallback (confianca antiga)
    has_logs = msg.get("logGuardrail") or msg.get("logRoteamento") or msg.get("logRag") or msg.get("logGeracao") or msg.get("confianca")
    if not has_logs:
        return

    with st.expander("🔍 Metadados Analíticos (Debug)", expanded=False):
        import ast

        # 1. GUARDRAIL
        if msg.get("logGuardrail"):
            st.markdown("### 🛡️ 1. Guardrail & Sanitização")
            try:
                g_dict = json.loads(msg["logGuardrail"])
                st.json(g_dict)
            except:
                st.caption("Raw Guardrail: " + msg["logGuardrail"])

        # 2. ROTEAMENTO
        if msg.get("logRoteamento"):
            st.markdown("### 🚦 2. Roteamento & Cynefin")
            try:
                r_dict = json.loads(msg["logRoteamento"])
                st.json(r_dict)
            except:
                st.caption("Raw Roteamento: " + msg["logRoteamento"])

        # 3. BUSCA RAG
        if msg.get("logRag"):
            st.markdown("### 📚 3. Busca Vetorial (RAG)")
            try:
                rag_dict = json.loads(msg["logRag"])
                st.json(rag_dict)
            except:
                st.caption("Raw RAG: " + msg["logRag"])

        # 4. GERAÇÃO LLM
        if msg.get("logGeracao"):
            st.markdown("### 🧠 4. Geração via LLM")
            try:
                gen_dict = json.loads(msg["logGeracao"])
                st.json(gen_dict)
            except:
                st.caption("Raw Geração: " + msg["logGeracao"])
        elif msg.get("confianca"):
            # Fallback pra msg antiga
            st.markdown("### 🧠 4. Geração via LLM (Legado)")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Confiança", msg.get("confianca", "N/A"))
                st.metric("Sentimento", msg.get("sentiment", "N/A"))
            with col2:
                st.metric("Score Rota", f"{msg.get('routeScore', 0.0):.2f}" if type(msg.get('routeScore')) in (float, int) else "N/A")
                st.metric("Score Sent.", f"{msg.get('sentimentScore', 0.0):.2f}" if type(msg.get('sentimentScore')) in (float, int) else "N/A")
            with col3:
                st.metric("Latência Rota", f"{msg.get('latencyRoute', 0)}ms" if type(msg.get('latencyRoute')) in (float, int) else "N/A")
                st.caption(f"🤖 Modelo: {msg.get('model', 'N/A')}")
            st.info(f"**Motivo/Raciocínio:** {msg.get('motivo', 'Não informado')}")
            
            prob_str = msg.get("probabilidades", "")
            if prob_str:
                st.markdown("**📊 Probabilidades de Caminhos:**")
                try:
                    prob_dict = ast.literal_eval(prob_str) if isinstance(prob_str, str) else prob_str
                    for rota, pct in sorted(prob_dict.items(), key=lambda x: x[1], reverse=True):
                        st.progress(min(pct / 100.0, 1.0), text=f"{rota}: {pct}%")
                except:
                    st.caption(f"Raw: {prob_str}")


# ================================================================
# RENDERIZAÇÃO: histórico confirmado (sem stream — já mostrado antes)
# ================================================================
for msg in st.session_state.historico_confirmado:
    with st.chat_message(msg["papel"]):
        if msg["papel"] == "assistant" and ("transferência" in msg["conteudo"].lower() or "atendente" in msg["conteudo"].lower() or "ticket" in msg["conteudo"].lower()):
            st.warning("🔄 Você foi transferido para um Atendente Humano!")
            st.markdown(f"*{msg['conteudo']}*") # Mostra o detalhe discretamente embaixo
        else:
            st.markdown(msg["conteudo"])
            
        if msg["papel"] == "assistant":
            import json
            render_expander_logs(msg)

# ================================================================
# RENDERIZAÇÃO: mensagens locais pendentes (usuário enviou mas backend ainda processa)
# ================================================================
tem_msg_pendente = len(st.session_state.msgs_locais_pendentes) > 0

for msg_local in st.session_state.msgs_locais_pendentes:
    with st.chat_message("user"):
        st.markdown(msg_local)
    with st.chat_message("assistant", avatar="⏳"):
        st.markdown("*Aguardando o assistente IA...*")

if tem_msg_pendente and st_autorefresh:
    st_autorefresh(interval=3000, limit=None, key="polling_pendentes")

# ================================================================
# RENDERIZAÇÃO: novas mensagens vindas do backend (stream só na 1ª vez)
# ================================================================
for msg in novas_do_backend:
    if msg["papel"] == "assistant":
        with st.chat_message("assistant"):
            if "transferência" in msg["conteudo"].lower() or "atendente" in msg["conteudo"].lower() or "ticket" in msg["conteudo"].lower():
                st.warning("🔄 Você foi transferido para um Atendente Humano!")
                st.write_stream(stream_resposta(f"*{msg['conteudo']}*"))
            else:
                st.write_stream(stream_resposta(msg["conteudo"]))
                
            render_expander_logs(msg)
    else:
        with st.chat_message("user"):
            st.markdown(msg["conteudo"])
    st.session_state.historico_confirmado.append(msg)

# Ao confirmar msgs do backend, limpa pendentes que já chegaram
if novas_do_backend:
    st.session_state.msgs_locais_pendentes.clear()
    st.rerun()

# ================================================================
# INPUT DO USUÁRIO
# ================================================================
if prompt := st.chat_input("Você (Escreva algo...):"):
    # Adiciona localmente para mostrar imediato enquanto aguarda backend
    st.session_state.msgs_locais_pendentes.append(prompt)
    st.session_state.ultima_interacao_front = time.time()

    mutation = """
    mutation ($telefone: String!, $texto: String!) {
      enviarMensagem(telefone: $telefone, texto: $texto) {
        status
        mensagem
        aguarde
      }
    }
    """
    try:
        requests.post(
            f"{API_URL}/graphql",
            json={"query": mutation, "variables": {"telefone": st.session_state.session_id, "texto": prompt}},
            timeout=5
        )
    except Exception:
        st.error("Erro interno. O backend FastAPI está rodando?")

    st.rerun()

# ================================================================
# POLLING DE INATIVIDADE DO USUÁRIO (+60 SEG DEPOIS DO BOT FALAR)
# ================================================================
if "ultima_interacao_front" not in st.session_state:
    st.session_state.ultima_interacao_front = time.time()

# Se o histórico_confirmado acabar numa msg do assistente e demorar > 60s
if st.session_state.historico_confirmado and st.session_state.historico_confirmado[-1]["papel"] == "assistant":
    tempo_inativo = time.time() - st.session_state.ultima_interacao_front
    if tempo_inativo > 60:
        st.session_state.ultima_interacao_front = time.time() # Reseta para não loppar imediatamente
        # Dispara intenção silenciosa fingindo que o usuario abandonou
        msg_inativo = "[SISTEMA: O usuário está inativo/calado há mais de 1 minuto. Crie uma pequena frase gentil perguntando 'Ainda por aí? O que eu expliquei fez sentido?' para resgatá-lo à conversa.]"
        
        mutation_ina = """
        mutation ($telefone: String!, $texto: String!) {
          enviarMensagem(telefone: $telefone, texto: $texto) {
            status
            aguarde
          }
        }
        """
        try:
            requests.post(
                f"{API_URL}/graphql",
                json={"query": mutation_ina, "variables": {"telefone": st.session_state.session_id, "texto": msg_inativo}},
                timeout=5
            )
        except:
            pass
