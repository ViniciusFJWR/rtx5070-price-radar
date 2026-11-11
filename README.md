# RTX 5070 Price Radar v2.2 — atualização preparada

**Status: pacote local pronto, NÃO instalado automaticamente no repositório GitHub.** O conector GitHub permitiu leitura mas recusou escrita (403). Continue usando a versão 2.1 até substituir os arquivos.

## Melhoria no monitor

- 15 anúncios habilitados (8 existentes + 7 URLs de placas RTX 5070 12 GB da Terabyte verificadas em fontes públicas); 2 anúncios da Pichau continuam desabilitados porque retornaram 403.
- Normaliza o vendedor da KaBuM! para evitar incluir texto como "Compre este produto e ganhe BRINDE" no nome do vendedor. Sem identificação confiável de marketplace, não gera alerta.
- Confere que o produto JSON-LD corresponde ao título principal, reduzindo falsos alertas de produtos relacionados.
- Mantém preço-alvo de R$ 4.500, agendamento de cinco minutos (sujeito a atraso), filtragem de RTX 5070 Ti/usados/PCs, notificações Telegram e deduplicação por URL.
- **Não valida cupons, frete, promoções que só apareçam no aplicativo, nem checkout**. Fontes adicionais ainda não foram testadas no runner GitHub.
- Não realiza técnicas para contornar bloqueios 403, captcha ou restrições de acesso.

## Instalação quando possível

Este ZIP contém **somente os arquivos atualizados**, sem `state.json` e sem qualquer segredo. Substituir `radar.py`, `products.json`, `README.md` e `tests/test_radar.py` no repositório; o workflow atual e seus Secrets não precisam mudar.

Para testar: `python -m unittest discover -s tests -v`. Depois do upload, GitHub → Actions → RTX 5070 Price Radar → Run workflow → check → Check prices. Uma execução verde não significa que todas as fontes funcionam: confirme linhas `[PREÇO]`, `[SEM CONFIRMAÇÃO]`, `[BLOQUEIO/HTTP]` e `[RESUMO]`.

## Avisos

Ainda não é monitoramento de toda a loja; cada anúncio precisa ser listado em `products.json`. Preço de dados estruturados não necessariamente é preço PIX ou preço final. A execução agendada pode sofrer atrasos e não garante aviso imediato. Em caso de bloqueios, não utilize proxies/CAPTCHA para burlar as restrições.
