"""
Тест для получения списка подарков пользователя Telegram.

3 категории подарков:
  1. Не улучшенные (StarGift) — обычные подарки за звёзды
  2. Улучшенные, НЕ на блокчейне (StarGiftUnique, gift_address=None)
  3. Улучшенные, НА блокчейне TON (StarGiftUnique, gift_address заполнен)

Используется метод payments.GetSavedStarGiftsRequest (Telethon 1.42.0)
"""
import asyncio
import os
import sys
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Фикс кодировки для Windows (cp1251 не поддерживает эмодзи)
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from telethon import TelegramClient
from telethon.tl.functions.payments import GetSavedStarGiftsRequest
from telethon.tl import types
from telethon.errors import UsernameNotOccupiedError, UserIdInvalidError

# Загружаем переменные окружения
load_dotenv()

API_ID = int(os.getenv('API_ID', '21192413'))
API_HASH = os.getenv('API_HASH', '2d7b04c4c7d7b93826277d37c9e4e2e4')
PHONE_NUMBER = os.getenv('PHONE_NUMBER', '').strip()

SESSION_NAME = 'gifts_session'


class TelegramGiftsTest:
    """Класс для получения и анализа подарков пользователя Telegram"""
    
    def __init__(self):
        self.client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    async def connect(self):
        """Подключение к Telegram"""
        try:
            if PHONE_NUMBER:
                await self.client.start(phone=PHONE_NUMBER)
            else:
                await self.client.start()
            
            me = await self.client.get_me()
            print(f"✅ Подключено к Telegram как: {me.first_name} (ID: {me.id})")
        except ValueError as e:
            if 'No phone number' in str(e):
                print("❌ Ошибка: Не указан номер телефона и нет сохраненной сессии")
                print("   Решение: Создайте .env с PHONE_NUMBER или авторизуйтесь вручную")
                raise
            else:
                raise
    
    async def get_user_by_username(self, username: str):
        """Получение пользователя по username"""
        try:
            username = username.lstrip('@')
            user = await self.client.get_entity(username)
            return user
        except UsernameNotOccupiedError:
            print(f"❌ Пользователь @{username} не найден")
            return None
        except Exception as e:
            print(f"❌ Ошибка при получении пользователя: {e}")
            return None
    
    async def get_user_by_id(self, user_id: int):
        """Получение пользователя по ID"""
        try:
            user = await self.client.get_entity(user_id)
            return user
        except (ValueError, UserIdInvalidError) as e:
            print(f"❌ Пользователь с ID {user_id} не найден: {e}")
            print("   💡 Попробуйте использовать username вместо ID")
            return None
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return None
    
    async def get_user_gifts(self, user_id: Optional[int] = None, 
                            username: Optional[str] = None) -> List[Dict]:
        """
        Получение ВСЕХ подарков пользователя с пагинацией.
        
        Использует payments.GetSavedStarGiftsRequest — правильный метод
        для Telethon 1.42.0 (вместо несуществующего GetUserStarGiftsRequest)
        """
        # 1. Получаем пользователя
        user = None
        if username:
            user = await self.get_user_by_username(username)
        elif user_id:
            user = await self.get_user_by_id(user_id)
        else:
            print("❌ Укажите user_id или username")
            return []
        
        if not user:
            return []
        
        first_name = getattr(user, 'first_name', '') or ''
        last_name = getattr(user, 'last_name', '') or ''
        uname = getattr(user, 'username', '') or ''
        
        print(f"\n📋 Пользователь: {first_name} {last_name}")
        print(f"   ID: {user.id}")
        print(f"   Username: @{uname}")
        
        # 2. Получаем подарки через GetSavedStarGiftsRequest с пагинацией
        all_gifts = []
        offset = ""  # Первая страница — пустая строка
        limit = 100
        page = 1
        
        print(f"\n🔍 Получение подарков через GetSavedStarGiftsRequest...")
        
        while True:
            try:
                result = await self.client(GetSavedStarGiftsRequest(
                    peer=user,
                    offset=offset,
                    limit=limit
                ))
                
                if not result or not hasattr(result, 'gifts') or not result.gifts:
                    if page == 1:
                        print("   ⚠️ Подарки не найдены (возможно, скрыты настройками приватности)")
                    break
                
                batch_size = len(result.gifts)
                print(f"   📦 Страница {page}: получено {batch_size} подарков")
                
                # Парсим каждый подарок
                for entry in result.gifts:
                    gift_data = self._parse_saved_star_gift(entry, user)
                    if gift_data:
                        all_gifts.append(gift_data)
                
                # Проверяем, есть ли ещё страницы
                # В SavedStarGifts есть next_offset для пагинации
                next_offset = getattr(result, 'next_offset', None)
                
                if next_offset and batch_size >= limit:
                    offset = next_offset
                    page += 1
                    await asyncio.sleep(0.3)  # Задержка от rate limiting
                else:
                    break
                    
            except Exception as e:
                print(f"   ❌ Ошибка при получении подарков (стр. {page}): {e}")
                import traceback
                traceback.print_exc()
                break
        
        print(f"\n📦 Всего получено подарков: {len(all_gifts)}")
        return all_gifts
    
    def _parse_saved_star_gift(self, entry, user) -> Optional[Dict]:
        """
        Парсинг объекта SavedStarGift в словарь.
        
        entry.gift может быть:
        - types.StarGift — не улучшенный подарок (категория 1)
        - types.StarGiftUnique с gift_address=None — улучшенный, НЕ на блокчейне (категория 2)
        - types.StarGiftUnique с gift_address — улучшенный, НА блокчейне TON (категория 3)
        """
        try:
            gift_obj = getattr(entry, 'gift', None)
            if not gift_obj:
                return None
            
            is_unique = isinstance(gift_obj, types.StarGiftUnique)
            
            # Ключевое поле: gift_address определяет, есть ли подарок на блокчейне
            gift_address = None
            if is_unique:
                gift_address = getattr(gift_obj, 'gift_address', None)
            
            # Определяем категорию
            if not is_unique:
                category = 'regular'           # 1. Не улучшенный (StarGift)
            elif gift_address:
                category = 'on_blockchain'      # 3. Улучшенный, НА блокчейне TON
            else:
                category = 'upgraded_no_chain'  # 2. Улучшенный, НЕ на блокчейне
            
            gift_data = {
                'id': getattr(gift_obj, 'id', None),
                'category': category,
                'is_unique': is_unique,
                'is_on_blockchain': category == 'on_blockchain',
                'gift_address': str(gift_address) if gift_address else None,
                'owner': getattr(user, 'username', '') or f"user_{user.id}",
                'owner_id': user.id,
                'date': getattr(entry, 'date', None),
                'saved_id': getattr(entry, 'saved_id', None),
                'msg_id': getattr(entry, 'msg_id', None),
                'name_hidden': getattr(entry, 'name_hidden', False),
                'pinned_to_top': getattr(entry, 'pinned_to_top', False),
            }
            
            # Получаем отправителя
            from_id = getattr(entry, 'from_id', None)
            if from_id:
                gift_data['from_id'] = getattr(from_id, 'user_id', 
                                      getattr(from_id, 'channel_id', 
                                      getattr(from_id, 'chat_id', None)))
            
            # Получаем сообщение
            message = getattr(entry, 'message', None)
            if message and hasattr(message, 'text'):
                gift_data['message'] = message.text
            
            if is_unique:
                # StarGiftUnique — улучшенный подарок (может быть или не быть на блокчейне)
                gift_data['title'] = getattr(gift_obj, 'title', 'Unknown NFT')
                gift_data['slug'] = getattr(gift_obj, 'slug', '')
                gift_data['num'] = getattr(gift_obj, 'num', '?')
                gift_data['availability_total'] = getattr(gift_obj, 'availability_total', '?')
                gift_data['name'] = gift_data['title']
                gift_data['nft_url'] = f"https://t.me/nft/{gift_data['slug']}" if gift_data['slug'] else None
                
                # Атрибуты NFT
                attributes = getattr(gift_obj, 'attributes', [])
                if attributes:
                    gift_data['attributes'] = []
                    for attr in attributes:
                        attr_info = {
                            'type': type(attr).__name__,
                            'name': getattr(attr, 'name', ''),
                        }
                        gift_data['attributes'].append(attr_info)
                
                # Стоимость и трансфер
                gift_data['transfer_stars'] = getattr(entry, 'transfer_stars', None)
                gift_data['can_export_at'] = getattr(entry, 'can_export_at', None)
                gift_data['can_transfer_at'] = getattr(entry, 'can_transfer_at', None)
                gift_data['can_resell_at'] = getattr(entry, 'can_resell_at', None)
                
                # Адрес владельца на блокчейне
                owner_address = getattr(gift_obj, 'owner_address', None)
                if owner_address:
                    gift_data['owner_address'] = str(owner_address)
            else:
                # Обычный подарок (StarGift) — не улучшенный
                gift_data['name'] = f"StarGift #{getattr(gift_obj, 'id', 'N/A')}"
                gift_data['convert_stars'] = getattr(entry, 'convert_stars', None)
                gift_data['upgrade_stars'] = getattr(entry, 'upgrade_stars', None)
                gift_data['can_upgrade'] = getattr(entry, 'can_upgrade', False)
            
            return gift_data
            
        except Exception as e:
            print(f"      ⚠️ Ошибка парсинга подарка: {e}")
            return None
    
    def filter_by_category(self, gifts: List[Dict], category: str) -> List[Dict]:
        """Фильтрация подарков по категории: 'regular', 'upgraded_no_chain', 'on_blockchain'"""
        return [g for g in gifts if g.get('category') == category]
    
    def get_gifts_statistics(self, gifts: List[Dict]) -> Dict:
        """Статистика по 3 категориям подарков"""
        regular = [g for g in gifts if g.get('category') == 'regular']
        upgraded_no_chain = [g for g in gifts if g.get('category') == 'upgraded_no_chain']
        on_blockchain = [g for g in gifts if g.get('category') == 'on_blockchain']
        
        return {
            'total_gifts': len(gifts),
            'regular': len(regular),
            'upgraded_no_chain': len(upgraded_no_chain),
            'on_blockchain': len(on_blockchain),
            'pinned': len([g for g in gifts if g.get('pinned_to_top')]),
            'hidden_sender': len([g for g in gifts if g.get('name_hidden')]),
        }
    
    async def disconnect(self):
        """Отключение"""
        await self.client.disconnect()
        print("\n✅ Отключено от Telegram")


async def run_gift_check(user_id: Optional[int] = None, username: Optional[str] = None):
    """Запуск проверки подарков"""
    tester = TelegramGiftsTest()
    
    try:
        await tester.connect()
        
        # Получаем все подарки
        gifts = await tester.get_user_gifts(user_id=user_id, username=username)
        
        if not gifts:
            print("\n📭 Подарки не найдены")
            return
        
        # Статистика
        stats = tester.get_gifts_statistics(gifts)
        
        # 3 категории
        regular = tester.filter_by_category(gifts, 'regular')
        upgraded_no_chain = tester.filter_by_category(gifts, 'upgraded_no_chain')
        on_blockchain = tester.filter_by_category(gifts, 'on_blockchain')
        
        print("\n" + "=" * 60)
        print("СТАТИСТИКА ПОДАРКОВ (3 категории)")
        print("=" * 60)
        print(f"   Всего подарков:                           {stats['total_gifts']}")
        print(f"   1. Не улучшенные (StarGift):              {stats['regular']}")
        print(f"   2. Улучшенные, НЕ на блокчейне:           {stats['upgraded_no_chain']}")
        print(f"   3. Улучшенные, НА блокчейне (TON):        {stats['on_blockchain']}")
        print(f"   Закрепленные:                             {stats['pinned']}")
        print(f"   Скрытый отправитель:                      {stats['hidden_sender']}")
        
        # Сохраняем файл с 3 секциями
        target_name = username or str(user_id)
        filename = f"gifts_{target_name}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Подарки пользователя @{target_name}\n")
            f.write(f"Всего: {stats['total_gifts']}\n")
            f.write(f"  1. Не улучшенные:              {stats['regular']}\n")
            f.write(f"  2. Улучшенные, НЕ на блокчейне: {stats['upgraded_no_chain']}\n")
            f.write(f"  3. Улучшенные, НА блокчейне:    {stats['on_blockchain']}\n")
            f.write("=" * 60 + "\n\n")
            
            # === СЕКЦИЯ 1: НА БЛОКЧЕЙНЕ TON ===
            f.write("=== НА БЛОКЧЕЙНЕ TON (улучшенные, экспортированы) ===\n\n")
            if on_blockchain:
                for i, gift in enumerate(on_blockchain, 1):
                    title = gift.get('title', gift.get('name', 'Unknown'))
                    num = gift.get('num', '?')
                    total = gift.get('availability_total', '?')
                    nft_url = gift.get('nft_url', '')
                    gift_addr = gift.get('gift_address', '')
                    
                    f.write(f"{i}) {title} #{num}/{total}\n")
                    if nft_url:
                        f.write(f"   NFT: {nft_url}\n")
                    if gift_addr:
                        f.write(f"   TON: https://tonviewer.com/{gift_addr}\n")
                    
                    attrs = gift.get('attributes', [])
                    if attrs:
                        attr_names = [a.get('name', '') for a in attrs if a.get('name')]
                        if attr_names:
                            f.write(f"   Атрибуты: {', '.join(attr_names)}\n")
                    f.write("\n")
            else:
                f.write("   Подарков на блокчейне не найдено.\n\n")
            
            f.write("=" * 60 + "\n")
            
            # === СЕКЦИЯ 2: УЛУЧШЕННЫЕ, НЕ НА БЛОКЧЕЙНЕ ===
            f.write("=== УЛУЧШЕННЫЕ, НЕ НА БЛОКЧЕЙНЕ ===\n\n")
            if upgraded_no_chain:
                for i, gift in enumerate(upgraded_no_chain, 1):
                    title = gift.get('title', gift.get('name', 'Unknown'))
                    num = gift.get('num', '?')
                    total = gift.get('availability_total', '?')
                    nft_url = gift.get('nft_url', '')
                    
                    f.write(f"{i}) {title} #{num}/{total}\n")
                    if nft_url:
                        f.write(f"   Ссылка: {nft_url}\n")
                    f.write("\n")
            else:
                f.write("   Улучшенных подарков вне блокчейна не найдено.\n\n")
            
            f.write("=" * 60 + "\n")
            
            # === СЕКЦИЯ 3: НЕ УЛУЧШЕННЫЕ ===
            f.write("=== НЕ УЛУЧШЕННЫЕ (обычные StarGift) ===\n\n")
            if regular:
                for i, gift in enumerate(regular, 1):
                    gift_id = gift.get('id', 'N/A')
                    can_upgrade = gift.get('can_upgrade', False)
                    upgrade_note = " (можно улучшить)" if can_upgrade else ""
                    f.write(f"{i}) StarGift #{gift_id}{upgrade_note}\n")
                f.write("\n")
            else:
                f.write("   Обычных подарков не найдено.\n\n")
        
        print(f"\n📄 Файл сохранен: {filename}")
        print(f"   Категория 3 (на блокчейне): {len(on_blockchain)} подарков с NFT + TON ссылками")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await tester.disconnect()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        target = sys.argv[1]
        if target.startswith('@'):
            asyncio.run(run_gift_check(username=target.lstrip('@')))
        elif target.isdigit():
            asyncio.run(run_gift_check(user_id=int(target)))
        else:
            asyncio.run(run_gift_check(username=target))
    else:
        target = input("👤 Введите юзернейм или ID: ").strip()
        if target.startswith('@'):
            asyncio.run(run_gift_check(username=target.lstrip('@')))
        elif target.isdigit():
            asyncio.run(run_gift_check(user_id=int(target)))
        else:
            asyncio.run(run_gift_check(username=target))
