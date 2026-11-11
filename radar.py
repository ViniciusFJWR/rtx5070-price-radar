"""Alertas conservadores a partir de dados estruturados das páginas cadastradas."""
import json
import os
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / 'state.json'
LIMIT = Decimal(os.getenv('PRICE_LIMIT_BRL', '4500'))
EXCLUDE = re.compile(r'5070\s*(?:ti|super)|notebook|laptop|pc\s*(?:gamer|completo)|usad[ao]|recondicionad[ao]|open[ -]?box', re.I)


def price_decimal(value):
    if value is None:
        return None
    s = re.sub(r'[^0-9.,]', '', str(value))
    if not s:
        return None
    if '.' in s and ',' in s:
        s = s.replace('.', '').replace(',', '.') if s.rfind(',') > s.rfind('.') else s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        p = Decimal(s)
        return p if p > 0 else None
    except InvalidOperation:
        return None


def walk(value):
    if isinstance(value, list):
        for v in value:
            yield from walk(v)
    elif isinstance(value, dict):
        yield value
        for v in value.values():
            if isinstance(v, (dict, list)):
                yield from walk(v)


def read_offer(product):
    url = product['url']
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'www.pichau.com.br', 'www.terabyteshop.com.br'}:
        raise ValueError('Domínio não autorizado')
    response = requests.get(url, timeout=20, headers={'User-Agent': 'Mozilla/5.0 (compatible; PriceRadar/1.0)'})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    candidates = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            source = json.loads(script.string or script.get_text())
        except (ValueError, TypeError):
            continue
        for node in walk(source):
            types = node.get('@type', [])
            if isinstance(types, str):
                types = [types]
            if not isinstance(types, list) or not any(str(t).split('/')[-1] == 'Product' for t in types):
                continue
            name = str(node.get('name', ''))
            if not re.search(r'\bRTX\s*5070\b', name, re.I) or not re.search(r'\b12\s*GB\b', name, re.I) or EXCLUDE.search(name):
                continue
            offers = node.get('offers', [])
            if isinstance(offers, dict):
                offers = [offers]
            for offer in offers:
                if not isinstance(offer, dict):
                    continue
                if str(offer.get('priceCurrency', '')).upper() != 'BRL':
                    continue
                if not str(offer.get('availability', '')).endswith('InStock'):
                    continue
                p = price_decimal(offer.get('price'))
                if p is not None:
                    candidates.append({'name': name, 'price': p, 'url': url})
    return min(candidates, key=lambda d: d['price']) if candidates else None


def notify(msg):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        print('Credenciais Telegram ausentes: nenhum alerta enviado.')
        return False
    r = requests.post(f'https://api.telegram.org/bot{token}/sendMessage', json={
        'chat_id': chat_id, 'text': msg, 'disable_web_page_preview': True
    }, timeout=20)
    r.raise_for_status()
    if not r.json().get('ok'):
        raise RuntimeError('Telegram não confirmou envio')
    return True


def main():
    data = json.loads((ROOT / 'products.json').read_text(encoding='utf-8'))
    old = json.loads(STATE_PATH.read_text(encoding='utf-8')) if STATE_PATH.exists() else {}
    state = dict(old)
    for product in data['products']:
        if not product.get('enabled', False):
            continue
        try:
            o = read_offer(product)
            if not o:
                print(f'{product["store"]}: sem preço verificável em JSON-LD')
                continue
            amount = o['price']
            print(f'{product["store"]}: preço estruturado R$ {amount:.2f}')
            last = price_decimal(old.get(o['url']))
            if amount >= LIMIT or (last is not None and amount >= last):
                continue
            msg = (f'🚨 RTX 5070 12 GB abaixo de R$ {LIMIT:.2f}!\n'
                   f'Loja: {product["store"]}\nProduto: {o["name"]}\n'
                   f'Preço estruturado anunciado: R$ {amount:.2f}\nLink: {o["url"]}\n'
                   'Confira o preço PIX, estoque, vendedor, cupons, frete e valor final no checkout.\n'
                   f'Consulta em {datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")} UTC')
            if notify(msg):
                state[o['url']] = str(amount)
        except (requests.RequestException, ValueError, KeyError, RuntimeError) as exc:
            print(f'Erro em {product.get("store", "?")}: {exc}', file=sys.stderr)
    if state != old:
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('Novo estado salvo')


if __name__ == '__main__':
    main()
