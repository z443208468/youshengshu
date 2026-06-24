@echo off
setlocal
set REPO_ROOT=%~dp0..\..
cd /d "%REPO_ROOT%"

set COSYVOICE_DIR=third_party\tts\CosyVoice

if not exist "%COSYVOICE_DIR%" (
  echo [ERROR] CosyVoice not found. Run tools\tts\clone_cosyvoice.bat first.
  exit /b 1
)

echo [INFO] Start CosyVoice FastAPI server manually in your CosyVoice conda env.
echo [INFO] Example:
echo   cd %COSYVOICE_DIR%
echo   python webui.py --port 50000 --model_dir pretrained_models/CosyVoice-300M
echo.
echo [INFO] After server is up, use TTS workbench or:
echo   python tools\tts\check_cosyvoice_api.py
exit /b 0
