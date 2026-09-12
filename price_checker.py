"""
Оценка стоимости подарков Telegram через tonapi.io

Алгоритм:
1. Получаем ВСЕ подарки пользователя через Telegram API
2. Группируем улучшенные подарки по коллекциям (title)
3. Для коллекций с подарками НА блокчейне — берём адрес коллекции через tonapi.io
4. Для каждой коллекции получаем floor price (минимальная цена продажи)
5. Считаем общую стоимость портфеля
"""
import asyncio
import os
import sys
import time
import requests
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from dotenv import load_dotenv

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

from telethon import TelegramClient
from telethon.tl.functions.payments import GetSavedStarGiftsRequest
from telethon.tl import types
from telethon.errors import UsernameNotOccupiedError

from credentials_config import load_telegram_credentials

API_ID, API_HASH = load_telegram_credentials()
PHONE_NUMBER = os.getenv('PHONE_NUMBER', '').strip()
SESSION_NAME = 'gifts_session'

TONAPI_BASE = "https://tonapi.io/v2"


# ==================== tonapi.io ====================

def tonapi_get_nft(address: str) -> Optional[Dict]:
    """Получить информацию о NFT по адресу контракта"""
    try:
        resp = requests.get(
            f"{TONAPI_BASE}/nfts/{address}",
            headers={"Accept": "application/json"},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def tonapi_get_collection_floor(collection_address: str) -> Tuple[float, float, int]:
    """
    Получить floor price коллекции через список предметов на продаже.
    Возвращает: (floor_price, avg_price, count_on_sale)
    """
    try:
        resp = requests.get(
            f"{TONAPI_BASE}/nfts/collections/{collection_address}/items",
            headers={"Accept": "application/json"},
            params={"limit": 100, "offset": 0},
            timeout=15
        )
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


# ==================== Telegram ====================

async def get_all_gifts(client, username: str) -> List[Dict]:
    """Получить ВСЕ подарки пользователя"""
    user = await client.get_entity(username)
    all_gifts = []
    offset = ""
    page = 1
    
    print(f"Получение подарков @{username}...")
    
    while True:
        result = await client(GetSavedStarGiftsRequest(
            peer=user, offset=offset, limit=100
        ))
        
        if not result or not result.gifts:
            break
        
        for entry in result.gifts:
            gift_obj = entry.gift
            is_unique = isinstance(gift_obj, types.StarGiftUnique)
            
            # Пропускаем не улучшенные подарки (StarGift) - они не NFT и не имеют цены
            if not is_unique:
                continue
            
            gift_address = getattr(gift_obj, 'gift_address', None)
            
            gift_data = {
                'is_unique': True,
                'gift_address': str(gift_address) if gift_address else None,
            }
            
            gift_data['title'] = getattr(gift_obj, 'title', 'Unknown')
            gift_data['slug'] = getattr(gift_obj, 'slug', '')
            gift_data['num'] = getattr(gift_obj, 'num', '?')
            gift_data['total'] = getattr(gift_obj, 'availability_total', '?')
            gift_data['nft_url'] = f"https://t.me/nft/{gift_data['slug']}" if gift_data['slug'] else None
            
            if gift_address:
                gift_data['category'] = 'on_blockchain'
            else:
                gift_data['category'] = 'upgraded_no_chain'
            
            # Атрибуты
            attrs = getattr(gift_obj, 'attributes', [])
            gift_data['attributes'] = [getattr(a, 'name', '') for a in attrs if getattr(a, 'name', '')]
        
            all_gifts.append(gift_data)
        
        print(f"  Страница {page}: +{len(result.gifts)} (всего: {len(all_gifts)})")
        
        next_offset = getattr(result, 'next_offset', None)
        if next_offset and len(result.gifts) >= 100:
            offset = next_offset
            page += 1
            await asyncio.sleep(0.3)
        else:
            break
    
    return all_gifts


# ==================== Оценка стоимости ====================

def evaluate_portfolio(gifts: List[Dict]) -> Dict:
    """
    Оценка стоимости портфеля подарков.
    
    1. Группируем улучшенные подарки по коллекциям
    2. Для каждой коллекции получаем floor price через tonapi.io
    3. Считаем общую стоимость
    """
    # Группируем по коллекциям (только улучшенные подарки)
    collections = defaultdict(lambda: {
        'on_chain': [],
        'off_chain': [],
        'collection_address': None,
        'floor_price': 0.0,
        'avg_price': 0.0,
        'on_sale_count': 0,
    })
    
    for gift in gifts:
        title = gift.get('title', 'Unknown')
        if gift['category'] == 'on_blockchain':
            collections[title]['on_chain'].append(gift)
        else:
            collections[title]['off_chain'].append(gift)
    
    # Для каждой коллекции получаем адрес через tonapi.io
    print(f"\nПолучение цен для {len(collections)} коллекций через tonapi.io...")
    
    for coll_name, coll_data in collections.items():
        # Берём первый подарок с gift_address для определения коллекции
        sample_addr = None
        for gift in coll_data['on_chain']:
            if gift.get('gift_address'):
                sample_addr = gift['gift_address']
                break
        
        if sample_addr:
            # Получаем адрес коллекции через NFT
            nft_info = tonapi_get_nft(sample_addr)
            if nft_info:
                coll_addr = nft_info.get('collection', {}).get('address', '')
                if coll_addr:
                    coll_data['collection_address'] = coll_addr
                    
                    # Получаем floor price
                    floor, avg, count = tonapi_get_collection_floor(coll_addr)
                    coll_data['floor_price'] = floor
                    coll_data['avg_price'] = avg
                    coll_data['on_sale_count'] = count
                    
                    total_in_coll = len(coll_data['on_chain']) + len(coll_data['off_chain'])
                    print(f"  {coll_name}: floor={floor:.2f} TON, avg={avg:.2f} TON "
                          f"({total_in_coll} шт., на продаже: {count})")
            time.sleep(0.4)  # Rate limiting
        else:
            # Нет подарков на блокчейне — пробуем найти коллекцию по slug
            # Берём slug из off_chain подарков
            sample_slug = None
            for gift in coll_data['off_chain']:
                slug = gift.get('slug', '')
                if slug:
                    sample_slug = slug
                    break
            
            if sample_slug:
                # Пробуем найти коллекцию, конвертируя slug в поисковый запрос
                total_in_coll = len(coll_data['off_chain'])
                print(f"  {coll_name}: НЕТ подарков на блокчейне ({total_in_coll} шт.) - цена неизвестна")
    
    return {
        'collections': dict(collections),
    }


def print_report(portfolio: Dict, username: str):
    """Вывод отчёта и сохранение в файл"""
    collections = portfolio['collections']
    
    lines = []
    
    def out(text=""):
        lines.append(text)
        print(text)
    
    out("=" * 70)
    out(f"  ОЦЕНКА СТОИМОСТИ ПОДАРКОВ @{username}")
    out("=" * 70)
    
    # Подсчёт (только улучшенные подарки)
    total_on_chain = sum(len(c['on_chain']) for c in collections.values())
    total_off_chain = sum(len(c['off_chain']) for c in collections.values())
    total_improved = total_on_chain + total_off_chain
    
    out(f"\n  Всего улучшенных подарков: {total_improved}")
    out(f"  1. Улучшенные, НЕ на блокчейне:    {total_off_chain}")
    out(f"  2. Улучшенные, НА блокчейне (TON):  {total_on_chain}")
    
    # Стоимость по коллекциям
    out(f"\n{'=' * 70}")
    out(f"  СТОИМОСТЬ ПО КОЛЛЕКЦИЯМ (floor price)")
    out(f"{'=' * 70}")
    
    grand_total_floor = 0.0
    grand_total_avg = 0.0
    
    # Сортируем коллекции: сначала те, у которых есть цена
    sorted_colls = sorted(
        collections.items(),
        key=lambda x: (x[1]['floor_price'] == 0, -len(x[1]['on_chain']) - len(x[1]['off_chain']))
    )
    
    for coll_name, coll_data in sorted_colls:
        count_on = len(coll_data['on_chain'])
        count_off = len(coll_data['off_chain'])
        count_total = count_on + count_off
        floor = coll_data['floor_price']
        avg = coll_data['avg_price']
        
        if floor > 0:
            value_floor = floor * count_total
            value_avg = avg * count_total
            grand_total_floor += value_floor
            grand_total_avg += value_avg
            
            out(f"\n  {coll_name}")
            out(f"    Кол-во: {count_total} (на блокчейне: {count_on}, вне: {count_off})")
            out(f"    Floor: {floor:.2f} TON | Средняя: {avg:.2f} TON")
            out(f"    Стоимость (floor):   {value_floor:.2f} TON")
            out(f"    Стоимость (средняя): {value_avg:.2f} TON")
            
            # Список подарков этой коллекции
            all_in_coll = coll_data['on_chain'] + coll_data['off_chain']
            for i, g in enumerate(all_in_coll, 1):
                slug = g.get('slug', '')
                chain_mark = "[TON]" if g.get('gift_address') else "[---]"
                attrs = g.get('attributes', [])
                attr_str = f" ({', '.join(attrs)})" if attrs else ""
                out(f"      {i}) {chain_mark} t.me/nft/{slug}{attr_str}")
        else:
            out(f"\n  {coll_name}")
            out(f"    Кол-во: {count_total} (на блокчейне: {count_on}, вне: {count_off})")
            out(f"    Цена: неизвестна (нет на блокчейне для оценки)")
    
    # Итого
    out(f"\n{'=' * 70}")
    out(f"  ИТОГО")
    out(f"{'=' * 70}")
    
    priced_collections = sum(1 for c in collections.values() if c['floor_price'] > 0)
    priced_gifts = sum(
        len(c['on_chain']) + len(c['off_chain'])
        for c in collections.values() if c['floor_price'] > 0
    )
    unpriced_gifts = total_on_chain + total_off_chain - priced_gifts
    
    out(f"\n  Оценено коллекций:  {priced_collections}/{len(collections)}")
    out(f"  Оценено подарков:   {priced_gifts}/{total_on_chain + total_off_chain}")
    out(f"  Не оценено:         {unpriced_gifts} подарков (нет данных на блокчейне)")
    out(f"\n  Стоимость (по floor price):   {grand_total_floor:.2f} TON")
    out(f"  Стоимость (по средней цене):  {grand_total_avg:.2f} TON")
    
    # Конвертация в USD (примерный курс)
    try:
        ton_usd = get_ton_price_usd()
        if ton_usd > 0:
            out(f"\n  Курс TON: ~${ton_usd:.2f} USD")
            out(f"  Стоимость (floor):   ~${grand_total_floor * ton_usd:.2f} USD")
            out(f"  Стоимость (средняя): ~${grand_total_avg * ton_usd:.2f} USD")
    except Exception:
        pass
    
    out(f"\n  * Floor price — минимальная цена, по которой продаётся подарок")
    out(f"    этой коллекции на маркетплейсах прямо сейчас.")
    out(f"  * Реальная цена зависит от атрибутов (модель, фон, символ).")
    
    # Сохраняем в файл
    filename = f"portfolio_{username}.txt"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"\n{'=' * 70}")
    print(f"  Отчёт сохранён: {filename}")
    print(f"{'=' * 70}")


def get_ton_price_usd() -> float:
    """Получить текущий курс TON в USD"""
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


# ==================== Main ====================

async def main():
    target = None
    
    if len(sys.argv) > 1:
        target = sys.argv[1].lstrip('@')
    else:
        target = input("Username: ").strip().lstrip('@')
    
    if not target:
        print("Укажите username!")
        return
    
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    try:
        if PHONE_NUMBER:
            await client.start(phone=PHONE_NUMBER)
        else:
            await client.start()
        
        me = await client.get_me()
        print(f"Подключено как: {me.first_name} (ID: {me.id})\n")
        
        # 1. Получаем все улучшенные подарки (StarGiftUnique)
        gifts = await get_all_gifts(client, target)
        print(f"\nВсего получено улучшенных подарков: {len(gifts)}")
        
        # 2. Оцениваем стоимость
        portfolio = evaluate_portfolio(gifts)
        
        # 3. Выводим отчёт
        print_report(portfolio, target)
        
    except Exception as e:
        print(f"\nОшибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
