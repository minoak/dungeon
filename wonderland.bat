@echo off
rem Wonderland fast starter - launches the WSL dungeon (~/dungeon)
rem Keep this file CRLF + ASCII-only (cp949 console safety).
chcp 65001 >nul
title Wonderland

:menu
echo.
echo  =============== WONDERLAND ===============
echo   [1] Live run + web viewer   (REAL run)
echo   [2] Watch in tmux           (REAL run)
echo   [3] Viewer only  (replays, no new run)
echo   [4] Experiment batch status
echo   [5] D19 demo run  (scan ON - new movement)
echo   [6] Big map 1F test  (80x30, many mobs)
echo   [Q] Quit
echo  ==========================================
set "pick="
set /p pick="pick> "
if /i "%pick%"=="1" goto live
if /i "%pick%"=="2" goto tmux
if /i "%pick%"=="3" goto viewer
if /i "%pick%"=="4" goto status
if /i "%pick%"=="5" goto d19
if /i "%pick%"=="6" goto bigmap
if /i "%pick%"=="Q" exit /b 0
goto menu

:live
echo Starting a REAL run (writes state/ and bestiary.json).
echo Closing the new window stops the run. Previous run is auto-saved to runs/.
start "Wonderland live" wsl -e bash -lc "bash ~/dungeon/live.sh"
timeout /t 4 /nobreak >nul
start "" http://localhost:8000/viewer/
goto menu

:d19
echo D19 demo: REAL run with DUNGEON_SCAN=1 (doors/rooms vocabulary, stairs by sight only).
echo Closing the new window stops the run. Previous run is auto-saved to runs/.
start "Wonderland D19 demo" wsl -e bash -lc "DUNGEON_SCAN=1 bash ~/dungeon/live.sh"
timeout /t 4 /nobreak >nul
start "" http://localhost:8000/viewer/
goto menu

:bigmap
echo Big map 1F test: PD-scale floor (80x30, 7 monsters + 2 lurkers, 4 traps, 1 potion, single depth).
echo Dummy physics check passed (5 seeds, median 250 ticks). Live run may take 1h+.
echo Closing the new window stops the run. Previous run is auto-saved to runs/.
start "Wonderland big map" wsl -e bash -lc "DUNGEON_W=80 DUNGEON_H=30 DUNGEON_MONSTERS=7 DUNGEON_TRAPS=4 DUNGEON_LURKERS=2 DUNGEON_POTIONS=1 DUNGEON_DEPTHS=1 DUNGEON_TURNS=500 bash ~/dungeon/live.sh"
timeout /t 4 /nobreak >nul
start "" http://localhost:8000/viewer/
goto menu

:tmux
echo tmux watch: detach = Ctrl-b then d / quit = tmux kill-session -t dungeon
start "Wonderland tmux" wsl -e bash -lc "bash ~/dungeon/start.sh"
goto menu

:viewer
wsl -e bash -lc "cd ~/dungeon && curl -s -o /dev/null --max-time 1 http://127.0.0.1:8000/viewer/tiles.json || (nohup python3 -m http.server 8000 --bind 127.0.0.1 --directory ~/dungeon >/dev/null 2>&1 &); sleep 1"
start "" http://localhost:8000/viewer/
goto menu

:status
echo --- running processes ---
wsl -e bash -lc "pgrep -af 'ab_persona|show_runner' | grep -v 'bash -lc' || echo none"
echo --- baseline log tail ---
wsl -e bash -lc "tail -n 8 ~/dungeon/ab_runs/persona_baseline.log"
echo.
pause
goto menu
