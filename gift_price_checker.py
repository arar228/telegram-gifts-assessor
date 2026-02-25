"""
Получение цен на Telegram NFT подарки из списка через Fragment.com.

Fragment.com — официальный маркетплейс Telegram для торговли NFT подарками.
Скрипт парсит страницы коллекций и получает floor price (минимальную цену
на продаже) в TON для каждого типа подарка.

Использование:
  python gift_price_checker.py                     # весь gifts_list.txt
  python gift_price_checker.py --file my_list.txt  # свой файл
  python gift_price_checker.py --limit 50          # первые 50 ссылок
  python gift_price_checker.py --workers 3         # параллельных запросов
"""
import os
import re
import sys
import time
import json
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    import requests
except ImportError:
    print("Установите requests: pip install requests")
    sys.exit(1)

FRAGMENT_BASE = "https://fragment.com"
TONAPI_BASE = "https://tonapi.io/v2"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Глобальный кэш курса TON/USD
_ton_rate = None


def parse_nft_link(link: str) -> Optional[Tuple[str, str]]:
    """Парсит ссылку t.me/nft/CollectionName-ID → (collection_slug, item_id)."""
    link = link.strip()
    match = re.search(r"t\.me/nft/([A-Za-z0-9]+)-(\d+)", link)
    if match:
        return match.group(1), match.group(2)
    return None


def _parse_grid_items(html: str):
    """
    Парсит все gift-карточки из HTML Fragment.com.
    
    Каждая карточка — <a class="tm-grid-item"> с:
      - ценой: <div class="... icon-ton">PRICE</div> или icon-star
      - статусом: <div class="tm-grid-item-status tm-status-unavail">Sold</div>
    
    Возвращает два списка цен в TON: (active_prices, sold_prices)
    """
    items = re.findall(
        r'<a href="(/gift/[^"]+)"[^>]*class="[^"]*tm-grid-item[^"]*"[^>]*>(.*?)</a>',
        html, re.DOTALL
    )
    
    active_prices = []
    sold_prices = []
    
    for link, content in items:
        # Извлекаем цену
        price_match = re.search(r'icon-ton[^>]*>\s*([\d,.]+)', content)
        if not price_match:
            continue
        
        try:
            price = float(price_match.group(1).replace(',', ''))
        except ValueError:
            continue
        
        if price <= 0:
            continue
        
        # Проверяем статус: Sold (tm-status-unavail) или активный
        is_sold = 'tm-status-unavail' in content or '>Sold<' in content
        
        if is_sold:
            sold_prices.append(price)
        else:
            active_prices.append(price)
    
    return active_prices, sold_prices


def get_fragment_collection_floor(slug: str) -> Dict:
    """
    Получает floor price коллекции с Fragment.com.
    
    Парсит страницу /gifts/<slug>?sort=price и разделяет карточки на:
      - Активные (On Auction / For sale) → floor = min(active)
      - Проданные (Sold) → last_sold = min(sold) (запасной вариант)
    
    Возвращает dict с ценой.
    """
    global _ton_rate
    result = {
        'slug': slug,
        'name': slug,
        'floor_ton': 0.0,
        'floor_usd': 0.0,
        'last_sold_ton': 0.0,
        'active_count': 0,
        'sold_count': 0,
        'is_sold_price': False,   # True если цена из проданных (нет активных)
        'error': None,
    }
    
    try:
        # Загружаем страницу коллекции, сортировка по цене
        url = f"{FRAGMENT_BASE}/gifts/{slug}?sort=price"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        
        if resp.status_code != 200:
            result['error'] = f"HTTP {resp.status_code}"
            return result
        
        text = resp.text
        
        # Извлекаем tonRate из ajInit
        aj_match = re.search(r'ajInit\((\{.*?\})\)', text)
        if aj_match:
            try:
                aj_data = json.loads(aj_match.group(1))
                rate = aj_data.get('state', {}).get('tonRate', 0.0)
                if rate > 0:
                    _ton_rate = rate
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Извлекаем display name из заголовка секции
        name_match = re.search(r'tm-section-header-title">(.*?)<', text)
        if name_match:
            result['name'] = name_match.group(1).strip()
        
        # Парсим все карточки, разделяя на активные и проданные
        active_prices, sold_prices = _parse_grid_items(text)
        result['active_count'] = len(active_prices)
        result['sold_count'] = len(sold_prices)
        
        if active_prices:
            # Есть активные листинги — берём минимальную цену
            result['floor_ton'] = min(active_prices)
            result['is_sold_price'] = False
        elif sold_prices:
            # Нет активных, но есть проданные — берём мин. цену последних продаж
            result['floor_ton'] = min(sold_prices)
            result['is_sold_price'] = True
        
        if sold_prices:
            result['last_sold_ton'] = min(sold_prices)
        
        if result['floor_ton'] > 0 and _ton_rate:
            result['floor_usd'] = result['floor_ton'] * _ton_rate
        
        if not active_prices and not sold_prices:
            result['error'] = "Нет данных о ценах"
            
    except requests.exceptions.Timeout:
        result['error'] = "Таймаут"
    except requests.exceptions.ConnectionError:
        result['error'] = "Ошибка соединения"
    except Exception as e:
        result['error'] = str(e)
    
    return result


def get_ton_price_usd() -> float:
    """Получить текущий курс TON в USD."""
    global _ton_rate
    if _ton_rate and _ton_rate > 0:
        return _ton_rate
    try:
        resp = requests.get(
            f"{TONAPI_BASE}/rates?tokens=ton&currencies=usd",
            headers={"Accept": "application/json"},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            rate = float(data["rates"]["TON"]["prices"]["USD"])
            _ton_rate = rate
            return rate
    except Exception:
        pass
    return 0.0


def format_num(n, decimals=2) -> str:
    """Форматирует число с разделителями тысяч."""
    if isinstance(n, int):
        return f"{n:,}".replace(',', ' ')
    return f"{n:,.{decimals}f}"


def main():
    parser = argparse.ArgumentParser(
        description="Цены Telegram NFT подарков через Fragment.com"
    )
    parser.add_argument("--file", "-f", default="gifts_list.txt", help="Файл со ссылками")
    parser.add_argument("--limit", "-n", type=int, default=0, help="Макс. ссылок (0 = все)")
    parser.add_argument("--workers", "-w", type=int, default=3, help="Параллельных запросов")
    parser.add_argument("--output", "-o", default="gift_prices_result.txt", help="Файл результата")
    parser.add_argument("--delay", "-d", type=float, default=0.5, help="Задержка (сек)")
    args = parser.parse_args()

    # 1. Читаем файл
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Файл не найден: {args.file}")
        sys.exit(1)

    if args.limit > 0:
        lines = lines[: args.limit]

    # 2. Группируем по коллекциям
    by_collection = defaultdict(list)
    bad_links = []

    for link in lines:
        parsed = parse_nft_link(link)
        if parsed:
            slug, item_id = parsed
            by_collection[slug].append({"link": link, "id": item_id})
        else:
            bad_links.append(link)

    total_gifts = sum(len(items) for items in by_collection.values())
    unique_collections = list(by_collection.keys())

    print(f"Загружено: {len(lines)} ссылок")
    print(f"Уникальных коллекций: {len(unique_collections)}")
    print(f"Подарков для оценки: {total_gifts}")
    if bad_links:
        print(f"Нераспознанных ссылок: {len(bad_links)}")
    print(f"Параллельных запросов: {args.workers}")
    print("=" * 60)
    print("Источник цен: Fragment.com")
    print("=" * 60)

    # 3. Получаем цены
    collection_prices = {}
    done = 0
    start = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {
            executor.submit(get_fragment_collection_floor, slug): slug
            for slug in unique_collections
        }
        
        for future in as_completed(future_map):
            slug = future_map[future]
            try:
                result = future.result()
            except Exception as e:
                result = {
                    'slug': slug, 'name': slug,
                    'floor_ton': 0.0, 'floor_usd': 0.0, 'last_sold_ton': 0.0,
                    'active_count': 0, 'sold_count': 0,
                    'is_sold_price': False, 'error': str(e),
                }
            collection_prices[slug] = result
            done += 1

            if result['floor_ton'] > 0:
                sold_mark = " [продажи]" if result.get('is_sold_price') else ""
                price_str = f"{result['floor_ton']:.2f} TON (~${result['floor_usd']:.2f}){sold_mark}"
            else:
                price_str = "—"

            name = result.get('name', slug)
            status = f"[{done}/{len(unique_collections)}] {name}: {price_str}"
            print(f"\r{status:<70}", end="", flush=True)
            
            time.sleep(args.delay)

    elapsed = time.time() - start
    print(f"\rВсе коллекции проверены за {elapsed:.1f} с" + " " * 40)

    # 4. Курс TON/USD
    ton_usd = get_ton_price_usd()
    if ton_usd > 0:
        print(f"Курс TON: ~${ton_usd:.2f} USD")

    # 5. Считаем итоги
    total_ton = 0.0
    total_usd = 0.0
    priced_gifts = 0
    priced_collections = 0

    sorted_slugs = sorted(
        unique_collections,
        key=lambda s: collection_prices[s]["floor_ton"] * len(by_collection[s]),
        reverse=True,
    )

    results = []
    for slug in sorted_slugs:
        cp = collection_prices[slug]
        count = len(by_collection[slug])
        floor_ton = cp['floor_ton']
        floor_usd = cp['floor_usd']
        value_ton = floor_ton * count
        value_usd = floor_usd * count

        if floor_ton > 0:
            total_ton += value_ton
            total_usd += value_usd
            priced_gifts += count
            priced_collections += 1

        results.append({
            'slug': slug,
            'name': cp.get('name', slug),
            'count': count,
            'floor_ton': floor_ton,
            'floor_usd': floor_usd,
            'value_ton': value_ton,
            'value_usd': value_usd,
            'active_count': cp.get('active_count', 0),
            'sold_count': cp.get('sold_count', 0),
            'is_sold_price': cp.get('is_sold_price', False),
            'error': cp.get('error'),
        })

    # 6. Вывод
    print("\n" + "=" * 60)
    print("ОЦЕНКА СТОИМОСТИ ПОДАРКОВ")
    print("=" * 60)
    print(f"\nВсего подарков:  {total_gifts}")
    print(f"Оценено:         {priced_gifts}/{total_gifts} "
          f"({priced_collections}/{len(unique_collections)} коллекций)")
    
    if total_ton > 0:
        print(f"\nСтоимость (floor):  {format_num(total_ton)} TON")
    if total_usd > 0:
        print(f"Стоимость (floor):  ~${format_num(total_usd)} USD")

    print(f"\n{'=' * 60}")
    print("ПО КОЛЛЕКЦИЯМ")
    print(f"{'=' * 60}")

    for r in results:
        if r['floor_ton'] > 0:
            sold_mark = " [цена продажи]" if r['is_sold_price'] else ""
            print(f"\n  {r['name']} ({r['slug']}) — {r['count']} шт.")
            print(f"    Floor: {r['floor_ton']:.2f} TON (~${r['floor_usd']:.2f}){sold_mark}")
            print(f"    Сумма: {format_num(r['value_ton'])} TON (~${format_num(r['value_usd'])})")
            print(f"    Активных/Проданных: {r['active_count']}/{r['sold_count']}")
        else:
            err = f" | {r['error']}" if r.get('error') else ""
            print(f"\n  {r['name']} ({r['slug']}) — {r['count']} шт.")
            print(f"    Цена: неизвестна{err}")

    # 7. Сохранение
    with open(args.output, "w", encoding="utf-8") as out:
        out.write("=" * 70 + "\n")
        out.write("ЦЕНЫ TELEGRAM NFT ПОДАРКОВ (Fragment.com)\n")
        out.write("=" * 70 + "\n\n")
        out.write(f"Файл: {args.file}\n")
        out.write(f"Дата: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        out.write(f"Всего подарков: {total_gifts}\n")
        out.write(f"Оценено: {priced_gifts}/{total_gifts} "
                  f"({priced_collections}/{len(unique_collections)} коллекций)\n\n")
        if total_ton > 0:
            out.write(f"Стоимость (floor): {format_num(total_ton)} TON\n")
        if total_usd > 0:
            out.write(f"Стоимость (floor): ~${format_num(total_usd)} USD\n")
        if ton_usd > 0:
            out.write(f"Курс TON: ~${ton_usd:.2f} USD\n")
        out.write("\n" + "-" * 70 + "\n")
        out.write("ПО КОЛЛЕКЦИЯМ\n")
        out.write("-" * 70 + "\n\n")

        for r in results:
            out.write(f"[{r['slug']}] {r['name']} — {r['count']} шт.\n")
            if r['floor_ton'] > 0:
                sold_mark = " [цена продажи, нет активных]" if r['is_sold_price'] else ""
                out.write(f"  Floor: {r['floor_ton']:.2f} TON (~${r['floor_usd']:.2f}){sold_mark}\n")
                out.write(f"  Сумма: {format_num(r['value_ton'])} TON (~${format_num(r['value_usd'])})\n")
                out.write(f"  Активных: {r['active_count']} | Проданных: {r['sold_count']}\n")
            else:
                err = f" ({r['error']})" if r.get('error') else ""
                out.write(f"  Цена: неизвестна{err}\n")
            out.write("\n")

        # Детальный список
        out.write("-" * 70 + "\n")
        out.write("ДЕТАЛЬНЫЙ СПИСОК\n")
        out.write("-" * 70 + "\n\n")

        for slug in sorted_slugs:
            cp = collection_prices[slug]
            items = by_collection[slug]
            floor_ton = cp['floor_ton']
            floor_usd = cp['floor_usd']
            name = cp.get('name', slug)

            sold_mark = " [цена продажи]" if cp.get('is_sold_price') else ""
            for item in items:
                if floor_ton > 0:
                    price_str = f"{floor_ton:.2f} TON (~${floor_usd:.2f}){sold_mark}"
                else:
                    price_str = "—"
                out.write(f"{item['link']}\n")
                out.write(f"  {name} #{item['id']} | Floor: {price_str}\n\n")

        out.write("=" * 70 + "\n")
        out.write("ИТОГО\n")
        out.write("=" * 70 + "\n")
        if total_ton > 0:
            out.write(f"\nОценка (floor): {format_num(total_ton)} TON\n")
        if total_usd > 0:
            out.write(f"Оценка (floor): ~${format_num(total_usd)} USD\n")

    print(f"\n{'=' * 60}")
    print(f"Подробный отчёт: {args.output}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
