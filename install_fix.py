import os
import sys
import subprocess
import requests
import zipfile
import shutil

def force_install():
    print("🛡️ Обход защиты GitHub...")
    
    # Ссылка на версию разработчика
    url = "https://github.com/LonamiWebs/Telethon/archive/refs/heads/master.zip"
    zip_name = "telethon_dev.zip"
    extract_folder = "telethon_dev_folder"
    
    # 1. Удаляем хвосты от прошлых попыток
    if os.path.exists(extract_folder):
        shutil.rmtree(extract_folder)
    
    # 2. Устанавливаем requests если нет
    try:
        import requests
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        import requests

    # 3. Скачиваем С ЗАГОЛОВКАМИ (Как браузер)
    print("📥 Скачивание архива...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    response = requests.get(url, headers=headers, stream=True)
    if response.status_code != 200:
        print(f"❌ Ошибка скачивания: Код {response.status_code}")
        return

    with open(zip_name, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            
    # Проверка размера (архив должен быть > 1 МБ)
    size_mb = os.path.getsize(zip_name) / (1024 * 1024)
    print(f"📦 Размер архива: {size_mb:.2f} MB")
    
    if size_mb < 0.1:
        print("❌ Ошибка: Архив слишком маленький. GitHub заблокировал скачивание.")
        return

    # 4. Распаковка
    print("📂 Распаковка...")
    try:
        with zipfile.ZipFile(zip_name, 'r') as zip_ref:
            zip_ref.extractall(extract_folder)
    except zipfile.BadZipFile:
        print("❌ Ошибка: Скачанный файл не является архивом.")
        return

    # 5. Поиск папки с кодом
    install_path = None
    for root, dirs, files in os.walk(extract_folder):
        if "setup.py" in files:
            install_path = root
            break
            
    if not install_path:
        print("❌ Не найден setup.py. Странная структура архива.")
        return

    # 6. Установка
    print(f"🛠️ Установка из {install_path}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "."], cwd=install_path)
    
    # 7. Чистка
    try:
        os.remove(zip_name)
        shutil.rmtree(extract_folder)
    except:
        pass
        
    print("\n✅ УСПЕШНО! Telethon обновлен. Теперь можно запускать бота.")

if __name__ == "__main__":
    force_install()
    input("\nНажмите Enter, чтобы выйти...")