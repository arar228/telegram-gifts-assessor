import asyncio
import os
from hydrogram import Client
from hydrogram.raw import functions, types

# --- ВАШИ ДАННЫЕ ---
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
SESSION_NAME = 'my_checker_session'

async def get_user_gifts(app: Client, username: str):
    """
    Получаем подарки через Raw API (напрямую у сервера Telegram).
    """
    print(f"🔄 Получаем профиль пользователя {username}...")
    
    try:
        # 1. Получаем ID пользователя
        peer = await app.resolve_peer(username)
        
        # 2. Формируем запрос
        # В вашей версии Hydrogram этот метод уже должен быть
        request = functions.payments.GetUserStarGifts(
            user_id=peer,
            offset="",
            limit=100
        )
        
        # 3. Отправляем запрос
        result = await app.invoke(request)
        return result.gifts

    except AttributeError:
        print("❌ ОШИБКА: Метод GetUserStarGifts не найден даже в dev-версии.")
        return []
    except Exception as e:
        print(f"❌ Ошибка при запросе: {e}")
        return []

async def main():
    # Инициализация (без лишних плагинов)
    app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)

    print("🚀 Запуск Чекера (Hydrogram Dev)...")
    
    async with app:
        print("✅ Авторизация успешна! (Вы в системе)")
        
        target = input("👤 Введите юзернейм (без @): ").strip().replace('@', '')
        
        if not target:
            print("❌ Юзернейм не может быть пустым.")
            return

        gifts = await get_user_gifts(app, target)
        
        print(f"\n📦 Всего найдено подарков: {len(gifts)}")
        print("=" * 40)
        
        nft_count = 0
        
        for entry in gifts:
            # В Hydrogram структура: entry (UserStarGift) -> field 'gift'
            gift = entry.gift
            
            # Определяем NFT (StarGiftUnique)
            is_nft = isinstance(gift, types.StarGiftUnique)
            
            # Получаем название безопасно
            title = getattr(gift, 'title', 'Подарок')
            
            if is_nft:
                nft_count += 1
                num = getattr(gift, 'num', '?')
                total = getattr(gift, 'availability_total', '?')
                g_id = getattr(gift, 'id', 'N/A')
                slug = getattr(gift, 'slug', '')
                
                print(f"💎 [NFT BLOCKCHAIN] {title}")
                print(f"   ├─ Номер: #{num} из {total}")
                print(f"   ├─ Slug: {slug}")
                print(f"   └─ ID: {g_id}")
            else:
                g_id = getattr(gift, 'id', 'N/A')
                print(f"🔹 [Обычный] ID: {g_id}")
                
        print("=" * 40)
        print(f"📊 ИТОГ: Найдено {nft_count} NFT-подарков.")

if __name__ == "__main__":
    asyncio.run(main())