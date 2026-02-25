import os
import sys
import subprocess
import urllib.request
import zipfile
import shutil

def auto_install():
    print("🚀 Начинаем умную установку...")
    
    # 1. Скачиваем архив заново (надежная ссылка)
    url = "https://github.com/LonamiWebs/Telethon/archive/refs/heads/master.zip"
    zip_name = "telethon_fix.zip"
    extract_folder = "telethon_temp_install"
    
    if os.path.exists(extract_folder):
        shutil.rmtree(extract_folder)
        
    print("📥 Скачиваем Telethon...")
    try:
        urllib.request.urlretrieve(url, zip_name)
    except Exception as e:
        print(f"❌ Ошибка скачивания: {e}")
        return

    # 2. Распаковываем
    print("📦 Распаковываем...")
    try:
        with zipfile.ZipFile(zip_name, 'r') as zip_ref:
            zip_ref.extractall(extract_folder)
    except zipfile.BadZipFile:
        print("❌ Ошибка: Архив поврежден. Попробуйте VPN или другой интернет.")
        return

    # 3. ИЩЕМ setup.py (Самый важный шаг)
    setup_path = None
    print("🔍 Ищем установочный файл...")
    
    for root, dirs, files in os.walk(extract_folder):
        if "setup.py" in files:
            setup_path = root
            print(f"✅ Найдено в папке: {setup_path}")
            break
    
    if not setup_path:
        print("❌ Не удалось найти setup.py внутри архива.")
        return

    # 4. Устанавливаем
    print("🛠 Устанавливаем...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "."], cwd=setup_path)
        print("\n🎉 ГОТОВО! Библиотека успешно установлена.")
    except Exception as e:
        print(f"\n❌ Ошибка установки: {e}")
        
    # 5. Уборка
    try:
        os.remove(zip_name)
        shutil.rmtree(extract_folder)
    except:
        pass

if __name__ == "__main__":
    auto_install()
    input("\nНажмите Enter, чтобы выйти...")