@echo off
setlocal enabledelayedexpansion
set REPO_ROOT=%~dp0
cd /d "%REPO_ROOT%desktop"

set YSS_REPO_ROOT=%REPO_ROOT%

call "%REPO_ROOT%setup_msvc_env.bat"
if errorlevel 1 (
  echo [ERROR] MSVC/Windows SDK environment setup failed. See agent.md.
  pause
  exit /b 1
)

npm install
npm run build
npm run tauri build

echo [SYSTEM] Build completed.
echo [SYSTEM] Check desktop\src-tauri\target\release\bundle
pause
