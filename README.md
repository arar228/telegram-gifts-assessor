# Telegram Star Gifts & NFT Assessor

A powerful and professional toolset for fetching, analyzing, and precisely evaluating the market value of Telegram Star Gifts, including blockchain-based NFTs. Built with Python and Telethon, this project provides a technical foundation to interact directly with the Telegram API and TON blockchain (via TonAPI) to extract deep insights into any user's gift portfolio.

## 🚀 Features

- **Direct Telegram API Integration**: Bypasses bot limitations by using an automated user client (`Telethon` and `Hydrogram`) to pull accurate data.
- **Deep Portfolio Analysis**: Categorizes gifts into three distinct classes:
  1. Regular Gifts (StarGifts)
  2. Upgraded Gifts (Off-chain)
  3. NFT Gifts (Minted on the TON Blockchain)
- **Live Market Valuation**: Automatically queries `tonapi.io` to determine the current floor price and average price for NFT collections, calculating the total real-time value of a user's portfolio in TON and USD.
- **Detailed Reporting**: Generates comprehensive `.txt` reports breaking down the portfolio structure, missing blockchain assets, and current market valuations.
- **Asynchronous Architecture**: Built entirely on `asyncio` for rapid parallel fetching and non-blocking execution.

## ⚙️ Architecture

The project consists of multiple modules tailored for different tasks:
- `price_checker.py`: The core engine for assessing portfolio market value using Telegram API + TonAPI.
- `test_gifts.py` / `checker.py` / `check_hydro.py`: Dedicated scripts for extracting raw user gifts using different MTProto libraries (`Telethon` vs `Hydrogram`).
- `userbot_final.py`: A streamlined userbot implementation for seamless Telegram interactions.

## 🛠 Prerequisites

- Python 3.8+
- Telegram `API_ID` and `API_HASH` (obtainable from my.telegram.org)
- A registered Telegram account (for userbot authentication)

## 📦 Installation & Setup

1. **Clone the repository**
   ```bash
   git clone <your-repository-url>
   cd <repository-dir>
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   Create a `.env` file in the root directory and add your credentials:
   ```env
   API_ID=your_api_id
   API_HASH=your_api_hash
   PHONE_NUMBER=+1234567890
   ```

## 💻 Usage

Run the primary price checker script to evaluate a user:
```bash
python price_checker.py @username
```

To fetch a detailed logical breakdown of gifts without pricing:
```bash
python test_gifts.py @username
```

## 🔒 Security Note
All scripts are configured to retrieve API keys via environment variables securely. Do **not** hardcode credentials in your code. Review `.env.example` if available.

## 📄 License
This project is for educational and portfolio demonstration purposes. Ensure you comply with Telegram's Terms of Service when using automated clients.
