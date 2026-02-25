"""
Оценка стоимости NFT подарков через Getgems GraphQL API

Использование:
  python price_getgems.py < gifts_list.txt
"""
import sys
import requests
import time
import json
from typing import Dict, List, Tuple
from collections import defaultdict

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

GETGEMS_GRAPHQL = "https://api.getgems.io/graphql"


def parse_slug_from_url(url: str) -> Tuple[str, str]:
    """Парсит slug из URL вида t.me/nft/CollectionName-ID"""
    url = url.strip()
    if url.startswith('http'):
        url = url.split('//', 1)[1] if '//' in url else url
    if url.startswith('t.me/nft/'):
        slug = url.replace('t.me/nft/', '')
    elif url.startswith('@'):
        slug = url[1:]
    else:
        slug = url
    
    parts = slug.split('-', 1)
    if len(parts) == 2:
        collection_name = parts[0]
        return collection_name, slug
    return slug, slug


def getgems_search_collection(query: str) -> List[Dict]:
    """Поиск коллекции через Getgems GraphQL"""
    query_gql = """
    query SearchCollections($query: String!) {
      nftCollections(query: $query, limit: 10) {
        address
        name
        approximateFloorPrice
      }
    }
    """
    
    try:
        resp = requests.post(
            GETGEMS_GRAPHQL,
            json={
                'query': query_gql,
                'variables': {'query': query}
            },
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if 'data' in data and 'nftCollections' in data['data']:
                return data['data']['nftCollections']
            elif 'errors' in data:
                # Пробуем другой запрос
                return getgems_search_nft(query)
    except Exception as e:
        print(f"  Ошибка Getgems API: {e}")
    
    return []


def getgems_search_nft(query: str) -> List[Dict]:
    """Поиск NFT через Getgems GraphQL"""
    query_gql = """
    query SearchNFTs($query: String!) {
      nftItems(query: $query, limit: 10) {
        address
        name
        collection {
          address
          name
          approximateFloorPrice
        }
        sale {
          fullPrice
        }
      }
    }
    """
    
    try:
        resp = requests.post(
            GETGEMS_GRAPHQL,
            json={
                'query': query_gql,
                'variables': {'query': query}
            },
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if 'data' in data and 'nftItems' in data['data']:
                items = data['data']['nftItems']
                collections = {}
                for item in items:
                    coll = item.get('collection')
                    if coll and coll.get('address'):
                        coll_addr = coll['address']
                        if coll_addr not in collections:
                            collections[coll_addr] = {
                                'address': coll_addr,
                                'name': coll.get('name', ''),
                                'approximateFloorPrice': coll.get('approximateFloorPrice', 0),
                            }
                return list(collections.values())
            elif 'errors' in data:
                print(f"    Getgems ошибка: {json.dumps(data['errors'], ensure_ascii=False)[:200]}")
    except Exception as e:
        print(f"  Ошибка: {e}")
    
    return []


def getgems_get_collection_floor(collection_address: str) -> Tuple[float, float, int]:
    """Получить floor price коллекции через Getgems"""
    query_gql = """
    query GetCollection($address: String!) {
      nftCollection(address: $address) {
        approximateFloorPrice
        nftItems(limit: 100, onSale: true) {
          sale {
            fullPrice
          }
        }
      }
    }
    """
    
    try:
        resp = requests.post(
            GETGEMS_GRAPHQL,
            json={
                'query': query_gql,
                'variables': {'address': collection_address}
            },
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if 'data' in data and 'nftCollection' in data['data']:
                coll = data['data']['nftCollection']
                floor = coll.get('approximateFloorPrice', 0)
                
                items = coll.get('nftItems', [])
                prices = []
                for item in items:
                    sale = item.get('sale')
                    if sale and sale.get('fullPrice'):
                        price_val = int(sale['fullPrice']) / 1e9
                        if price_val > 0:
                            prices.append(price_val)
                
                if prices:
                    return min(prices), sum(prices) / len(prices), len(prices)
                elif floor > 0:
                    return floor / 1e9, floor / 1e9, 0
    except Exception as e:
        print(f"    Ошибка получения floor: {e}")
    
    return 0.0, 0.0, 0


def get_ton_price_usd() -> float:
    """Получить курс TON в USD"""
    try:
        resp = requests.get(
            "https://tonapi.io/v2/rates?tokens=ton&currencies=usd",
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
    """Оценка стоимости подарков по списку ссылок через Getgems"""
    
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
    
    # 2. Для каждой коллекции ищем через Getgems
    print("Поиск цен через Getgems GraphQL API...")
    print("=" * 70)
    
    collection_data = {}
    
    for coll_name, gifts in collections.items():
        print(f"\n{coll_name} ({len(gifts)} подарков)")
        
        # Пробуем разные варианты поиска
        search_queries = [
            coll_name,
            coll_name.replace('_', ' '),
            coll_name.replace('_', ''),
        ]
        
        found = False
        for search_query in search_queries:
            # Ищем коллекцию
            search_results = getgems_search_collection(search_query)
            
            if search_results:
                # Берём первую найденную коллекцию
                coll_info = search_results[0]
                coll_addr = coll_info.get('address', '')
                coll_display_name = coll_info.get('name', coll_name)
                
                if coll_addr:
                    print(f"  Найдена коллекция: {coll_display_name}")
                    print(f"  Адрес: {coll_addr[:30]}...")
                    
                    # Получаем floor price
                    floor, avg, count = getgems_get_collection_floor(coll_addr)
                    
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
                        # Используем approximateFloorPrice из поиска
                        approx_floor = coll_info.get('approximateFloorPrice', 0)
                        if approx_floor > 0:
                            floor_val = approx_floor / 1e9
                            collection_data[coll_name] = {
                                'name': coll_display_name,
                                'address': coll_addr,
                                'floor_price': floor_val,
                                'avg_price': floor_val,
                                'on_sale_count': 0,
                                'gifts': gifts,
                            }
                            print(f"  Floor (приблизительно): {floor_val:.2f} TON")
                        else:
                            print(f"  Цена: не найдена")
                            collection_data[coll_name] = {
                                'name': coll_display_name,
                                'address': coll_addr,
                                'floor_price': 0.0,
                                'avg_price': 0.0,
                                'on_sale_count': 0,
                                'gifts': gifts,
                            }
                    found = True
                    break
        
        if not found:
            print(f"  Коллекция не найдена в Getgems")
            collection_data[coll_name] = {
                'name': coll_name,
                'address': None,
                'floor_price': 0.0,
                'avg_price': 0.0,
                'on_sale_count': 0,
                'gifts': gifts,
            }
        
        time.sleep(0.3)  # Rate limiting
    
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
    filename = "portfolio_getgems.txt"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("ОЦЕНКА СТОИМОСТИ NFT ПОДАРКОВ (Getgems API)\n")
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
    
    if not sys.stdin.isatty():
        urls = [line.strip() for line in sys.stdin if line.strip()]
    elif len(sys.argv) > 1:
        urls = sys.argv[1:]
    else:
        print("Использование:")
        print("  python price_getgems.py < gifts_list.txt")
        return
    
    if not urls:
        print("Список ссылок пуст!")
        return
    
    evaluate_gifts_from_list(urls)


if __name__ == "__main__":
    main()
