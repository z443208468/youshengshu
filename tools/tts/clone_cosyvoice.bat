@echo off
setlocal
set REPO_ROOT=%~dp0..\..
cd /d "%REPO_ROOT%"

if not exist "third_party\tts" mkdir "third_party\tts"

if exist "third_party\tts\CosyVoice\.git" (
  echo [INFO] CosyVoice already cloned.
  exit /b 0
)

git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git third_party\tts\CosyVoice
if errorlevel 1 exit /b 1

cd /d third_party\tts\CosyVoice
git submodule update --init --recursive
if errorlevel 1 exit /b 1

echo [OK] CosyVoice cloned.
