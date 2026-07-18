---
title: Mikrotik Live Monitor
emoji: 📊
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 5001
pinned: false
---

# MikroTik Live Monitor

Este espaço contém o dashboard de monitoramento de SLA e telemetria do roteador MikroTik, rodando sob Docker no Hugging Face Spaces de forma 100% gratuita.

## Implantação e Execução

O container do Docker é configurado e exposto automaticamente através da porta `5001`. 
O banco de dados SQLite (`telemetry.db`) é inicializado automaticamente no diretório do aplicativo.

> **Importante:** Por se tratar de um ambiente gratuito do Hugging Face Spaces sem volumes persistentes configurados, o banco de dados SQLite (`telemetry.db`) será redefinido ao estado inicial sempre que o contêiner for recriado ou reiniciar por inatividade.
