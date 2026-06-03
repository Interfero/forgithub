@echo off
chcp 65001 >nul
title Jarvis — браузер для оконного режима
call "%~dp0_root.bat"
call "%~dp0install-browsers.bat"
