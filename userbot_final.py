import asyncio
import os
from telethon import TelegramClient
from telethon import functions, types

# --- НАСТРОЙКИ ---
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
SESSION_NAME = 'my_final_session'
# -----------------

async def get_user_gifts(client, username):
    """Метод юзербота для получения подарков"""
    print(f"🔄 Получаю профиль {username}...")
    
    # 1. Находим пользователя
    user = await client.get_entity(username)
    
    # 2. Делаем запрос (метод из нового слоя API)
    # Так как мы обновились через .bat, этот метод теперь существует
    req = functions.payments.GetUserStarGiftsRequest(
        user_id=user.id,
        offset=0,
        limit=100
    )
    
    # 3. Получаем результат
    result = await client(req)
    return result.gifts

async def main():
    print("🚀 Запуск Юзербота...")
    
    # Подключаемся
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        print("✅ Юзербот в сети!")
        
        target = input("👤 Введите юзернейм (без @): ").strip().replace('@', '')
        
        try:
            gifts = await get_user_gifts(client, target)
            
            print(f"\n📦 Всего подарков: {len(gifts)}")
            print("=" * 40)
            
            nft_count = 0
            for entry in gifts:
                # В Telethon структура может быть entry.gift
                # или entry (если это старый слой, но мы обновились)
                gift = getattr(entry, 'gift', entry)
                
                # Проверяем тип: StarGiftUnique = NFT
                is_nft = isinstance(gift, types.StarGiftUnique)
                
                # Доп. проверка (иногда Telethon помечает их иначе)
                if not is_nft and hasattr(gift, 'slug') and gift.slug:
                    is_nft = True

                if is_nft:
                    nft_count += 1
                    title = getattr(gift, 'title', 'Подарок')
                    num = getattr(gift, 'num', '?')
                    total = getattr(gift, 'availability_total', '?')
                    print(f"💎 [NFT] {title} | #{num} из {total}")
                else:
                    g_id = getattr(gift, 'id', 'N/A')
                    print(f"🔹 [Обычный] ID: {g_id}")
            
            print("=" * 40)
            print(f"📊 Найдено {nft_count} NFT на блокчейне.")

        except AttributeError as e:
            print(f"❌ ОШИБКА: {e}")
            print("⚠️ Похоже, обновление через .bat файл не сработало.")
        except Exception as e:
            print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main())