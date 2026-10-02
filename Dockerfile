FROM python:3.11-slim

# Impede o Python de escrever ficheiros .pyc e força o log a sair no terminal em tempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependências do sistema necessárias para compilar bibliotecas matemáticas
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 🔥 O SEGREDO DO COLD START:
# Descarrega o modelo do Semantic Router diretamente para dentro da imagem Docker.
# Assim, o seu servidor na nuvem não precisa de descarregar 100MB cada vez que reiniciar.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copia todo o código do projeto para o contentor
COPY . .

# Expõe a porta que o FastAPI vai usar
EXPOSE 8000

# HEALTHCHECK: permite ao Cloud Run detectar instâncias travadas e reiniciá-las
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Comando para iniciar o servidor em modo de produção com múltiplos workers
# --workers 2: aproveita multiprocessing em containers com 2+ CPUs
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]