"""
Проверка цен подарков по списку ссылок — через tonapi.io.

Группирует по коллекциям, получает Floor Price с tonapi.io (Getgems nftSearch
не возвращает данные по Telegram Gifts).

Использование:
  python check_list_prices.py                    # весь gifts_list.txt
  python check_list_prices.py --limit 20         # только первые 20
  python check_list_prices.py --workers 50       # 50 параллельных запросов к коллекциям
"""
import requests
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Tuple, List
from collections import defaultdict

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TONAPI_BASE = "https://tonapi.io/v2"


def parse_nft_link(link: str) -> Optional[Tuple[str, str]]:
    """Парсит ссылку t.me/nft/CollectionName-ID. Возвращает (collection_slug, item_number)."""
    link = link.strip()
    match = re.search(r"t\.me/nft/([A-Za-z0-9]+)-(\d+)", link)
    if match:
        return match.group(1), match.group(2)
    return None


def fetch_collection_floor(collection_slug: str) -> Dict:
    """
    Получает floor price коллекции через tonapi.io.
    Возвращает: {'floor': float, 'avg': float, 'name': str, 'address': str, 'error': str|None}
    """
    result = {'floor': 0.0, 'avg': 0.0, 'name': collection_slug, 'address': None, 'error': None}
    try:
        resp = requests.get(
            f"{TONAPI_BASE}/nfts/search",
            params={"q": collection_slug, "limit": 10},
            timeout=10,
        )
        if resp.status_code != 200:
            result['error'] = f"HTTP {resp.status_code}"
            return result

        data = resp.json()
        items = data.get('nft_items', [])
        collections = {}
        for item in items:
            coll = item.get('collection', {})
            if coll:
                addr = coll.get('address', '')
                name = coll.get('name', '')
                if addr and addr not in collections:
                    collections[addr] = {'name': name, 'address': addr}

        if not collections:
            return result

        coll_addr = list(collections.values())[0]['address']
        result['address'] = coll_addr
        result['name'] = list(collections.values())[0]['name']

        resp2 = requests.get(
            f"{TONAPI_BASE}/nfts/collections/{coll_addr}/items",
            params={"limit": 100, "offset": 0},
            timeout=15,
        )
        if resp2.status_code != 200:
            return result

        data2 = resp2.json()
        items2 = data2.get('nft_items', [])
        on_sale = [i for i in items2 if i.get('sale')]
        if on_sale:
            prices = []
            for item in on_sale:
                sale = item['sale']
                val = int(sale.get('price', {}).get('value', 0)) / 1e9
                if val > 0:
                    prices.append(val)
            if prices:
                result['floor'] = min(prices)
                result['avg'] = sum(prices) / len(prices)
    except Exception as e:
        result['error'] = str(e)
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Проверка цен подарков через tonapi.io')
    parser.add_argument('--file', '-f', default='gifts_list.txt', help='Файл со списком ссылок')
    parser.add_argument('--limit', '-n', type=int, default=0, help='Ограничить количество (0 = все)')
    parser.add_argument('--workers', '-w', type=int, default=50, help='Параллельных запросов к коллекциям')
    parser.add_argument('--output', '-o', default='check_prices_result.txt', help='Файл результата')
    parser.add_argument('--quiet', '-q', action='store_true', help='Минимум вывода в консоль')
    args = parser.parse_args()

    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            links = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"❌ Файл не найден: {args.file}")
        sys.exit(1)

    if args.limit > 0:
        links = links[:args.limit]

    total = len(links)
    collections_to_fetch = set()
    link_data = []
    for link in links:
        parsed = parse_nft_link(link)
        if parsed:
            slug, num = parsed
            collections_to_fetch.add(slug)
            link_data.append({'link': link, 'collection_slug': slug, 'item_number': num})
        else:
            link_data.append({'link': link, 'collection_slug': '', 'item_number': '', 'error': 'Неверный формат'})

    unique_collections = list(collections_to_fetch)
    print(f"📋 Загружено {total} ссылок, {len(unique_collections)} уникальных коллекций")
    print(f"⚡ Параллельных запросов: {args.workers}")
    print("=" * 60)

    collection_floors = {}
    start = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_slug = {executor.submit(fetch_collection_floor, slug): slug for slug in unique_collections}
        for future in as_completed(future_to_slug):
            slug = future_to_slug[future]
            data = future.result()
            collection_floors[slug] = {
                'floor': data['floor'], 'avg': data['avg'],
                'name': data['name'], 'error': data['error'],
            }
            done += 1
            if not args.quiet:
                floor_str = f"{data['floor']:.2f} TON" if data['floor'] else "—"
                print(f"\r[{done}/{len(unique_collections)}] {slug}: {floor_str}", end='', flush=True)

    elapsed = time.time() - start
    print(f"\rГотово за {elapsed:.1f} с")

    results = []
    total_floor_value = 0.0
    for ld in link_data:
        slug = ld['collection_slug']
        floor = collection_floors.get(slug, {}).get('floor', 0) or 0
        coll_name = collection_floors.get(slug, {}).get('name', slug)
        err = collection_floors.get(slug, {}).get('error') or ld.get('error')
        r = {
            'collection_slug': slug,
            'item_number': ld['item_number'],
            'on_sale': False,
            'sale_price_ton': None,
            'floor_price_ton': floor if floor else None,
            'collection_name': coll_name,
            'error': err,
        }
        results.append((ld['link'], r))
        if floor:
            total_floor_value += floor

    print("\n\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ")
    print("=" * 60)
    print(f"Всего подарков:       {total}")
    print(f"Оценка (floor):       {total_floor_value:.2f} TON")

    try:
        resp = requests.get(f"{TONAPI_BASE}/rates?tokens=ton&currencies=usd", timeout=5)
        if resp.status_code == 200:
            ton_usd = float(resp.json()['rates']['TON']['prices']['USD'])
            print(f"\nКурс TON: ~${ton_usd:.2f} USD")
            print(f"Оценка (floor): ~${total_floor_value * ton_usd:.2f} USD")
    except Exception:
        pass

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("ПРОВЕРКА ЦЕН ПОДАРКОВ (tonapi.io)\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Всего: {total} | Оценка (floor): {total_floor_value:.2f} TON\n\n")
        f.write("-" * 70 + "\n\n")

        for link, r in results:
            slug = r['collection_slug']
            num = r['item_number']
            floor_str = f"{r['floor_price_ton']:.2f} TON" if r['floor_price_ton'] else "—"
            err_str = f" | Ошибка: {r['error']}" if r['error'] else ""
            f.write(f"{link}\n")
            f.write(f"  Коллекция: {slug} | №{num} | Floor: {floor_str}{err_str}\n\n")

    print(f"\n📄 Детальный отчёт: {args.output}")


if __name__ == "__main__":
    main()
