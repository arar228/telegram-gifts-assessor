# Документация по Telegram Client API для работы с подарками

## Обзор

Этот проект использует Telegram Client API (MTProto) через библиотеку Telethon для получения информации о подарках пользователей, которые находятся на блокчейне TON.

## API Credentials

- **API ID**: 21192413
- **API Hash**: 2d7b04c4c7d7b93826277d37c9e4e2e4

Получить свои credentials можно на: https://my.telegram.org/apps

## Основные методы

### 1. Подключение к Telegram

```python
from telethon import TelegramClient

client = TelegramClient('session_name', api_id, api_hash)
await client.start(phone=phone_number)
```

### 2. Получение пользователя

#### По ID:
```python
user = await client.get_entity(user_id)
```

#### По username:
```python
user = await client.get_entity('username')
```

### 3. Получение полной информации о пользователе

```python
from telethon.tl.functions.users import GetFullUserRequest

full_info = await client(GetFullUserRequest(user))
```

## Подарки на блокчейне TON

### Признаки подарка на блокчейне

Подарки, которые находятся на блокчейне TON, имеют следующие признаки:

1. **Надпись в интерфейсе**: "This gift is on the TON blockchain"
2. **NFT-идентификатор**: Формат `t.me/nft/CollectionName-ID`
3. **Блокчейн-информация**: Доступна через блокчейн-эксплореры (Ton.org, Getgems.io)

### Структура данных подарка на блокчейне

```python
{
    'id': 'gift_id',
    'name': 'Toy Bear',
    'collectible_id': 25794,
    'blockchain': 'TON',
    'nft_id': 't.me/nft/CollectionName-ID',
    'model': 'Watermelon',
    'model_rarity': '1.5%',
    'symbol': 'Coat of Arms',
    'symbol_rarity': '0.4%',
    'backdrop': 'Lemongrass',
    'backdrop_rarity': '2%',
    'quantity': '55 735 of 57 724 issued',
    'value': '~$53.00',
    'is_blockchain': True,
    'description': 'This gift is on the TON blockchain',
    'owner': 'username'
}
```

## Получение статистики

Статистика должна браться по **открытым подаркам** по username или ID пользователя.

### Фильтрация подарков на блокчейне

Подарки фильтруются по следующим признакам:
- Наличие поля `blockchain == 'TON'`
- Наличие поля `is_blockchain == True`
- Наличие текста "blockchain" или "ton blockchain" в описании
- Наличие NFT-идентификатора (`nft_id`)

## Актуальная документация

Для получения актуальной информации о методах API рекомендуется:

1. **Официальная документация Telegram**: https://core.telegram.org/api
2. **Telethon документация**: https://docs.telethon.dev/
3. **Telegram API Updates**: https://core.telegram.org/api/updates

## Примечания

- Методы API могут изменяться в зависимости от версии Telegram
- Для работы с подарками на блокчейне может потребоваться дополнительная интеграция с TON API
- Некоторые методы могут быть доступны только для определенных типов аккаунтов (Premium)
