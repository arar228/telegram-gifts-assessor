# Варианты, где смотреть цену Telegram Gift NFT

## 1. API и сервисы

| Источник | Что даёт | Как использовать |
|----------|----------|------------------|
| **tonapi.io** | Поиск коллекций, floor по адресу коллекции | `GET /v2/nfts/search?q=FreshSocks`, затем `GET /v2/nfts/collections/{address}/items` — в проекте: `price_from_list.py`, `check_list_prices.py`. Для Telegram Gifts часто пусто. |
| **Getgems GraphQL** | Поиск коллекций, floor, продажи | `api.getgems.io/graphql` — запросы `nftCollections`, `nftCollection`, `nftSearch`. В проекте: `price_getgems.py`, `check_list_prices.py` (ранее). nftSearch по подаркам часто пустой. |
| **giftasset.pro** | Цена по имени подарка (market_floor, collection_floor) | `GET https://giftasset.pro/api/v1/gifts/get_gift_by_name?name=FreshSocks-79283`. Документация: https://giftasset.pro/docs. В проекте: `price_giftasset.py`. Опционально: `GIFTASSET_API_KEY`. |
| **apiTON** | Адрес подарка по имени (slug) | `POST https://app.apiton.org/v2.Nft/Gift` body: `{"name": "FreshSocks-79283"}`. Документация: https://docs.apiton.org/gift-18474729e0. Цену нужно смотреть отдельно (по адресу в других API). |
| **TONX API** | Коллекции, предметы, метаданные, история | https://docs.tonxapi.com — нет готового floor/цен, только данные контрактов. Нужен API key. |

## 2. Сайты и приложения (ручная проверка)

| Сервис | Описание |
|--------|----------|
| **Getgems — Top Gifts** | https://getgems.io/top-gifts — маркетплейс, отображает floor и объёмы по коллекциям подарков. |
| **ton.gifts** | https://ton.gifts — каталог Telegram Gift NFT. |
| **Telegifts** | https://telegifts.app — приложение (iOS), floor в TON и USDT по маркетплейсам Tonnel, Portals, MRKT. Публичного API в открытом доступе нет. |
| **Tonnel Relayer** | Telegram-бот/мини-приложение, маркетплейс подарков (1M+ пользователей). |
| **Tonviewer** | https://tonviewer.com — эксплорер TON; если есть адрес NFT, можно смотреть контракт и сделки (цены вручную). |

## 3. Идея для скрипта

1. **apiTON Gift** — по каждой ссылке из списка вызывать `POST /v2.Nft/Gift` с `name = "CollectionName-Id"` (например `FreshSocks-79283`), получить адрес NFT.
2. По адресу NFT запросить **tonapi.io** `GET /v2/nfts/{address}` — в ответе может быть `sale` с ценой, если лот в продаже.
3. Для floor по коллекции — один раз найти адрес коллекции (tonapi search или Getgems), затем брать floor из Getgems/top-gifts или tonapi collections.

## 4. Ограничения

- Telegram Gifts не всегда есть в tonapi/Getgems под теми же именами (FreshSocks, HappyBrownie и т.д.), поэтому поиск по названию коллекции часто даёт пустой результат.
- Готового «одного API с ценой по ссылке t.me/nft/...» нет: обычно нужна цепочка (slug → адрес → цена или коллекция → floor).

Если нужно, можно добавить в проект скрипт, который для списка ссылок: вызывает apiTON Gift, затем по адресу проверяет цену в tonapi (sale) и при необходимости один раз получает floor коллекции с Getgems/tonapi.
