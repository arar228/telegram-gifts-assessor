"""
Определение цен подарков из gifts_list.txt через API giftasset.pro.

Использует GET /api/v1/gifts/get_gift_by_name?name=CollectionName-ID
(документация: https://giftasset.pro/docs)

Переменная окружения GIFTASSET_API_KEY — опционально, если API требует ключ.

Использование:
  python price_giftasset.py                    # файл gifts_list.txt
  python price_giftasset.py --file list.txt
  python price_giftasset.py --limit 50         # только первые 50
  python price_giftasset.py --workers 5        # параллельных запросов (по умолчанию 3)
"""
import os
import re
import sys
import time
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    import requests
except ImportError:
    print("Установите requests: pip install requests")
    sys.exit(1)

GIFTASSET_BASE = "https://giftasset.pro/api/v1"


def parse_nft_link(link: str):
    """Парсит ссылку t.me/nft/CollectionName-ID. Возвращает имя подарка 'CollectionName-ID' или None."""
    link = link.strip()
    match = re.search(r"t\.me/nft/([A-Za-z0-9]+-\d+)", link)
    if match:
        return match.group(1)
    return None


def get_gift_price(gift_name: str, api_key: str = None) -> dict:
    """
    Запрос к giftasset.pro: GET /gifts/get_gift_by_name?name=...
    Возвращает: {
        'gift_name': str,
        'price_ton': float | None,   # market_floor.min или avg
        'market_floor': {'min','max','avg'} | None,
        'collection_floor': float | None,
        'error': str | None
    }
    """
    result = {
        'gift_name': gift_name,
        'price_ton': None,
        'market_floor': None,
        'collection_floor': None,
        'error': None,
    }
    try:
        url = f"{GIFTASSET_BASE}/gifts/get_gift_by_name"
        params = {"name": gift_name}
        headers = {"Accept": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        if resp.status_code == 401:
            result['error'] = "Unauthorized (нужен API ключ? задайте GIFTASSET_API_KEY)"
            return result
        if resp.status_code != 200:
            result['error'] = f"HTTP {resp.status_code}"
            return result
        data = resp.json()
        mf = data.get("market_floor")
        if mf and isinstance(mf, dict):
            result['market_floor'] = mf
            # цена: min или avg (в TON)
            result['price_ton'] = mf.get("min") or mf.get("avg")
            if result['price_ton'] is not None:
                result['price_ton'] = float(result['price_ton'])
        # collection_floor из первого провайдера
        providers = data.get("providers") or {}
        for p in providers.values():
            if isinstance(p, dict) and "collection_floor" in p:
                result['collection_floor'] = float(p["collection_floor"])
                break
        if result['price_ton'] is None and result['collection_floor'] is not None:
            result['price_ton'] = result['collection_floor']
    except Exception as e:
        result['error'] = str(e)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Цены подарков из списка через API giftasset.pro"
    )
    parser.add_argument("--file", "-f", default="gifts_list.txt", help="Файл со ссылками")
    parser.add_argument("--limit", "-n", type=int, default=0, help="Макс. количество (0 = все)")
    parser.add_argument("--workers", "-w", type=int, default=3, help="Параллельных запросов")
    parser.add_argument("--output", "-o", default="price_giftasset_result.txt", help="Файл результата")
    parser.add_argument("--use-avg", action="store_true", help="Использовать среднюю цену (avg) вместо min")
    args = parser.parse_args()

    api_key = os.environ.get("GIFTASSET_API_KEY", "").strip() or None

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Файл не найден: {args.file}")
        sys.exit(1)

    if args.limit > 0:
        lines = lines[: args.limit]

    # Парсим ссылки → имя подарка (CollectionName-ID)
    gifts = []
    for link in lines:
        name = parse_nft_link(link)
        if name:
            gifts.append({"link": link, "name": name})
        else:
            gifts.append({"link": link, "name": None, "error": "Неверный формат ссылки"})

    total = len(gifts)
    to_fetch = [g for g in gifts if g.get("name")]
    print(f"Загружено {total} ссылок, запрос цен для {len(to_fetch)} подарков (giftasset.pro)")
    if api_key:
        print("Используется API ключ (GIFTASSET_API_KEY)")
    else:
        print("API ключ не задан (GIFTASSET_API_KEY). Если API вернёт 401 — задайте ключ.")
    print("=" * 60)

    start = time.time()
    results_by_name = {}
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_gift = {
            executor.submit(get_gift_price, g["name"], api_key): g for g in to_fetch
        }
        for future in as_completed(future_to_gift):
            g = future_to_gift[future]
            r = future.result()
            if args.use_avg and r.get("market_floor") and r["market_floor"].get("avg") is not None:
                r["price_ton"] = float(r["market_floor"]["avg"])
            results_by_name[g["name"]] = r
            done += 1
            price_str = f"{r['price_ton']:.2f} TON" if r.get("price_ton") else "—"
            print(f"\r[{done}/{len(to_fetch)}] {g['name']}: {price_str}", end="", flush=True)
            time.sleep(0.15)  # небольшой rate limit между запросами

    elapsed = time.time() - start
    print(f"\rГотово за {elapsed:.1f} с")

    # Группируем по коллекции (первая часть имени до последнего '-')
    by_collection = defaultdict(list)
    for g in gifts:
        name = g.get("name")
        if not name:
            by_collection["_unknown"].append((g, None))
            continue
        coll = name.rsplit("-", 1)[0] if "-" in name else name
        res = results_by_name.get(name, {})
        price = res.get("price_ton") if res else None
        by_collection[coll].append((g, res))

    total_ton = 0.0
    for coll, items in by_collection.items():
        for g, res in items:
            if res and res.get("price_ton") is not None:
                total_ton += res["price_ton"]

    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ (giftasset.pro)")
    print("=" * 60)
    print(f"Всего подарков: {total}")
    print(f"Оценка (цена по API): {total_ton:.2f} TON")

    with open(args.output, "w", encoding="utf-8") as out:
        out.write("=" * 70 + "\n")
        out.write("ЦЕНЫ ПОДАРКОВ — giftasset.pro API\n")
        out.write("=" * 70 + "\n\n")
        out.write(f"Файл: {args.file} | Подарков: {total}\n")
        out.write(f"Оценка итого: {total_ton:.2f} TON\n\n")
        out.write("-" * 70 + "\n\n")

        for coll in sorted(by_collection.keys(), key=lambda c: (c == "_unknown", c)):
            items = by_collection[coll]
            coll_ton = sum(
                (r.get("price_ton") or 0) for _, r in items if r and r.get("price_ton") is not None
            )
            out.write(f"[{coll}] ({len(items)} шт.) — сумма: {coll_ton:.2f} TON\n\n")
            for g, res in items:
                out.write(f"  {g['link']}\n")
                if g.get("error"):
                    out.write(f"    Ошибка: {g['error']}\n")
                elif res:
                    p = res.get("price_ton")
                    price_str = f"{p:.2f} TON" if p is not None else "—"
                    err = f" | {res['error']}" if res.get("error") else ""
                    out.write(f"    Цена: {price_str}{err}\n")
                out.write("\n")
            out.write("\n")

        out.write("=" * 70 + "\n")
        out.write("ИТОГО\n")
        out.write("=" * 70 + "\n")
        out.write(f"\nОценка: {total_ton:.2f} TON\n")

    print(f"\nДетальный отчёт: {args.output}")


if __name__ == "__main__":
    main()
