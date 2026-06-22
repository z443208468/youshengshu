@echo off
setlocal enabledelayedexpansion
set REPO_ROOT=%~dp0
cd /d "%REPO_ROOT%desktop"

set YSS_REPO_ROOT=%REPO_ROOT%

npm install
npm run build
npm run tauri build

echo [SYSTEM] Build completed.
echo [SYSTEM] Check desktop\src-tauri\target\release\bundle
pause
