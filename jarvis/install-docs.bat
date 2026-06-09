@echo off

chcp 65001 >nul

title Jarvis — документы (MarkItDown)

cd /d "%~dp0"



echo ========================================

echo   MarkItDown — чтение PDF/Office без LLM

echo ========================================

echo.



if not exist "backend\venv\Scripts\python.exe" (

  echo Сначала запустите start.bat

  pause

  exit /b 1

)



backend\venv\Scripts\python.exe -m pip install "markitdown[pdf,docx,pptx,xlsx]" -q

if errorlevel 1 (

  echo [ОШИБКА] pip install

  pause

  exit /b 1

)



cd backend

venv\Scripts\python.exe -c "from modules.document_tools import get_document_engine_status, supported_formats_help; import json; print(json.dumps(get_document_engine_status(), ensure_ascii=False, indent=2)); print(); print(supported_formats_help())"

cd ..

echo.

echo Готово. В чате: doc_read / doc_convert или загрузка файла через скрепку.

pause

