import asyncio
import os
from hydrogram import Client
from hydrogram.raw import functions, types

# --- НАСТРОЙКИ ВАШЕГО ЮЗЕРБОТА ---
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
SESSION_NAME = 'my_userbot'
# ---------------------------------

async def get_gifts(app: Client, username: str):
    """
    Метод для получения подарков.
    Работает через Raw API (низкоуровневые запросы).
    """
    print(f"🔄 [Метод] Получаю данные профиля {username}...")
    
    try:
        # 1. Превращаем юзернейм в объект Peer (ID и Hash)
        peer = await app.resolve_peer(username)
        
        # 2. Формируем прямой запрос к API Telegram
        # Мы "руками" собираем пакет для отправки на сервер
        req = functions.payments.GetUserStarGifts(
            user_id=peer,
            offset="",
            limit=100
        )
        
        # 3. Отправляем (Invoke)
        result = await app.invoke(req)
        
        return result.gifts

    except Exception as e:
        print(f"❌ Ошибка в методе: {e}")
        return []

async def main():
    # Инициализация Юзербота
    # (Мы не используем tgcrypto, бот будет работать в чистом Python режиме)
    app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)

    print("🚀 Запуск Юзербота...")
    
    async with app:
        print("✅ Юзербот авторизован!")
        
        # --- Использование нашего метода ---
        target_user = input("👤 Введите юзернейм (без @): ").strip().replace('@', '')
        
        # Вызываем наш метод
        gifts = await get_gifts(app, target_user)
        
        print(f"\n📦 Получено подарков: {len(gifts)}")
        print("=" * 40)
        
        nft_count = 0
        
        for entry in gifts:
            # Внутри entry лежит сам подарок (gift)
            gift = entry.gift
            
            # Проверяем тип: StarGiftUnique = NFT на блокчейне
            is_nft = isinstance(gift, types.StarGiftUnique)
            
            if is_nft:
                nft_count += 1
                # Безопасно достаем атрибуты (через getattr, чтобы не упало при смене API)
                title = getattr(gift, 'title', 'Неизвестный NFT')
                num = getattr(gift, 'num', '?')
                total = getattr(gift, 'availability_total', '?')
                print(f"💎 [NFT BLOCKCHAIN] {title} | #{num} из {total}")
            else:
                # Обычный подарок
                print(f"🔹 [Обычный] ID: {getattr(gift, 'id', 'N/A')}")
                
        print("=" * 40)
        print(f"📊 ИТОГ: Найдено {nft_count} NFT-подарков.")

if __name__ == "__main__":
    asyncio.run(main())