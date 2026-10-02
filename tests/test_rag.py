import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# Configura o path raiz
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(".env")

from infrastructure.redis_client import EstadoConversa
from core.agent import processar_mensagem_llm

# Exibir logs do terminal
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

async def main():
    estado = EstadoConversa(session_id="+5500000000055")
    perguntas = [
        "Quais são as regras completas para cancelar uma aposta na plataforma?",
        "Qual o limite mínimo para depósito via PIX na BetAgent?",
        "Como funciona o bônus de boas vindas, tem algum rollover para o saque?",
        "Posso sacar usando chave PIX CPF da minha esposa no meu login?",
        "Existe devolução do meu dinheiro caso o jogo de futebol empate e anule?"
    ]
    
    print("Iniciando bateria de 5 testes consecutivos ativando a tool de RAG...")
    
    for i, p in enumerate(perguntas, 1):
        print(f"\n[{i}/5] Enviando pergunta: {p}")
        # Passaremos apenas a tool_consultar_manual para forçar o AI a usá-la se possível,
        # O agente agora recebe o escopo via ferramentas_permitidas baseado no Router no main, mas como aqui é teste unitário do agente:
        resposta, tools, confianca, motivo, modelo = await processar_mensagem_llm(
            estado=estado, 
            mensagem=p,
            ferramentas_permitidas=["consultar_manual"]
        )
        print("  -> LLM RESPONDEU:", resposta[:100], "...")
        print("  -> TOOLS USADAS:", tools)
        
if __name__ == "__main__":
    asyncio.run(main())
