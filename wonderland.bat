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
echo   [5] SOLO run  (3 strangers, apart, each exits alone)
echo   [6] Big map 1F test  (80x30, many mobs)
echo   [7] Gemini brain     (API - COSTS MONEY)
echo   [8] Gemini + ally-sight  (door fix ON - compare with 7)
echo   [9] BIG verdict: map + Gemini + ally-sight + social  (~25min, ~500 KRW)
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
if /i "%pick%"=="7" goto gemini
if /i "%pick%"=="8" goto allysight
if /i "%pick%"=="9" goto bigally
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
echo SOLO run: the party premise is removed. Three strangers wake up far apart on one
echo floor, do not know each other exist, and each descends alone at the stairs.
echo The run continues until all three are out or dead - we watch every one of them.
echo If they meet they are free: walk together, split up, talk. The engine does not decide.
echo NOTE they cannot fight each other - the engine has no character-vs-character attack.
echo.
echo Question this run answers: does each character act on its OWN sheet goal
echo when there is nobody to follow? In the 07-26 party run the archer Fyrn spent
echo 34 of 51 decisions following someone - with explore 0 and search 0 - while her
echo sheet says she must see everything down here. Alone, does she explore?
echo.
echo Sheets: party_solo.json = party.json minus relationships. Same people, strangers.
echo Gemini brain. *** COSTS MONEY *** roughly 350 KRW.
echo After the run, read it with:  python3 ~/dungeon/analyze_run.py runs/NAME.jsonl
echo Closing the new window stops the run. Previous run is auto-saved to runs/.
start "Wonderland solo" wsl -e bash -lc "DUNGEON_W=80 DUNGEON_H=30 DUNGEON_MONSTERS=7 DUNGEON_TRAPS=4 DUNGEON_LURKERS=2 DUNGEON_POTIONS=1 DUNGEON_DEPTHS=1 DUNGEON_TURNS=500 DUNGEON_SOLO=1 DUNGEON_PARTY_FILE=party_solo.json DUNGEON_BRAIN_BACKEND=gemini_api bash ~/dungeon/live.sh"
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

:gemini
echo Gemini brain: HTTP API instead of claude.exe. Key comes from .env (GEMINI_API_KEY).
echo *** THIS COSTS MONEY *** - paid tier, ~1400 KRW per 200-tick run.
echo Model: gemini-3-flash-preview, thinkingLevel=minimal.
echo NOTE: different model = different acting. Not comparable to Haiku runs.
echo Closing the new window stops the run. Previous run is auto-saved to runs/.
start "Wonderland gemini" wsl -e bash -lc "DUNGEON_BRAIN_BACKEND=gemini_api bash ~/dungeon/live.sh"
timeout /t 4 /nobreak >nul
start "" http://localhost:8000/viewer/
goto menu

:allysight
echo Same as [7] but with DUNGEON_ALLY_SIGHT=1 - the door fix.
echo Allies stay visible through walls/doors within sight radius (allies only;
echo monsters and structure keep normal line of sight). Run [7] and [8] to compare.
echo Watch for: "where are you" chatter, party bouncing back through doorways.
echo *** THIS COSTS MONEY *** - paid tier, ~1400 KRW per 200-tick run.
echo Closing the new window stops the run. Previous run is auto-saved to runs/.
start "Wonderland ally-sight" wsl -e bash -lc "DUNGEON_BRAIN_BACKEND=gemini_api DUNGEON_ALLY_SIGHT=1 bash ~/dungeon/live.sh"
timeout /t 4 /nobreak >nul
start "" http://localhost:8000/viewer/
goto menu

:bigally
echo BIG map verdict run: [6] scale (80x30, 7 mobs + 2 lurkers, 4 traps, 1 potion,
echo single floor, 500 ticks) with Gemini brain, ally-sight AND social channel ON.
echo Judging four things at once:
echo   1. did the door/lost problem actually go away (ally-sight regression check)
echo   2. does the social split break the chatter-clump - follow share, cells/tick
echo   3. how often does "cannot see but walks straight to ally" happen (D18 party sense)
echo   4. is the 15-tick wait cap too long (D25)
echo Controls: runs/stream-20260724-160300.jsonl = clump (follow 38/97, 17 cells/71t)
echo           runs/bigmap-allysight-20260726.jsonl = same but social OFF
echo Time ~25 min at ~2.7s/tick. *** COSTS MONEY *** roughly 450-500 KRW.
echo Closing the new window stops the run. Previous run is auto-saved to runs/.
start "Wonderland big verdict" wsl -e bash -lc "DUNGEON_W=80 DUNGEON_H=30 DUNGEON_MONSTERS=7 DUNGEON_TRAPS=4 DUNGEON_LURKERS=2 DUNGEON_POTIONS=1 DUNGEON_DEPTHS=1 DUNGEON_TURNS=500 DUNGEON_BRAIN_BACKEND=gemini_api DUNGEON_ALLY_SIGHT=1 DUNGEON_SOCIAL=1 bash ~/dungeon/live.sh"
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
