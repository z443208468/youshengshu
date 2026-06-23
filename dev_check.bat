@echo off
setlocal enabledelayedexpansion
set REPO_ROOT=%~dp0
cd /d "%REPO_ROOT%"

call ".venv\Scripts\activate.bat" 2>nul
set PYTHONPATH=%REPO_ROOT%src;%PYTHONPATH%

echo [CHECK] Python deps (dev only — may upgrade pip)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo [CHECK] Python tests
python -m pytest -q
if errorlevel 1 exit /b 1

echo [CHECK] Python CLI module entrypoint
python -m youshengshu.cli --help | findstr /C:"split,translate,status,doctor,all" >nul
if errorlevel 1 (
  echo [ERROR] python -m youshengshu.cli --help did not print CLI help.
  exit /b 1
)

echo [CHECK] Python doctor JSON
python -m youshengshu.cli --config config/default_config.json doctor --json > .doctor_check.json
if errorlevel 1 (
  echo [ERROR] doctor --json failed.
  type .doctor_check.json
  del .doctor_check.json
  exit /b 1
)

findstr /C:"can_split" .doctor_check.json >nul
if errorlevel 1 (
  echo [ERROR] doctor JSON missing can_split.
  type .doctor_check.json
  del .doctor_check.json
  exit /b 1
)

findstr /C:"can_translate" .doctor_check.json >nul
if errorlevel 1 (
  echo [ERROR] doctor JSON missing can_translate.
  type .doctor_check.json
  del .doctor_check.json
  exit /b 1
)

del .doctor_check.json

echo [CHECK] Python split/status smoke test

set SMOKE_DIR=.tmp_dev_check
set SMOKE_INPUT=%SMOKE_DIR%\input.txt
set SMOKE_CONFIG=%SMOKE_DIR%\config.json
set SMOKE_EN=%SMOKE_DIR%\en_chapters
set SMOKE_CN=%SMOKE_DIR%\cn_chapters
set SMOKE_MANIFEST=%SMOKE_DIR%\manifest.json

if exist "%SMOKE_DIR%" rmdir /s /q "%SMOKE_DIR%"
mkdir "%SMOKE_DIR%"

python -c "from pathlib import Path; p=Path(r'%SMOKE_INPUT%'); text='Chapter 1: Chapter 1: Test\n' + ('A paragraph for smoke test. '*260) + '\n\nChapter 2: Chapter 2: Test\n' + ('Another paragraph for smoke test. '*260); p.write_text(text, encoding='utf-8')"

python -c "import json; from pathlib import Path; cfg={'paths':{'input_file':r'%SMOKE_INPUT%','en_chapters_dir':r'%SMOKE_EN%','cn_chapters_dir':r'%SMOKE_CN%','manifest_file':r'%SMOKE_MANIFEST%'},'chapter_split':{'strict_chapter_sequence':True,'min_valid_chapter_chars':100},'lmstudio':{'base_url':'http://localhost:1234/v1','api_key':'lm-studio','model_id':'auto','temperature':0.2,'top_p':0.85,'request_timeout_seconds':2,'max_retries':1,'retry_sleep_seconds':1},'chunking':{'min_unit':'paragraph','initial_paragraphs_per_batch':8,'min_paragraphs_per_batch':1,'overflow_backoff_factor':0.5},'translation':{'skip_existing_done_chapters':True,'write_partial_file':True,'strip_model_preamble':True}}; Path(r'%SMOKE_CONFIG%').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')"

python -m youshengshu.cli --config "%SMOKE_CONFIG%" split --json > "%SMOKE_DIR%\split.json"
if errorlevel 1 goto smoke_fail

findstr /C:"manifest_file" "%SMOKE_DIR%\split.json" >nul
if errorlevel 1 goto smoke_fail

if not exist "%SMOKE_MANIFEST%" goto smoke_fail

python -m youshengshu.cli --config "%SMOKE_CONFIG%" status --json > "%SMOKE_DIR%\status.json"
if errorlevel 1 goto smoke_fail

findstr /C:"total" "%SMOKE_DIR%\status.json" >nul
if errorlevel 1 goto smoke_fail

findstr /C:"chapters" "%SMOKE_DIR%\status.json" >nul
if errorlevel 1 goto smoke_fail

rmdir /s /q "%SMOKE_DIR%"
goto smoke_ok

:smoke_fail
echo [ERROR] split/status smoke test failed.
if exist "%SMOKE_DIR%\split.json" type "%SMOKE_DIR%\split.json"
if exist "%SMOKE_DIR%\status.json" type "%SMOKE_DIR%\status.json"
if exist "%SMOKE_DIR%" rmdir /s /q "%SMOKE_DIR%"
exit /b 1

:smoke_ok

echo [CHECK] Positive grep — translation control features
git grep "chapterIndex" -- desktop/src >nul 2>nul
if errorlevel 1 (
  echo [ERROR] chapterIndex not found in desktop/src
  exit /b 1
)

git grep -e "--chapter-index" -- src/youshengshu desktop/src-tauri >nul 2>nul
if errorlevel 1 (
  echo [ERROR] --chapter-index not found in src/youshengshu or desktop/src-tauri
  exit /b 1
)

git grep "translated_paragraph_count" -- src/youshengshu tests desktop/src >nul 2>nul
if errorlevel 1 (
  echo [ERROR] translated_paragraph_count not found
  exit /b 1
)

git grep "resume_state_path" -- src/youshengshu tests desktop/src >nul 2>nul
if errorlevel 1 (
  echo [ERROR] resume_state_path not found
  exit /b 1
)

echo [CHECK] Negative grep — forbidden patterns must not exist in src/youshengshu
git grep "REFUSAL_PATTERNS" -- src/youshengshu >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  echo [ERROR] REFUSAL_PATTERNS must not exist in src/youshengshu
  git grep "REFUSAL_PATTERNS" -- src/youshengshu
  exit /b 1
)
git grep "en_path.replace" -- src/youshengshu >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  echo [ERROR] en_path.replace fallback must not exist in src/youshengshu
  git grep "en_path.replace" -- src/youshengshu
  exit /b 1
)
call :assert_no_grep "我无法" "src/youshengshu"
if errorlevel 1 exit /b 1
call :assert_no_grep "我不能" "src/youshengshu"
if errorlevel 1 exit /b 1
call :assert_no_grep "不能提供" "src/youshengshu"
if errorlevel 1 exit /b 1
call :assert_no_grep "作为AI" "src/youshengshu"
if errorlevel 1 exit /b 1
call :assert_no_grep "作为 AI" "src/youshengshu"
if errorlevel 1 exit /b 1

echo [CHECK] Frontend build
cd /d "%REPO_ROOT%desktop"
npm run build
if errorlevel 1 exit /b 1

echo [CHECK] Rust cargo check
call "%REPO_ROOT%setup_msvc_env.bat"
if errorlevel 1 exit /b 1
echo [CHECK] MSVC=%MSVC_VER% SDK=%SDK_VER%
cd /d "%REPO_ROOT%desktop\src-tauri"
cargo check
if errorlevel 1 exit /b 1

echo [CHECK] Rust cargo test
cargo test
if errorlevel 1 exit /b 1

echo [CHECK] OK
exit /b 0

:assert_no_grep
git grep "%~1" -- %~2 >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  echo [ERROR] Forbidden pattern found: %~1 in %~2
  git grep "%~1" -- %~2
  exit /b 1
)
exit /b 0
