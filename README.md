# Telegram Gift Portfolio Assessor

A Python toolkit for collecting Telegram gift inventories and estimating collection-level market values from external data sources. It separates account-based gift discovery from pricing experiments across TonAPI, Getgems, Fragment, and Giftasset-related utilities.

[Source map](#source-map) · [Setup requirements](#setup-requirements) · [Limitations and verification](#limitations-and-verification)

## Engineering focus

- Represent regular gifts, upgraded gifts, and on-chain NFT gifts in a common reporting workflow.
- Explore the boundary between Telegram account data and blockchain/marketplace metadata.
- Produce text reports and list-based analyses that can be inspected independently of the Telegram interface.

Prices in these tools are estimates from external listings or collection data. They are not guaranteed sale prices or a valuation audit.

## Source map

| Source | Responsibility |
|---|---|
| [price_checker.py](price_checker.py) | Inventory collection, TonAPI lookup, portfolio aggregation, and text reporting |
| [test_gifts.py](test_gifts.py), [run_test.py](run_test.py) | Account-backed gift inspection utilities |
| [gift_price_checker.py](gift_price_checker.py) | Link parsing and Fragment-oriented pricing lookup |
| [price_getgems.py](price_getgems.py), [price_apiton_tonapi.py](price_apiton_tonapi.py) | Alternative marketplace/API lookup paths |
| [price_from_list.py](price_from_list.py), [price_giftasset.py](price_giftasset.py) | List-based analysis and optional Giftasset integration |
| [userbot_final.py](userbot_final.py), [checker.py](checker.py) | Telethon/Hydrogram integration variants |
| [API_DOCUMENTATION.md](API_DOCUMENTATION.md), [PRICE_SOURCES.md](PRICE_SOURCES.md) | Existing API and price-source notes |

**Stack:** Python, Telethon, Hydrogram in selected scripts, asyncio, Requests, and python-dotenv. Telegram collection is asynchronous; several HTTP pricing functions use synchronous Requests calls.

## Setup requirements

```bash
git clone https://github.com/arar228/telegram-gifts-assessor.git
cd telegram-gifts-assessor
python -m venv .venv
# Activate .venv using your shell's activation command.
python -m pip install -r requirements.txt
```

`requests` and `hydrogram` are imported by scripts but are not declared in the current requirements file. Reconcile dependencies for the particular script you intend to use before running it; this documentation pass leaves the dependency file unchanged.

| Setting | Purpose |
|---|---|
| `API_ID`, `API_HASH` | Your Telegram application's MTProto credentials |
| `PHONE_NUMBER` | Optional phone number for the existing login flow |
| `GIFTASSET_API_KEY` | Optional credential used by the Giftasset utility |

`price_checker.py` and `test_gifts.py` call `load_dotenv()`. Some other utilities read process environment variables directly. The current branch still contains credential fallbacks in parts of the code; supply your own configuration and coordinate the separate security migration before deployment. Preserve account sessions privately and use only accounts/data you are authorized to access.

After credentials and dependencies are prepared, the main utility accepts a Telegram username:

```bash
python price_checker.py @username
```

This command performs real account/API activity. The similarly named `test_gifts.py` is an interactive/network utility, not an offline unit-test command.

## Limitations and verification

Source/documentation review: **2026-09-07**. Live Telegram login, marketplace availability, pricing accuracy, and deployment were not verified in this pass. No GitHub Actions workflow is included in this snapshot.

Collection floors, missing listings, off-chain ownership, conversion rates, and provider response changes can affect estimates. A useful next test boundary is recorded/synthetic API responses with assertions on classification and report totals. Avoid publishing account sessions, phone numbers, raw user reports, or private API credentials with the case study.
