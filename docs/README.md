# 📚 Hub de Documentação Técnica & Engenharia de IA — Z-Oracle Atendee

Bem-vindo à documentação técnica oficial do **Z-Oracle Atendee**. Este diretório reúne whitepapers, especificações de arquitetura, benchmarks empíricos e diretrizes de governança conversacional que fundamentam o projeto.

Este material foi estruturado para fornecer visibilidade profunda a **Engenheiros de IA, Arquitetos de Software, Tech Leads e Agentes de Recrutamento Técnico** interessados em avaliar rigor de código, design de sistemas resilientes e mitigação prática de alucinações em LLMs.

---

## 🧭 Mapa de Documentos

| Documento | Foco Principal | Público-Alvo | Resumo Executivo |
| :--- | :--- | :--- | :--- |
| **[`arquitetura.md`](./arquitetura.md)** | **Engenharia de Sistemas & Infraestrutura** | Arquitetos de Software, DevOps, Backend Leads | Detalhamento dos fluxos assíncronos, buffer de debounce em Redis (15s), persistência stateful, WAF semântico e matriz comparativa da stack (FastAPI, LlamaIndex, PostgreSQL/pgvector). |
| **[`roteadorsemantico.md`](./roteadorsemantico.md)** | **Benchmark & Inferência On-Premise** | Engenheiros de ML, Performance & MLOps | Prova empírica de triagem vetorial executada 100% em CPU local (`all-MiniLM-L6-v2` + produto escalar em C/NumPy) com latência medida de **6.35 ms** e **zero chamadas de nuvem**. |
| **[`diretrizes.md`](./diretrizes.md)** | **Governança Conversacional & Produto** | Product Managers, Tech Leads, QA & Compliance | Protocolos obrigatórios de investigação em 2 passos, retenção de foco anti-drift, conformidade com a LGPD (anonimização matemática de PII) e metas de CSAT/NPS. |
| **[`pesquisa.md`](./pesquisa.md)** | **Epistemologia & Oráculo de Resolução de Problemas** | AI Researchers, Cientistas Cognitivos, R&D | Tese técnica e conceitual sobre a transição de inferência probabilística para raciocínio de Primeiros Princípios, TRIZ-GPT, Matriz Cynefin, orquestração multiagente e GraphRAG. |

---

## 🏛️ Destaques de Engenharia para Avaliadores Técnicos

1. **Eficiência de Custos e Latência (Zero-Cloud Triage):**
   - Roteamento semântico local que elimina até 85% do custo desnecessário de chamadas de LLM em saudações e dados estruturados.
2. **Prevenção Real de "Cérebro Dividido" (Tool Scoping):**
   - Ferramentas de mutação de banco de dados ou RAG só são expostas ao modelo generativo mediante intenção estritamente classificada pela camada vetorial local.
3. **Resiliência a Mensagens Fragmentadas:**
   - Buffer inteligente de debounce distribuído no Redis que consolida rajadas de mensagens do WhatsApp antes da invocação do pipeline de IA.
4. **Governança e LGPD:**
   - Anonimização determinística de CPFs e cartões em memória antes de qualquer transmissão externa ou registro em logs relacionais.
