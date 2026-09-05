@echo off
rem [REAL RUN] Windows port of live.sh - writes state/ and bestiary.json. NOT a verify suite.
rem Keep this file CRLF + ASCII-only (cp949 console safety).
rem Usage: live.bat  (env DUNGEON_* may be set by the caller, see wonderland.bat)
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "DUNGEON_STATE_DIR="
rem Demo runs get a fresh dungeon each time (D31, 2026-09-05). Gates/A-B set an integer seed.
if not defined DUNGEON_SEED set "DUNGEON_SEED=random"
rem Demo sight radius 6 (D33, 2026-09-05; engine/gates keep 5). Ally sight exemption is runner default 1.
if not defined DUNGEON_SIGHT set "DUNGEON_SIGHT=6"
if not exist state mkdir state
if not exist runs mkdir runs

rem Preserve the previous run before show_runner truncates stream.jsonl (same rule as live.sh).
powershell -NoProfile -Command "$f='state\stream.jsonl'; if((Test-Path $f) -and (Get-Item $f).Length -gt 0){ $n='runs\stream-'+(Get-Item $f).LastWriteTime.ToString('yyyyMMdd-HHmmss')+'.jsonl'; if(-not(Test-Path $n)){Copy-Item $f $n} }"

rem Ensure the web viewer server on port 8000 (idempotent - reuse if already up).
rem Serve the dungeon root so /viewer/ can fetch /runs/ and /state/ (VIEWER_DESIGN section 3).
powershell -NoProfile -Command "try{ Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 http://127.0.0.1:8000/viewer/tiles.json | Out-Null }catch{ Start-Process -WindowStyle Hidden python -ArgumentList '-m','http.server','8000','--bind','127.0.0.1','--directory','%~dp0.' }"

echo Watch: http://localhost:8000/viewer/   (run picker = live, keep playhead at the end)
echo Stop: Ctrl-C or close this window. The previous run is already saved to runs/.
echo.

rem Bestiary persistence is for live runs only (verify/experiments keep it off = isolation).
if not defined DUNGEON_BESTIARY_FILE set "DUNGEON_BESTIARY_FILE=%~dp0bestiary.json"
if not defined DUNGEON_GM set "DUNGEON_GM=0"
python show_runner.py
