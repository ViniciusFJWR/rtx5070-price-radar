# RTX 5070 Price Radar — protótipo

Monitor experimental de placas **RTX 5070 12 GB padrão** em páginas individuais da Pichau e Terabyte, com alvo de **R$ 4.500** e alerta por Telegram.

**Status:** ainda é necessário configurar as credenciais Telegram e validar coleta em execuções reais. O GitHub Actions solicita execução a cada 5 minutos, mas pode atrasar ou ser suspenso; não equivale a detecção instantânea. Lojas podem bloquear requisições ou deixar de publicar dados estruturados. O protótipo não compara cupons, frete, preço PIX ou checkout automaticamente. Preços extraídos de JSON-LD podem não ser o menor preço mostrado na página, portanto confira antes de comprar.

## Ativar alertas (não publique tokens)

1. Abra [@BotFather](https://t.me/BotFather) no Telegram, use `/newbot` e guarde o token em segurança. Abra a conversa com o bot criado e pressione **Start**.
2. Para obter o **chat ID**, consulte `https://api.telegram.org/botSEU_TOKEN/getUpdates` no seu próprio navegador (substitua apenas localmente) depois de enviar uma mensagem ao bot. Procure `message.chat.id`. **Não compartilhe token nem link contendo token.**
3. No repositório GitHub, vá a **Settings → Secrets and variables → Actions → New repository secret** e crie `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`.
4. Abra **Actions → RTX 5070 Price Radar → Run workflow** para testar. Veja os logs. Uma mensagem só é enviada se houver preço estruturado confiável abaixo do limite; não é um teste de envio isolado.
5. Ative as notificações do Telegram no celular.

As URLs iniciais estão em `products.json`. Só URLs HTTPS das duas lojas cadastradas no código são aceitas. Novas lojas exigem adaptar e testar a extração. `state.json` guarda o último valor alertado por URL, para não repetir o mesmo preço; uma nova queda gera outro aviso. O workflow pode precisar de permissão **Read and write** em Settings → Actions → General → Workflow permissions para gravar o estado.

### Limitações

- O monitor não faz scraping agressivo e não tenta contornar bloqueios.
- O alerta depende de JSON-LD `Product` com `priceCurrency=BRL`, `availability=InStock` e preço numérico; se esses dados faltarem, não alerta.
- A oferta é um *indício* que requer confirmação no checkout.
- A execução em repositório público usa infraestrutura do GitHub; o GitHub pode limitar, atrasar ou suspender tarefas agendadas.
