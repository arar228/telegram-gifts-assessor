"""
Альтернативный источник цен: apiTON (Gift по имени) + tonapi (NFT по адресу).

1. apiTON: POST /v2.Nft/Gift {"name": "FreshSocks-79283"} → адрес NFT
2. tonapi: GET /v2/nfts/{address} → sale.price если в продаже

Использование:
  python price_apiton_tonapi.py --file gifts_list.txt
  python price_apiton_tonapi.py --limit 30 --workers 20
"""
import re
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Tuple
from collections import defaultdict

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

APITON_GIFT_URL = "https://app.apiton.org/v2.Nft/Gift"
TONAPI_BASE = "https://tonapi.io/v2"


def parse_slug(link: str) -> Optional[str]:
    """Из t.me/nft/CollectionName-ID извлекает CollectionName-ID."""
    link = link.strip()
    m = re.search(r"t\.me/nft/([A-Za-z0-9]+-\d+)", link)
    return m.group(1) if m else None


def apiton_gift_address(slug: str) -> Dict:
    """apiTON: по имени подарка (FreshSocks-79283) возвращает адрес. {'address': str, 'error': str|None}"""
    out = {'address': None, 'error': None}
    try:
        r = requests.post(
            APITON_GIFT_URL,
            json={"name": slug},
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if r.status_code != 200:
            out['error'] = f"HTTP {r.status_code}"
            return out
        data = r.json()
        # Ожидаем адрес в ответе (уточнить по доке apiTON)
        addr = data.get('address') or data.get('nft_address') or data.get('item_address')
        if isinstance(addr, str) and len(addr) > 10:
            out['address'] = addr
        elif isinstance(data.get('result'), str):
            out['address'] = data['result']
    except Exception as e:
        out['error'] = str(e)
    return out


def tonapi_nft_price(address: str) -> Dict:
    """tonapi: по адресу NFT возвращает цену продажи если есть. {'price_ton': float|None, 'error': str|None}"""
    out = {'price_ton': None, 'error': None}
    try:
        r = requests.get(
            f"{TONAPI_BASE}/nfts/{address}",
            timeout=10,
        )
        if r.status_code != 200:
            out['error'] = f"HTTP {r.status_code}"
            return out
        data = r.json()
        sale = data.get('sale')
        if sale and isinstance(sale.get('price'), dict):
            val = int(sale['price'].get('value', 0)) / 1e9
            if val > 0:
                out['price_ton'] = val
    except Exception as e:
        out['error'] = str(e)
    return out


def check_one_link(link: str) -> Dict:
    """По одной ссылке: slug → apiTON адрес → tonapi цена."""
    slug = parse_slug(link)
    result = {
        'link': link,
        'slug': slug,
        'address': None,
        'price_ton': None,
        'on_sale': False,
        'error': None,
    }
    if not slug:
        result['error'] = 'Неверный формат'
        return result

    g = apiton_gift_address(slug)
    if g['error']:
        result['error'] = g['error']
        return result
    result['address'] = g['address']
    if not g['address']:
        return result

    p = tonapi_nft_price(g['address'])
    if p.get('price_ton'):
        result['price_ton'] = p['price_ton']
        result['on_sale'] = True
    if p.get('error') and not result['error']:
        result['error'] = p['error']
    return result


def main():
    import argparse
    p = argparse.ArgumentParser(description='Цены через apiTON + tonapi')
    p.add_argument('--file', '-f', default='gifts_list.txt')
    p.add_argument('--limit', '-n', type=int, default=0)
    p.add_argument('--workers', '-w', type=int, default=30)
    p.add_argument('--output', '-o', default='price_apiton_result.txt')
    args = p.parse_args()

    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            links = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Файл не найден: {args.file}")
        sys.exit(1)

    if args.limit > 0:
        links = links[:args.limit]

    total = len(links)
    print(f"Ссылок: {total}, воркеров: {args.workers}")
    print("Источники: apiTON Gift → tonapi NFT")
    print("=" * 50)

    results = [None] * total
    start = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        fut2idx = {ex.submit(check_one_link, link): i for i, link in enumerate(links)}
        for fut in as_completed(fut2idx):
            i = fut2idx[fut]
            results[i] = fut.result()
            done += 1
            print(f"\r[{done}/{total}]", end='', flush=True)

    elapsed = time.time() - start
    print(f"\rГотово за {elapsed:.1f} с\n")

    on_sale = [r for r in results if r and r.get('on_sale')]
    with_addr = [r for r in results if r and r.get('address')]
    total_sale = sum(r['price_ton'] for r in on_sale if r.get('price_ton'))

    print("РЕЗУЛЬТАТЫ")
    print("=" * 50)
    print(f"Всего: {total}")
    print(f"Получено адресов (apiTON): {len(with_addr)}")
    print(f"В продаже (tonapi): {len(on_sale)}")
    print(f"Сумма продаж: {total_sale:.2f} TON")

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write("apiTON Gift + tonapi NFT\n")
        f.write(f"Всего: {total} | Адресов: {len(with_addr)} | В продаже: {len(on_sale)}\n\n")
        for r in results:
            if not r:
                continue
            price = f"{r['price_ton']:.2f} TON" if r.get('price_ton') else "—"
            addr = r.get('address') or "—"
            err = f" | {r['error']}" if r.get('error') else ""
            f.write(f"{r['link']}\n  Адрес: {addr} | Цена: {price}{err}\n\n")
    print(f"\nОтчёт: {args.output}")


if __name__ == "__main__":
    main()
