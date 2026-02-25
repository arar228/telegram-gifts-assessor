"""
Скрипт для запуска проверки подарков с параметрами командной строки
"""
import asyncio
import argparse
import sys

# Фикс кодировки для Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from test_gifts import run_gift_check


def main():
    """Главная функция с парсингом аргументов"""
    parser = argparse.ArgumentParser(
        description='Проверка подарков пользователя Telegram (NFT на блокчейне TON)'
    )
    parser.add_argument(
        '--user-id',
        type=int,
        help='ID пользователя Telegram'
    )
    parser.add_argument(
        '--username',
        type=str,
        help='Username пользователя Telegram (без @)'
    )
    
    args = parser.parse_args()
    
    if not args.user_id and not args.username:
        parser.print_help()
        sys.exit(1)
    
    print("🚀 Запуск проверки подарков Telegram")
    print("=" * 50)
    
    asyncio.run(run_gift_check(user_id=args.user_id, username=args.username))


if __name__ == "__main__":
    main()
