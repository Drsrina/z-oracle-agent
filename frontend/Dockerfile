FROM node:18-alpine

WORKDIR /app

# Instalar dependências
COPY package.json ./
RUN npm install --omit=dev

# Copiar arquivos da aplicação
COPY index.js index.html style.css ./

EXPOSE 3000

ENV PORT=3000
ENV API_URL=http://api:8000

CMD ["node", "index.js"]
