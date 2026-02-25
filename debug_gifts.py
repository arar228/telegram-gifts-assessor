import asyncio
import logging
import os
from telethon import TelegramClient
from telethon.tl import functions, types

# Включаем логирование, чтобы видеть ВСЕ ошибки
logging.basicConfig(level=logging.ERROR)

# --- ВАШИ ДАННЫЕ ---
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
SESSION_NAME = 'debug_session'
# -------------------

async def main():
    print("1️⃣ [СТАРТ] Запускаем скрипт...")
    
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    print("2️⃣ [КЛИЕНТ] Подключаемся к Telegram...")
    await client.start()
    
    # Проверка: если скрипт тут завис, значит он ждет код в консоли!
    print("3️⃣ [АВТОРИЗАЦИЯ] Успешно! Мы внутри аккаунта.")
    
    me = await client.get_me()
    print(f"   --> Вы вошли как: {me.first_name} (ID: {me.id})")

    target = input("\n⌨️ Введите юзернейм для проверки (без @): ").strip().replace('@', '')
    print(f"4️⃣ [ПОИСК] Ищем пользователя {target}...")

    try:
        user = await client.get_entity(target)
        print(f"   --> Пользователь найден: ID {user.id}")

        print("5️⃣ [ЗАПРОС] Делаем запрос GetUserStarGiftsRequest...")
        
        # Прямой вызов API
        result = await client(functions.payments.GetUserStarGiftsRequest(
            user_id=user.id,
            offset=0,
            limit=100
        ))

        print(f"6️⃣ [ОТВЕТ] Получен ответ от Telegram! Подарков в списке: {len(result.gifts)}")
        
        print("\n" + "="*30)
        for entry in result.gifts:
            # Разбираем каждый подарок
            gift = entry.gift
            
            # Проверяем тип подарка
            # В версиях TL схемы:
            # StarGift - обычный
            # StarGiftUnique - NFT/Лимитированный
            
            is_nft = isinstance(gift, types.StarGiftUnique)
            
            # Доп. проверка по атрибутам, если типы не совпадают
            if not is_nft and hasattr(gift, 'slug'): # У NFT часто есть slug
                is_nft = True
            
            status = "💎 NFT (Блокчейн)" if is_nft else "🔹 Обычный"
            
            # Пытаемся достать название
            title = getattr(gift, 'title', 'Без названия')
            if title == 'Без названия' and hasattr(gift, 'id'):
                title = f"Gift ID {gift.id}"

            print(f"{status}: {title}")
            
            if is_nft:
                # Если это NFT, пробуем достать детали
                num = getattr(gift, 'num', '?')
                total = getattr(gift, 'availability_total', '?')
                print(f"   --> Номер: {num} из {total}")

        print("="*30 + "\n")

    except TypeError as e:
        print(f"\n❌ [ОШИБКА ТИПОВ]: {e}")
        print("!!! Это значит, что библиотека Telethon устарела.")
        print("Выполните: pip install --upgrade https://github.com/LonamiWebs/Telethon/archive/master.zip")
    except AttributeError as e:
        print(f"\n❌ [ОШИБКА АТРИБУТА]: {e}")
        print("!!! Скорее всего, метод GetUserStarGiftsRequest не найден в вашей версии библиотеки.")
    except Exception as e:
        print(f"\n❌ [НЕИЗВЕСТНАЯ ОШИБКА]: {type(e).__name__}: {e}")

    print("7️⃣ [ФИНАЛ] Отключаемся...")
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())