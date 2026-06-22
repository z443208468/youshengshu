@echo off
setlocal enabledelayedexpansion
set REPO_ROOT=%~dp0
cd /d "%REPO_ROOT%"

call ".venv\Scripts\activate.bat" 2>nul

echo [CHECK] Python deps (dev only — may upgrade pip)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo [CHECK] Python tests
python -m pytest -q
if errorlevel 1 exit /b 1

echo [CHECK] Python CLI help
python -m youshengshu.cli --help
python -m youshengshu.cli split --help
python -m youshengshu.cli status --help
python -m youshengshu.cli translate --help
python -m youshengshu.cli doctor --help
if errorlevel 1 exit /b 1

echo [CHECK] Frontend build
cd /d "%REPO_ROOT%desktop"
npm run build
if errorlevel 1 exit /b 1

echo [CHECK] Rust cargo check
cd /d "%REPO_ROOT%desktop\src-tauri"
cargo check
if errorlevel 1 exit /b 1

echo [CHECK] OK
exit /b 0
