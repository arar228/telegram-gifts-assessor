"""
Оценка стоимости NFT подарков по списку ссылок t.me/nft/...

Использование:
  python price_from_list.py < список_ссылок.txt
  или
  python price_from_list.py ссылка1 ссылка2 ...
"""
import sys
import requests
import time
from typing import Dict, List, Tuple
from collections import defaultdict

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TONAPI_BASE = "https://tonapi.io/v2"


def parse_slug_from_url(url: str) -> Tuple[str, str]:
    """
    Парсит slug из URL вида t.me/nft/CollectionName-ID
    Возвращает: (collection_name, full_slug)
    """
    url = url.strip()
    if url.startswith('http'):
        url = url.split('//', 1)[1] if '//' in url else url
    if url.startswith('t.me/nft/'):
        slug = url.replace('t.me/nft/', '')
    elif url.startswith('@'):
        slug = url[1:]
    else:
        slug = url
    
    # Разделяем на коллекцию и ID
    parts = slug.split('-', 1)
    if len(parts) == 2:
        collection_name = parts[0]
        nft_id = parts[1]
        return collection_name, slug
    return slug, slug


def tonapi_search_collection(query: str) -> List[Dict]:
    """Поиск коллекции по названию через tonapi.io"""
    try:
        # Пробуем поиск через /nfts/search
        url = f"{TONAPI_BASE}/nfts/search"
        params = {"q": query, "limit": 10}
        resp = requests.get(url, params=params, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('nft_items', [])
            collections = {}
            
            for item in items:
                coll = item.get('collection', {})
                if coll:
                    coll_addr = coll.get('address', '')
                    coll_name = coll.get('name', '')
                    if coll_addr and coll_name:
                        collections[coll_addr] = {
                            'name': coll_name,
                            'address': coll_addr,
                        }
            
            return list(collections.values())
    except Exception as e:
        print(f"  Ошибка поиска '{query}': {e}")
    
    return []


def tonapi_get_collection_by_address(address: str) -> Dict:
    """Получить информацию о коллекции по адресу"""
    try:
        url = f"{TONAPI_BASE}/nfts/collections/{address}"
        resp = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}


def tonapi_get_collection_floor(collection_address: str) -> Tuple[float, float, int]:
    """Получить floor price коллекции"""
    try:
        url = f"{TONAPI_BASE}/nfts/collections/{collection_address}/items"
        params = {"limit": 100, "offset": 0}
        resp = requests.get(url, headers={"Accept": "application/json"}, params=params, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('nft_items', [])
            on_sale = [i for i in items if i.get('sale')]
            
            if on_sale:
                prices = []
                for item in on_sale:
                    sale = item['sale']
                    price_val = int(sale.get('price', {}).get('value', 0)) / 1e9
                    if price_val > 0:
                        prices.append(price_val)
                
                if prices:
                    return min(prices), sum(prices) / len(prices), len(prices)
    except Exception:
        pass
    return 0.0, 0.0, 0


def get_ton_price_usd() -> float:
    """Получить курс TON в USD"""
    try:
        resp = requests.get(
            f"{TONAPI_BASE}/rates?tokens=ton&currencies=usd",
            headers={"Accept": "application/json"},
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            return float(data['rates']['TON']['prices']['USD'])
    except Exception:
        pass
    return 0.0


def evaluate_gifts_from_list(urls: List[str]):
    """Оценка стоимости подарков по списку ссылок"""
    
    # 1. Парсим ссылки и группируем по коллекциям
    collections = defaultdict(list)
    
    print("Парсинг ссылок...")
    for url in urls:
        if not url.strip():
            continue
        coll_name, full_slug = parse_slug_from_url(url)
        collections[coll_name].append({
            'slug': full_slug,
            'url': url if url.startswith('http') else f"https://{url}",
        })
    
    print(f"Найдено {len(collections)} коллекций, {sum(len(g) for g in collections.values())} подарков\n")
    
    # 2. Для каждой коллекции ищем адрес и floor price
    print("Поиск цен через tonapi.io...")
    print("=" * 70)
    
    collection_data = {}
    
    for coll_name, gifts in collections.items():
        print(f"\n{coll_name} ({len(gifts)} подарков)")
        
        # Ищем коллекцию
        search_results = tonapi_search_collection(coll_name)
        
        if search_results:
            # Берём первую найденную коллекцию
            coll_info = search_results[0]
            coll_addr = coll_info['address']
            coll_display_name = coll_info['name']
            
            print(f"  Найдена коллекция: {coll_display_name}")
            print(f"  Адрес: {coll_addr[:30]}...")
            
            # Получаем floor price
            floor, avg, count = tonapi_get_collection_floor(coll_addr)
            
            if floor > 0:
                collection_data[coll_name] = {
                    'name': coll_display_name,
                    'address': coll_addr,
                    'floor_price': floor,
                    'avg_price': avg,
                    'on_sale_count': count,
                    'gifts': gifts,
                }
                print(f"  Floor: {floor:.2f} TON | Средняя: {avg:.2f} TON | На продаже: {count}")
            else:
                print(f"  Цена: не найдена (нет предметов на продаже)")
                collection_data[coll_name] = {
                    'name': coll_display_name,
                    'address': coll_addr,
                    'floor_price': 0.0,
                    'avg_price': 0.0,
                    'on_sale_count': 0,
                    'gifts': gifts,
                }
        else:
            print(f"  Коллекция не найдена в tonapi.io")
            collection_data[coll_name] = {
                'name': coll_name,
                'address': None,
                'floor_price': 0.0,
                'avg_price': 0.0,
                'on_sale_count': 0,
                'gifts': gifts,
            }
        
        time.sleep(0.5)  # Rate limiting
    
    # 3. Выводим отчёт
    print("\n" + "=" * 70)
    print("ОЦЕНКА СТОИМОСТИ")
    print("=" * 70)
    
    total_gifts = sum(len(c['gifts']) for c in collection_data.values())
    priced_collections = sum(1 for c in collection_data.values() if c['floor_price'] > 0)
    priced_gifts = sum(len(c['gifts']) for c in collection_data.values() if c['floor_price'] > 0)
    
    print(f"\nВсего подарков: {total_gifts}")
    print(f"Оценено коллекций: {priced_collections}/{len(collection_data)}")
    print(f"Оценено подарков: {priced_gifts}/{total_gifts}")
    
    # Сортируем по стоимости
    sorted_colls = sorted(
        collection_data.items(),
        key=lambda x: (x[1]['floor_price'] == 0, -x[1]['floor_price'] * len(x[1]['gifts']))
    )
    
    grand_total_floor = 0.0
    grand_total_avg = 0.0
    
    print(f"\n{'=' * 70}")
    print("СТОИМОСТЬ ПО КОЛЛЕКЦИЯМ")
    print(f"{'=' * 70}")
    
    for coll_name, data in sorted_colls:
        count = len(data['gifts'])
        floor = data['floor_price']
        avg = data['avg_price']
        
        if floor > 0:
            value_floor = floor * count
            value_avg = avg * count
            grand_total_floor += value_floor
            grand_total_avg += value_avg
            
            print(f"\n{data['name']} ({coll_name})")
            print(f"  Кол-во: {count}")
            print(f"  Floor: {floor:.2f} TON | Средняя: {avg:.2f} TON")
            print(f"  Стоимость (floor):   {value_floor:.2f} TON")
            print(f"  Стоимость (средняя): {value_avg:.2f} TON")
        else:
            print(f"\n{data['name']} ({coll_name})")
            print(f"  Кол-во: {count}")
            print(f"  Цена: неизвестна")
    
    # Итого
    print(f"\n{'=' * 70}")
    print("ИТОГО")
    print(f"{'=' * 70}")
    print(f"\nСтоимость (по floor price):   {grand_total_floor:.2f} TON")
    print(f"Стоимость (по средней цене):  {grand_total_avg:.2f} TON")
    
    ton_usd = get_ton_price_usd()
    if ton_usd > 0:
        print(f"\nКурс TON: ~${ton_usd:.2f} USD")
        print(f"Стоимость (floor):   ~${grand_total_floor * ton_usd:.2f} USD")
        print(f"Стоимость (средняя): ~${grand_total_avg * ton_usd:.2f} USD")
    
    # Сохраняем в файл
    filename = "portfolio_from_list.txt"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("ОЦЕНКА СТОИМОСТИ NFT ПОДАРКОВ\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Всего подарков: {total_gifts}\n")
        f.write(f"Оценено: {priced_gifts}/{total_gifts}\n\n")
        
        f.write("СТОИМОСТЬ ПО КОЛЛЕКЦИЯМ\n")
        f.write("=" * 70 + "\n\n")
        
        for coll_name, data in sorted_colls:
            count = len(data['gifts'])
            floor = data['floor_price']
            avg = data['avg_price']
            
            if floor > 0:
                value_floor = floor * count
                value_avg = avg * count
                f.write(f"{data['name']} ({coll_name})\n")
                f.write(f"  Кол-во: {count}\n")
                f.write(f"  Floor: {floor:.2f} TON | Средняя: {avg:.2f} TON\n")
                f.write(f"  Стоимость (floor):   {value_floor:.2f} TON\n")
                f.write(f"  Стоимость (средняя): {value_avg:.2f} TON\n\n")
            else:
                f.write(f"{data['name']} ({coll_name})\n")
                f.write(f"  Кол-во: {count}\n")
                f.write(f"  Цена: неизвестна\n\n")
        
        f.write("=" * 70 + "\n")
        f.write("ИТОГО\n")
        f.write("=" * 70 + "\n")
        f.write(f"\nСтоимость (floor):   {grand_total_floor:.2f} TON\n")
        f.write(f"Стоимость (средняя): {grand_total_avg:.2f} TON\n")
        
        if ton_usd > 0:
            f.write(f"\nКурс TON: ~${ton_usd:.2f} USD\n")
            f.write(f"Стоимость (floor):   ~${grand_total_floor * ton_usd:.2f} USD\n")
            f.write(f"Стоимость (средняя): ~${grand_total_avg * ton_usd:.2f} USD\n")
    
    print(f"\n{'=' * 70}")
    print(f"Отчёт сохранён: {filename}")
    print(f"{'=' * 70}")


def main():
    urls = []
    
    # Читаем из stdin или аргументов
    if not sys.stdin.isatty():
        # Читаем из stdin
        urls = [line.strip() for line in sys.stdin if line.strip()]
    elif len(sys.argv) > 1:
        # Читаем из аргументов
        urls = sys.argv[1:]
    else:
        print("Использование:")
        print("  python price_from_list.py < список_ссылок.txt")
        print("  или")
        print("  python price_from_list.py ссылка1 ссылка2 ...")
        return
    
    if not urls:
        print("Список ссылок пуст!")
        return
    
    evaluate_gifts_from_list(urls)


if __name__ == "__main__":
    main()
