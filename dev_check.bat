@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
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

echo [CHECK] TTS package import
python -m youshengshu_tts.cli --help >nul
if errorlevel 1 (
  echo [ERROR] youshengshu_tts.cli help failed
  exit /b 1
)

echo [CHECK] TTS config/status smoke
if not exist ".tmp_dev_check" mkdir ".tmp_dev_check"
python -c "import json; from pathlib import Path; cfg={'paths':{'source_mode':'cn_chapters_dir','source_path':'data/cn_chapters','output_dir':'.tmp_dev_check/audio_projects/default','manifest_file':'.tmp_dev_check/audio_projects/default/audio_manifest.json'},'segmentation':{'target_chars_min':80,'target_chars_max':180,'hard_chars_max':240,'punctuation':'\u3002\uff01\uff1f\uff1b\u2026\u2026\n'},'cosyvoice':{'base_url':'http://127.0.0.1:50000','mode':'sft','spk_id':'\u4e2d\u6587\u5973','prompt_text':'','prompt_audio_path':'','instruct_text':'','request_timeout_seconds':120,'max_retries':2,'retry_sleep_seconds':2,'sample_rate':22050},'audio':{'output_format':'wav','sample_rate':22050}}; Path('.tmp_dev_check/tts_config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')"
python -m youshengshu_tts.cli --config .tmp_dev_check\tts_config.json doctor --json > .tmp_dev_check\tts_doctor.json
if errorlevel 1 (
  echo [ERROR] TTS doctor failed
  exit /b 1
)

git grep "WorkspaceModule" -- desktop/src >nul 2>nul
if errorlevel 1 (
  echo [ERROR] WorkspaceModule not found
  exit /b 1
)

git grep "WorkspaceShell" -- desktop/src >nul 2>nul
if errorlevel 1 (
  echo [ERROR] WorkspaceShell not found
  exit /b 1
)

git grep "ModuleNav" -- desktop/src >nul 2>nul
if errorlevel 1 (
  echo [ERROR] ModuleNav not found
  exit /b 1
)

git grep "TtsWorkbench" -- desktop/src >nul 2>nul
if errorlevel 1 (
  echo [ERROR] TtsWorkbench not found
  exit /b 1
)

git grep "RvcWorkbench" -- desktop/src >nul 2>nul
if errorlevel 1 (
  echo [ERROR] RvcWorkbench not found
  exit /b 1
)

git grep "write_json_config" -- desktop/src desktop/src-tauri >nul 2>nul
if errorlevel 1 (
  echo [ERROR] write_json_config bridge not found
  exit /b 1
)

git grep "TranslationWorkbench" -- desktop/src >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  echo [ERROR] TranslationWorkbench must not exist in first version
  exit /b 1
)

git grep "write_tts_config" -- desktop/src desktop/src-tauri >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  echo [ERROR] write_tts_config must not exist; use write_json_config
  exit /b 1
)

git grep "run_tts_cli" -- desktop/src desktop/src-tauri >nul 2>nul
if errorlevel 1 (
  echo [ERROR] run_tts_cli bridge not found
  exit /b 1
)

git grep "_write_pcm_as_wav" -- src/youshengshu_tts >nul 2>nul
if errorlevel 1 (
  echo [ERROR] CosyVoice provider must wrap raw PCM as WAV
  exit /b 1
)

git grep "setframerate" -- src/youshengshu_tts >nul 2>nul
if errorlevel 1 (
  echo [ERROR] WAV writer must set sample rate
  exit /b 1
)

git grep "source_mode" -- src/youshengshu_tts desktop/src/features/tts >nul 2>nul
if errorlevel 1 (
  echo [ERROR] TTS source_mode missing
  exit /b 1
)

git grep "YSS_TTS_FAKE_PROVIDER" -- src/youshengshu_tts tests >nul 2>nul
if errorlevel 1 (
  echo [ERROR] TTS fake provider test switch missing
  exit /b 1
)

git grep "FakeTtsProvider" -- src/youshengshu_tts tests >nul 2>nul
if errorlevel 1 (
  echo [ERROR] FakeTtsProvider missing
  exit /b 1
)

git grep "ModuleHome" -- desktop/src >nul 2>nul
if errorlevel 1 (
  echo [ERROR] ModuleHome missing
  exit /b 1
)

git grep "工作台首页" -- desktop/src >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Workspace home label missing
  exit /b 1
)

git grep "setActiveModule] = useState<WorkspaceModule>" -- desktop/src/App.tsx >nul 2>nul
if errorlevel 1 (
  echo [ERROR] App must initially open ModuleHome
  exit /b 1
)

git grep "useState<WorkspaceModule>(\"home\")" -- desktop/src/App.tsx >nul 2>nul
if errorlevel 1 (
  git grep "useState<WorkspaceModule>" -- desktop/src/App.tsx | findstr /C:"home" >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] App initial activeModule must be home
    exit /b 1
  )
)

git grep "TTS 服务状态" -- desktop/src/features/tts >nul 2>nul
if errorlevel 1 (
  echo [ERROR] TTS service status card missing
  exit /b 1
)

git grep "CosyVoice 服务未连接" -- desktop/src/features/tts >nul 2>nul
if errorlevel 1 (
  echo [ERROR] TTS disconnected state message missing
  exit /b 1
)

git grep "生成第" -- desktop/src/features/tts >nul 2>nul
if errorlevel 1 (
  echo [ERROR] TTS chapter action buttons must include chapter number
  exit /b 1
)

git grep "TTS = 文本" -- desktop/src/features/rvc >nul 2>nul
if errorlevel 1 (
  echo [ERROR] RVC placeholder must explain TTS vs RVC
  exit /b 1
)

git grep "aria-current" -- desktop/src/components/workspace >nul 2>nul
if errorlevel 1 (
  echo [ERROR] ModuleNav must expose active state for accessibility
  exit /b 1
)

git grep "flex h-full w-full overflow-hidden" -- desktop/src/App.tsx desktop/src/features/tts >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Workspace module pages must use h-full w-full layout containers
  exit /b 1
)

git grep "h-full w-full" -- desktop/src/features/rvc >nul 2>nul
if errorlevel 1 (
  echo [ERROR] RVC page must use h-full w-full root layout
  exit /b 1
)

git grep "instruct2" -- desktop/src/features/tts >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  echo [ERROR] TTS UI must not expose instruct2
  exit /b 1
)

git grep "TtsSettings" -- desktop/src/features/tts >nul 2>nul
if errorlevel 1 (
  echo [ERROR] TTS settings state missing
  exit /b 1
)

git grep "buildTtsConfigPayload" -- desktop/src/features/tts >nul 2>nul
if errorlevel 1 (
  echo [ERROR] buildTtsConfigPayload missing
  exit /b 1
)

git grep "saveTtsConfigOnly" -- desktop/src/features/tts >nul 2>nul
if errorlevel 1 (
  echo [ERROR] saveTtsConfigOnly missing
  exit /b 1
)

git grep "refreshTtsStatusOnly" -- desktop/src/features/tts >nul 2>nul
if errorlevel 1 (
  echo [ERROR] refreshTtsStatusOnly missing
  exit /b 1
)

git grep "ttsLogs" -- desktop/src/features/tts >nul 2>nul
if errorlevel 1 (
  echo [ERROR] TTS log panel must use ttsLogs state
  exit /b 1
)

git grep "handlePickSource" -- desktop/src/features/tts/TtsWorkbench.tsx >nul 2>nul
if errorlevel 1 (
  echo [ERROR] handlePickSource missing
  exit /b 1
)

git grep "handlePickOutputDir" -- desktop/src/features/tts/TtsWorkbench.tsx >nul 2>nul
if errorlevel 1 (
  echo [ERROR] handlePickOutputDir missing
  exit /b 1
)

git grep "handlePickPromptAudio" -- desktop/src/features/tts/TtsWorkbench.tsx >nul 2>nul
if errorlevel 1 (
  echo [ERROR] handlePickPromptAudio missing
  exit /b 1
)

git grep "handleOpenAudioDir" -- desktop/src/features/tts/TtsWorkbench.tsx >nul 2>nul
if errorlevel 1 (
  echo [ERROR] handleOpenAudioDir missing
  exit /b 1
)

git grep "@tauri-apps/plugin-dialog" -- desktop/src/features/tts/TtsWorkbench.tsx >nul 2>nul
if errorlevel 1 (
  echo [ERROR] TtsWorkbench must import plugin-dialog open
  exit /b 1
)

findstr /C:"YSS_TTS_FAKE_PROVIDER=1" dev_check.bat | findstr /V /C:"git grep" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  echo [ERROR] dev_check must not run synthesize; synthesize is covered by pytest
  exit /b 1
)

git grep "def load_manifest(path: Path) -> TtsManifest:" -- src/youshengshu_tts/manifest.py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] load_manifest missing
  exit /b 1
)

git grep "manifest_status_payload" -- src/youshengshu_tts/manifest.py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] manifest_status_payload missing
  exit /b 1
)

git grep "def normalize_text" -- src/youshengshu_tts/text_segmenter.py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] normalize_text missing
  exit /b 1
)

git grep "def chapter_sort_key" -- src/youshengshu_tts/pipeline.py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] chapter_sort_key missing
  exit /b 1
)

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

echo [CHECK] Runtime preflight dry run
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%scripts\windows\preflight-runtime.ps1" -RepoRoot "%REPO_ROOT%." -DryRun
if errorlevel 1 exit /b 1

echo [CHECK] Frontend build
cd /d "%REPO_ROOT%desktop"
npm run build
if errorlevel 1 exit /b 1

if not exist "%REPO_ROOT%desktop\src\generated\buildInfo.ts" (
  echo [ERROR] buildInfo.ts not generated
  exit /b 1
)

findstr /C:"FRONTEND_BUILD_GIT_SHORT_HEAD" "%REPO_ROOT%desktop\src\generated\buildInfo.ts" >nul
if errorlevel 1 (
  echo [ERROR] buildInfo.ts missing FRONTEND_BUILD_GIT_SHORT_HEAD
  exit /b 1
)

git grep "FRONTEND_BUILD_GIT_SHORT_HEAD" -- desktop/src >nul 2>nul
if errorlevel 1 (
  echo [ERROR] frontend build head is not displayed or imported
  exit /b 1
)

git grep "git_short_head" -- desktop/src-tauri >nul 2>nul
if errorlevel 1 (
  echo [ERROR] runtime git_short_head is not exposed by Tauri
  exit /b 1
)

git grep "preflight-runtime.ps1" -- run_youshengshu.bat scripts >nul 2>nul
if errorlevel 1 (
  echo [ERROR] runtime preflight script is not wired
  exit /b 1
)

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
