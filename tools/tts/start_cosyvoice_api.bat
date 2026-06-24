@echo off
setlocal

set REPO_ROOT=%~dp0..\..
for %%I in ("%REPO_ROOT%") do set REPO_ROOT=%%~fI

set COSYVOICE_ROOT=%REPO_ROOT%\third_party\tts\CosyVoice
set FASTAPI_DIR=%COSYVOICE_ROOT%\runtime\python\fastapi

if "%PYTHON_CMD%"=="" set PYTHON_CMD=python
if "%COSYVOICE_MODEL_DIR%"=="" set COSYVOICE_MODEL_DIR=%COSYVOICE_ROOT%\pretrained_models\CosyVoice-300M

if not exist "%FASTAPI_DIR%\server.py" (
  echo [ERROR] CosyVoice FastAPI server.py not found: "%FASTAPI_DIR%\server.py"
  exit /b 1
)

cd /d "%FASTAPI_DIR%"
"%PYTHON_CMD%" server.py --port 50000 --model_dir "%COSYVOICE_MODEL_DIR%"
