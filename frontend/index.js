const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const path = require('path');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 3000;
const API_URL = process.env.API_URL || 'http://localhost:8000';

app.use(cors());

// Servir arquivos estáticos (HTML e CSS) nativamente do diretório atual
app.use(express.static(__dirname));

// Proxy reverso para contornar qualquer problema de CORS e abstrair a API de backend
app.use(
  '/api',
  createProxyMiddleware({
    target: API_URL,
    changeOrigin: true,
    pathRewrite: {
      '^/api': '', // Remove /api da requisição encaminhada ao backend
    },
    onProxyRes: function (proxyRes, req, res) {
      proxyRes.headers['Access-Control-Allow-Origin'] = '*'; // Garante headers de CORS relaxados no dev
    }
  })
);

// Fallback para SPA / console principal
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

app.listen(PORT, () => {
  console.log(`[Z-ORACLE-FRONTEND] Servidor e Proxy rodando na porta ${PORT}`);
  console.log(`[Z-ORACLE-FRONTEND] Proxy apontando para API Backend: ${API_URL}`);
});
