# Relatório Técnico: Arquitetura Rebot

Este documento descreve as principais funcionalidades, ferramentas e tecnologias que compõem o sistema **Rebot**, um cofre de atendimento automatizado via webhook projetado para alta escalabilidade, segurança e baixa latência.

## 1. Funcionalidades Core

### Roteamento Inteligente e Determinístico
**O que faz:** Antes de acionar qualquer modelo de linguagem pesado, o sistema avalia a intenção da mensagem. Se for uma saudação simples ou uma operação determinística (como informar um CPF), o fluxo é resolvido localmente em milissegundos, evitando custos e atrasos. Apenas mensagens complexas ou dúvidas são enviadas para a IA.
**Tecnologias Envolvidas:** `NumPy` (cálculo vetorial acelerado por hardware), Matrizes estáticas para Fast Match, Regex.

### Motor Cognitivo e RAG Dinâmico
**O que faz:** Responde a dúvidas dos usuários buscando informações em bases de conhecimento atualizáveis em tempo real. Implementa *Semantic Chunking* (separação inteligente de textos por tags HTML) para garantir que respostas sobre temas diferentes não se misturem e causem alucinações ("Cérebro Dividido").
**Tecnologias Envolvidas:** Framework de Agentes (estruturação do fluxo RAG), Embeddings Semânticos para busca em banco vetorial, Processador HTML nativo.

### Prevenção e Bloqueio de Ataques (Guardrails)
**O que faz:** Atua como um firewall ativo contra *Prompt Injection* e engenharia social. O sistema não confia cegamente na entrada do usuário; ele intercepta tentativas de manipular o comportamento do bot ou descobrir suas instruções secretas.
**Tecnologias Envolvidas:** Modelos LLM ultrarrápidos configurados exclusivamente como juízes (LLM-as-a-judge), filtragem via Regex estruturada.

### Gestão Contínua de Sessão e Compressão de Conhecimento
**O que faz:** Mantém a "Rolling Memory" (memória contínua) do usuário ativa entre interações. Quando a conversa se alonga, o sistema gera compactações automáticas do contexto, evitando sobrecarga de tokens nas próximas requisições. 
**Tecnologias Envolvidas:** Mecanismos de banco de dados em memória (Cache rápido), Modelos de Sumarização Dedicados.

+10s pra buffer de mensagens inserir

### Anonimização de Dados e LGPD
**O que faz:** Ofusca e mascara proativamente dados sensíveis como CPFs e cartões de crédito já nos primeiros momentos, antes de enviá-los a qualquer LLM externo ou salvá-los nos logs, garantindo total adequação regulamentar.
**Tecnologias Envolvidas:** Expressões Regulares (Regex) com cobertura de padrões Brasileiros e de Cartões Internacionais, Validador matemático `validate-docbr`.

### Orquestração e Evasão de Latência de Webhooks
**O que faz:** Impede que os provedores de webhook (ex: APIs do WhatsApp) entrem em loop caso a geração de resposta demore. O sistema devolve o "OK" de recebimento de imediato para a plataforma e processa requisições lentas (bancos de dados, envios de logs) de forma assíncrona.
**Tecnologias Envolvidas:** Tarefas de Fundo (Background Tasks), Arquitetura Assíncrona e APIs com resposta desvinculada.

### Extensibilidade e Integração Futura de Ferramentas (Tool Calling)
**O que faz:** A arquitetura atual é construída sob um pipeline de "Function Calling", o que significa que o agente não apenas gera texto, mas pode executar funções em tempo real. Adicionar novas capacidades (como integrar com APIs de pagamento, checar saldos reais no banco de dados, gerar links dinâmicos de Checkout ou criar tickets no Zendesk/Jira) requer apenas a criação de uma nova Rota no *Semantic Router* e a definição de uma função Python assinada.
**Tecnologias Envolvidas:** Padrão "Agentic Workflow" do LlamaIndex e injeção dinâmica de dependências (closures), permitindo que o LLM entenda os parâmetros exigidos pela nova ferramenta e os preencha a partir do texto do próprio usuário, tudo em um ambiente rigorosamente tipado e seguro.

---

## 2. Tecnologias e Ferramentas Empregadas

* **LlamaIndex (AgentWorkflow & VectorStore):** Orquestra o raciocínio da inteligência artificial, criando restrições rígidas baseadas em ferramentas (Tools) e impedindo delírios fora do escopo.
* **LLM Google Gemini (Gemini 1.5 Flash & Gemini 2.5 Flash):** Modelos nativos do Google ofertando altíssima performance. O modelo 1.5 Flash atua como o juiz super-rápido do sistema de segurança (Guardrail) e sumarizador do Redis, enquanto o modelo 2.5 Flash opera como o cérebro conversacional principal do agente.
* **Sentence-Transformers & HuggingFace (all-MiniLM-L6-v2):** Usado localmente sem dependência de nuvem para transformar texto humano em vetores matemáticos para o Roteamento Semântico e para o RAG. Escudo contra oscilações de serviços terceiros.
* **FastAPI:** Gateway hiper performático e tipado para expor as regras de negócio via rotas RESTful para webhooks e integrações de frontend.
* **Redis:** O baluarte da arquitetura responsável pela preservação das sessões stateful entre as interações do WhatsApp/Webhook, permitindo resiliência até perante quebras de conexão. Implementado via Connection Poolings.
* **Pydantic:** Garantia matemática de que todo dado imputado, transmitido ou salvo pelo sistema respeita contratos estritos (ex: o banco não corrompe porque recebeu "ABC" num campo de CPF inteiro).
