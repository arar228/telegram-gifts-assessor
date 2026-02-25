@echo off
echo [1/4] Удаляем старые библиотеки...
python -m pip uninstall telethon hydrogram pyrogram -y

echo [2/4] Скачиваем свежую версию Telethon (Master Branch)...
curl -L https://github.com/LonamiWebs/Telethon/archive/refs/heads/master.zip -o telethon_new.zip

echo [3/4] Распаковываем...
powershell -command "Expand-Archive -Force telethon_new.zip -DestinationPath ."

echo [4/4] Устанавливаем...
cd Telethon-master
python -m pip install .
cd ..

echo.
echo ==============================================
echo  ГОТОВО! Библиотека обновлена.
echo  Теперь можно запускать юзербота.
echo ==============================================
del telethon_new.zip
pause