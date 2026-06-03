@echo off
chcp 65001 >nul
call "%~dp0_root.bat"
echo Пересоздание backend\venv с Python 3.11 (для XTTS-v2)...
echo.

where py >nul 2>&1 || (
  echo Установите Python 3.11: https://www.python.org/downloads/release/python-3119/
  pause
  exit /b 1
)

py -3.11 -c "import sys" 2>nul || (
  echo Python 3.11 не найден. Выполните: py install 3.11
  pause
  exit /b 1
)

if exist "backend\venv" (
  echo Удаление старого venv...
  rmdir /s /q "backend\venv"
)

py -3.11 -m venv backend\venv
call backend\venv\Scripts\activate.bat
pip install --upgrade pip wheel
if exist "backend\wheels\PySocks-1.7.1-py3-none-any.whl" pip install backend\wheels\PySocks-1.7.1-py3-none-any.whl
pip install -r backend\requirements.txt

echo.
echo Готово. Запустите start.bat
pause
