"""Monitor conservador de preços da RTX 5070, com alertas por Telegram.

Não contorna bloqueios nem infere preços de páginas sem dados verificáveis.
"""
from __future__ import annotations

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
STATE_PATH = ROOT / "state.json"
LIMIT = Decimal(os.getenv("PRICE_LIMIT_BRL", "4500"))
ALLOWED_HOSTS = {
    "www.pichau.com.br", "www.terabyteshop.com.br", "www.kabum.com.br",
    "www.amazon.com.br", "www.magazineluiza.com.br", "hardstore.com.br",
    "patoloco.com.br", "www.patoloco.com.br",
}
EXCLUDE = re.compile(
    r"5070\s*(?:ti|super)\b|notebook|laptop|desktop\s+completo|"
    r"\bpc\s*(?:gamer|completo)\b|\busad[ao]\b|\brecondicionad[ao]\b|"
    r"\bopen[ -]?box\b|\brefurbished\b", re.I
)
GPU = re.compile(r"\b(?:RTX|GeForce\s+RTX)\s*5070\b", re.I)
MEMORY = re.compile(r"\b12\s*GB\b", re.I)
MONEY = r"R\$\s*([\d.,]+)"
PIX = re.compile(rf"{MONEY}\s*(?:à\s*vista\s*)?(?:no\s*)?pix\b|{MONEY}\s*à\s*vista\s*no\s*pix\b", re.I)


def price_decimal(raw):
    """Decimal BRL from currency strings or schema.org numeric prices."""
    if raw is None or isinstance(raw, bool):
        return None
    text = str(raw).strip()
    if not re.fullmatch(r"[\d\s.,R$]+", text):
        return None
    s = re.sub(r"[^\d.,]", "", text)
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif "." in s and len(s.split(".")[-1]) == 3:
        # Ex.: 4.399: milhar, não centavos
        s = s.replace(".", "")
    try:
        amount = Decimal(s)
        return amount if Decimal("50") <= amount <= Decimal("100000") else None
    except InvalidOperation:
        return None


def each_dict(value):
    if isinstance(value, list):
        for v in value:
            yield from each_dict(v)
    elif isinstance(value, dict):
        yield value
        for v in value.values():
            if isinstance(v, (list, dict)):
                yield from each_dict(v)


def valid_gpu(title):
    return bool(GPU.search(title) and MEMORY.search(title) and not EXCLUDE.search(title))


def permitted(url):
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in ALLOWED_HOSTS


def clean_seller(value):
    """Reject promo text accidentally captured alongside a seller name."""
    if isinstance(value, dict):
        value = value.get("name")
    if not isinstance(value, str):
        return None
    raw = re.sub(r"\s+", " ", value).strip(" :.;")
    # A loja aparece muitas vezes seguida imediatamente de textos de promoção.
    aliases = [(r"KaBuM!?", "KaBuM!"), (r"TerabyteShop", "TerabyteShop"),
               (r"Hardstore", "Hardstore"), (r"Patoloco", "Patoloco"),
               (r"Amazon(?:\.com\.br)?", "Amazon.com.br")]
    for pattern, result in aliases:
        if re.match(rf"^(?:{pattern})(?=\s|[.,;:]|$)", raw, re.I):
            return result
    if not (2 <= len(raw) <= 60):
        return None
    if re.search(r"\b(?:compre|produto|brinde|entrega|frete|suporte|promoção|desconto|estoque|cliente|garantia|parcelamento|receba|aproveite)\b", raw, re.I):
        return None
    return raw


def seller_from_page(text, host):
    """Only trust the store itself or a short, unambiguous seller label.

    Never assume that an item displayed on a marketplace belongs to its host.
    """
    if host == "www.terabyteshop.com.br":
        return "TerabyteShop"
    if host == "hardstore.com.br":
        return "Hardstore"
    top = text[:4500]
    if host == "www.kabum.com.br":
        # Don't use a greedy capture: otherwise 'Compre este produto e ganhe BRINDE'
        # gets appended to the merchant name, as seen in production logs.
        if re.search(r"Vendido\s+(?:e\s+entregue\s+)?por\s*:?(?:\s*)(KaBuM!?)(?=\s|[.,;:]|$)", top, re.I):
            return "KaBuM!"
        return None  # Marketplace seller not verifiable in this format.
    # Other marketplaces: require explicit name in JSON-LD, not a flattened page.
    return None


def similar_title(a, b):
    """Cross-check the JSON-LD Product against the actual product heading."""
    def words(s):
        return {x for x in re.findall(r"[a-z0-9]+", s.lower())
                if len(x) >= 3 and x not in {"placa", "video", "geforce", "nvidia", "gddr7", "ray", "tracing", "dlss"}}
    wa, wb = words(a), words(b)
    brands = {"asus", "gigabyte", "msi", "galax", "zotac", "palit", "gainward", "inno3d", "colorful", "pny", "asrock"}
    ba, bb = wa & brands, wb & brands
    if ba and bb and ba != bb:
        return False
    # RTX/5070/12GB alone does not prove the page and its structured
    # Product describe the same board. At least one distinctive token must match.
    common = {"rtx", "5070", "12gb", "12g", "oc", "prime", "gaming", "nvidia", "geforce"}
    da, db = wa - common, wb - common
    if da and db and not (da & db):
        return False
    return bool(wa and wb and len(wa & wb) / min(len(wa), len(wb)) >= 0.55)

def pix_candidate(text, base):
    """Only explicit PIX label near a single price in top product section.

    Never infer a PIX discount mathematically. Ambiguous pages return None.
    """
    found = set()
    for match in PIX.finditer(text[:2800]):
        raw = match.group(1) or match.group(2)
        p = price_decimal(raw)
        if p is not None and p <= base and p >= base * Decimal("0.65"):
            found.add(p)
    return next(iter(found)) if len(found) == 1 else None


def parse_patoloco(soup, url):
    """Extrai apenas um preço PIX explícito da seção do produto na Patoloco.

    Não aproveita preços de produtos relacionados nem calcula descontos implícitos.
    A estrutura real da loja pode mudar; ausência de dados é registrada, não alertada.
    """
    heading = next((h for h in soup.find_all("h1") if valid_gpu(h.get_text(" ", strip=True))), None)
    if heading is None:
        return None, "título de RTX 5070 12 GB não encontrado na página"
    title = heading.get_text(" ", strip=True)
    text = soup.get_text(" ", strip=True)
    start = text.find(title)
    if start < 0:
        return None, "seção do produto não encontrada"
    # Restringe ao cabeçalho de compra para evitar preços de outros anúncios.
    section = text[start:start + 2100]
    stop = re.search(r"\b(?:Consulte o frete|DESCRIÇÃO COMPLETA|Descrição completa)\b", section, re.I)
    if stop:
        section = section[:stop.start()]
    if re.search(r"este produto está indisponível|produto indisponível|produto esgotado|avise-me quando disponível", section, re.I):
        return None, "produto indisponível na Patoloco"
    if not re.search(r"\bComprar\b", section, re.I):
        return None, "botão de compra não confirmado na Patoloco"
    # Extrai preços apenas antes do primeiro botão Comprar.
    before_buy = re.split(r"\bComprar\b", section, maxsplit=1, flags=re.I)[0]
    prices = set()
    for match in PIX.finditer(before_buy):
        amount = price_decimal(match.group(1) or match.group(2))
        if amount is not None:
            prices.add(amount)
    if len(prices) != 1:
        return None, "preço PIX único não confirmado na seção de compra"
    return {
        "name": title,
        "price": prices.pop(),
        "price_type": "PIX explícito (Patoloco)",
        "seller": "Patoloco",
        "url": url,
    }, None


def parse_product(html, url):
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(url).hostname
    if host in {"patoloco.com.br", "www.patoloco.com.br"}:
        return parse_patoloco(soup, url)
    head = soup.find("main") or soup.body or soup
    main_text = head.get_text(" ", strip=True)
    # Sinal explícito de produto indisponível deve prevalecer sobre schema desatualizado.
    if re.search(r"\bproduto\s+esgotado\b|\bstatus\s*:\s*encomenda\b", main_text[:2500], re.I):
        return None, "sem estoque confirmado na página"
    primary_heading = soup.find('h1')
    heading_name = primary_heading.get_text(" ", strip=True) if primary_heading else ""
    if heading_name and not valid_gpu(heading_name):
        return None, "título principal não é RTX 5070 12 GB padrão"
    options = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text())
        except (TypeError, ValueError):
            continue
        for node in each_dict(data):
            kind = node.get("@type", [])
            if isinstance(kind, str):
                kind = [kind]
            if not isinstance(kind, list) or not any(str(x).split("/")[-1] == "Product" for x in kind):
                continue
            title = str(node.get("name") or "")
            if not valid_gpu(title):
                continue
            if heading_name and not similar_title(heading_name, title):
                continue  # Produto relacionado, não o anúncio principal.
            offers = node.get("offers", [])
            if isinstance(offers, dict):
                offers = [offers]
            if not isinstance(offers, list):
                continue
            for offer in offers:
                if not isinstance(offer, dict):
                    continue
                availability = str(offer.get("availability") or "").rstrip("/").split("/")[-1]
                if availability.lower() != "instock":
                    continue
                if str(offer.get("itemCondition", "")).lower().endswith(("usedcondition", "refurbishedcondition")):
                    continue
                spec = offer.get("priceSpecification") or {}
                if isinstance(spec, list):
                    spec = spec[0] if spec else {}
                if not isinstance(spec, dict):
                    spec = {}
                currency = str(offer.get("priceCurrency") or spec.get("priceCurrency") or "").upper()
                if currency != "BRL":
                    continue
                p = price_decimal(offer.get("price") or spec.get("price") or offer.get("lowPrice"))
                if p is None:
                    continue
                seller = clean_seller(offer.get("seller") or node.get("seller"))
                if not seller:
                    seller = seller_from_page(main_text, host)
                if not seller:
                    # Não notificar sem identificar vendedor (evita marketplace desconhecido).
                    continue
                pix = pix_candidate(main_text, p)
                actual = pix if pix is not None else p
                options.append({
                    "name": title,
                    "price": actual,
                    "price_type": "PIX explícito" if pix is not None else "preço estruturado",
                    "seller": seller,
                    "url": url,
                })
    if not options:
        return None, "sem oferta estruturada BRL/em estoque com vendedor identificado"
    return min(options, key=lambda o: o["price"]), None


def get_product(entry, client=requests):
    url = entry["url"]
    if not permitted(url):
        raise ValueError("domínio não permitido")
    response = client.get(url, timeout=18, headers={"User-Agent": "Mozilla/5.0 (compatible; RTX5070PriceRadar/2.2)"})
    response.raise_for_status()
    if not permitted(response.url):
        raise ValueError("redirecionamento para domínio não permitido")
    return parse_product(response.text, url)


def send_telegram(msg, client=requests):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        print("[ALERTA PENDENTE] Secrets Telegram ausentes", flush=True)
        return False
    resp = client.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat, "text": msg, "disable_web_page_preview": True}, timeout=18
    )
    resp.raise_for_status()
    if not resp.json().get("ok"):
        raise RuntimeError("Telegram não confirmou o envio")
    return True


def main():
    entries = json.loads((ROOT / "products.json").read_text(encoding="utf-8"))["products"]
    old = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    state = dict(old)
    errors = 0
    checked = 0
    found = 0
    for entry in entries:
        if not entry.get("enabled", False):
            continue
        checked += 1
        try:
            offer, issue = get_product(entry)
            if offer is None:
                print(f'[SEM CONFIRMAÇÃO] {entry["store"]}: {issue}', flush=True)
                continue
            found += 1
            price = offer["price"]
            print(f'[PREÇO] {entry["store"]}: R$ {price:.2f} ({offer["price_type"]}); vendedor: {offer["seller"]}', flush=True)
            last = price_decimal(old.get(offer["url"]))
            if price >= LIMIT or (last is not None and price >= last):
                continue
            message = (
                f'🚨 RTX 5070 12 GB abaixo de R$ {LIMIT:.2f}!\n'
                f'Loja: {entry["store"]}\nVendedor: {offer["seller"]}\n'
                f'Produto: {offer["name"]}\nPreço: R$ {price:.2f} ({offer["price_type"]})\n'
                f'Link: {offer["url"]}\n'
                '⚠️ Confirme vendedor, condição, estoque, cupom, frete e preço final no checkout.\n'
                f'Verificado: {datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")} UTC'
            )
            if send_telegram(message):
                state[offer["url"]] = str(price)
                print(f'[ALERTA ENVIADO] {entry["store"]}', flush=True)
        except requests.HTTPError as error:
            errors += 1
            status = error.response.status_code if error.response is not None else "?"
            print(f'[BLOQUEIO/HTTP] {entry["store"]}: código {status}; nenhuma oferta confirmada', file=sys.stderr, flush=True)
        except (requests.RequestException, ValueError, KeyError, RuntimeError) as error:
            errors += 1
            print(f'[ERRO] {entry["store"]}: {type(error).__name__}: {str(error)[:150]}', file=sys.stderr, flush=True)
    if state != old:
        STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f'[RESUMO] Fontes ativas: {checked}; preços validados: {found}; erros de consulta: {errors}', flush=True)
    if found == 0:
        print('[ATENÇÃO] Nenhum preço validado; a execução não deve ser interpretada como monitoramento saudável.', file=sys.stderr, flush=True)


if __name__ == '__main__':
    main()
