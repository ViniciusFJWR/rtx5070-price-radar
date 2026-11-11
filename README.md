# RTX 5070 Price Radar — versão 2.1 (experimental)

Monitoramento de **RTX 5070 12 GB padrão** e notificações no Telegram para valores confirmados abaixo de **R$ 4.500**.

## Estado e cobertura

- O workflow solicita execução a cada 5 minutos. GitHub Actions pode atrasar ou suspender jobs agendados; **não é alerta instantâneo**.
- `products.json` lista **8 páginas ativas** em Terabyte, KaBuM!, Magalu, Amazon BR, Hardstore e Patoloco. Estas fontes são **experimentais** e precisam de validação nos logs do GitHub Actions. Não equivale a pesquisar todo o catálogo dessas lojas.
- Pichau foi desativada por 403 nas execuções anteriores. Mercado Livre, GK Infostore, Guerra Digital, WAZ, Carrefour, Inpower e outras lojas **ainda não têm fontes de coleta confiáveis implementadas**.
- Consulta dados estruturados JSON-LD `Product` com `Offer`, moeda BRL e disponibilidade `InStock`, identifica vendedor quando informado, recusa produto usado/RTX 5070 Ti e descarta informação insuficiente.
- Quando há indicação inequívoca de preço PIX próximo ao preço do produto, usa essa informação se consistente com o preço estruturado; senão registra o preço estruturado, sem presumir desconto. **Não valida cupons, frete ou checkout.**
- Cada alerta inclui preço, vendedor declarado na página, modalidade de preço e link. **Confirme tudo no checkout antes de comprar.**
- `state.json` evita repetir o mesmo preço; preços menores que o último alerta geram novo aviso. Histórico persiste por commit automático; se `git push` falhar, o estado pode não persistir.
- Erros HTTP, bloqueios 403, ausência de estoque ou falta de JSON-LD confiável são mostrados nos logs. **Job verde não significa que todos os sites funcionaram.**

## Configuração

1. GitHub → Settings → Secrets and variables → Actions: definir `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` (sem colocar valores nos arquivos públicos).
2. GitHub → Actions → RTX 5070 Price Radar → Run workflow.
3. Abrir job `check` e etapa `Check prices`. Observar `[PREÇO]`, `[SEM CONFIRMAÇÃO]`, `[BLOQUEIO/HTTP]` e `[RESUMO]`.
4. Ativar notificações do Telegram no celular. O workflow de teste `test-telegram.yml` permite testar a entrega separadamente.
5. GitHub → Settings → Actions → General → Workflow permissions → Read and write, se o commit de `state.json` falhar.

Para executar testes locais sem acesso à internet: `python -m unittest discover -s tests -v`.

## Custos e uso responsável

Repositórios públicos podem usar runners padrão do GitHub Actions gratuitamente, respeitando políticas de uso e limites do serviço. Uma execução a cada 5 minutos requer até 288 execuções/dia, sem garantia de início pontual. O monitor não tenta vencer bloqueios, captcha nem restrições técnicas. Se a fonte bloquear acesso automatizado, ela deixa de ser uma fonte válida até existir uma alternativa autorizada.

## Patoloco (incluída na v2.1)

- São acompanhadas duas páginas individuais de RTX 5070 12 GB padrão: Galax 1-Click OC e INNO3D Twin X2 OC.
- A extração na Patoloco exige título de GPU correspondente, botão de compra, disponibilidade não marcada como indisponível e **um preço à vista no PIX explícito na seção de compra**. A oferta não é enviada sem essas confirmações.
- Páginas oficiais consultadas na preparação: https://patoloco.com.br/placa-de-video-galax-geforce-rtx-5070-1-click-oc-12gb-gddr7-192-bit-dlss4-57non7mdbroc e https://patoloco.com.br/placa-de-video-inno3d-nvidia-geforce-rtx-5070-twin-x2-oc-12gb-gddr7-dlss-ray-tracing-n50702-12d7x-195064n.
- O cupom `LOCO` de 1% é anunciado no site, mas **não é automaticamente aplicado ou validado no checkout**.
- A extração precisa ser validada nos logs do GitHub Actions; páginas podem mudar, ou a loja pode recusar requisições da nuvem.
