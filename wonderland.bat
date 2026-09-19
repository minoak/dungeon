@echo off
rem Wonderland starter - local web launcher or online server.
rem Keep this file CRLF + ASCII-only (cp949 console safety).
chcp 65001 >nul
title Wonderland
cd /d "%~dp0"

:menu
echo.
echo  =============== WONDERLAND ===============
echo   [L] LOCAL LAUNCHER: characters, models, play and replays
echo   [S] ONLINE SERVER: account login + saved characters
echo   [Q] Quit
echo  ==========================================
set "pick="
set /p pick="pick> "
if /i "%pick%"=="L" goto launcher
if /i "%pick%"=="S" goto online
if /i "%pick%"=="Q" exit /b 0
goto menu

:online
start "" "https://botpicdun.duckdns.org/"
goto menu

:launcher
echo Open the web launcher to set up characters and models, start or resume a run, or watch replays.
echo API brains use your provider's key. The rules brain (dummy) is free.
start "Wonderland launcher" cmd /k "set PYTHONUTF8=1&& python launcher.py"
goto menu
