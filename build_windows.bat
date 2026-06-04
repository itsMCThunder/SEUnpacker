@echo off
setlocal
cd /d "%~dp0"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --onefile --windowed --name SEUnpacker --icon "assets\icons\seunpacker.ico" --add-data "assets;assets" app.py
 echo.
 echo Build complete. Check the dist folder for SEUnpacker.exe
pause
