@echo off
chcp 65001 >nul
title Jarvis — браузер для оконного режима
cd /d "%~dp0"
call "%~dp0install-browsers.bat"
