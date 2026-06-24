@echo off
setlocal enabledelayedexpansion

set APP_NAME=有声书翻译工坊
set REPO_ROOT=%~dp0
cd /d "%REPO_ROOT%"

echo [SYSTEM] Starting %APP_NAME%
echo [SYSTEM] Repo root: %REPO_ROOT%

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found in PATH.
  pause
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm not found in PATH.
  pause
  exit /b 1
)

where cargo >nul 2>nul
if errorlevel 1 (
  echo [ERROR] cargo not found in PATH. Install Rust toolchain first.
  pause
  exit /b 1
)

if not exist ".venv" (
  echo [SYSTEM] Creating Python venv...
  python -m venv .venv
)

call ".venv\Scripts\activate.bat"

echo [SYSTEM] Checking Python dependencies...
python -c "import openai" 2>nul
if errorlevel 1 (
  echo [SYSTEM] Installing Python requirements...
  python -m pip install -r requirements.txt
)

cd /d "%REPO_ROOT%desktop"

if not exist "node_modules" (
  echo [SYSTEM] Installing desktop npm dependencies...
  npm install
)

set YSS_REPO_ROOT=%REPO_ROOT%

echo [SYSTEM] Runtime preflight...
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%scripts\windows\preflight-runtime.ps1" -RepoRoot "%REPO_ROOT%."
if errorlevel 1 (
  echo [ERROR] Runtime preflight failed.
  pause
  exit /b 1
)

for /f %%i in ('git rev-parse --short HEAD') do set LOCAL_HEAD=%%i
echo [SYSTEM] Git HEAD: %LOCAL_HEAD%
echo [SYSTEM] Expected UI source: %REPO_ROOT%desktop\src
echo [SYSTEM] Expected Vite URL: http://localhost:1420

call "%REPO_ROOT%setup_msvc_env.bat"
if errorlevel 1 (
  echo [ERROR] MSVC/Windows SDK environment setup failed.
  echo [ERROR] See agent.md for manual LIB/INCLUDE configuration.
  pause
  exit /b 1
)
echo [SYSTEM] MSVC/SDK env ready (MSVC %MSVC_VER%, SDK %SDK_VER%)

echo [SYSTEM] Launching Tauri desktop app...
npm run tauri dev

pause
