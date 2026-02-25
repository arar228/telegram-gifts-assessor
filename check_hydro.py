import asyncio
import os
from hydrogram import Client
from hydrogram.raw import functions, types

# --- ВАШИ ДАННЫЕ ---
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
SESSION_NAME = 'my_gift_checker'
# -------------------

async def main():
    # Инициализация клиента
    app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)
    
    print("🚀 Запуск Hydrogram...")
    
    async with app:
        print("✅ Успешная авторизация!")
        
        target = input("Введите юзернейм (без @): ").strip().replace('@', '')
        print(f"🔍 Ищем пользователя {target}...")
        
        try:
            # Получаем информацию о пользователе (Resolve Peer)
            peer = await app.resolve_peer(target)
            
            # Делаем RAW запрос к API (Get User Star Gifts)
            # Этот метод точно есть в свежем Hydrogram
            req = functions.payments.GetUserStarGifts(
                user_id=peer,
                offset="",
                limit=100
            )
            
            result = await app.invoke(req)
            
            print(f"\n🎁 Найдено подарков: {len(result.gifts)}")
            print("-" * 40)
            
            nft_count = 0
            
            for entry in result.gifts:
                # В Raw API объект выглядит как UserStarGift
                # Внутри него есть поле gift (StarGift)
                gift_data = entry.gift
                
                # Проверяем, является ли подарок уникальным (NFT)
                # Тип StarGiftUnique означает NFT на блокчейне
                is_nft = isinstance(gift_data, types.StarGiftUnique)
                
                status = "💎 [NFT/TON]" if is_nft else "🔹 [Обычный]"
                
                title = "Подарок"
                if hasattr(gift_data, 'title'):
                    title = gift_data.title
                elif hasattr(gift_data, 'id'):
                    title = f"ID: {gift_data.id}"
                
                # Вывод информации
                if is_nft:
                    nft_count += 1
                    num = getattr(gift_data, 'num', '?')
                    total = getattr(gift_data, 'availability_total', '?')
                    print(f"{status} {title} | Номер: {num} из {total}")
                else:
                    print(f"{status} {title}")
            
            print("-" * 40)
            print(f"📊 ИТОГ: NFT на блокчейне: {nft_count}")
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main())