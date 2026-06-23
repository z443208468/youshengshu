use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::Emitter;
use tokio::io::AsyncBufReadExt;
use tokio::process::Command;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PYTHON_MODULE_NAME: &str = "youshengshu.cli";
const LOG_EVENT_NAME: &str = "youshengshu-log";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
struct UiPaths {
    repo_root: String,
    config_path: String,
    python_command: String,
    input_file: String,
    en_chapters_dir: String,
    cn_chapters_dir: String,
    manifest_file: String,
    lm_studio_base_url: String,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ProcessOutput {
    code: i32,
    stdout: String,
    stderr: String,
    command_line: String,
    started_at: String,
    finished_at: String,
    log_file_path: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct AppContext {
    repo_root: String,
    config_path: String,
    python_command: String,
    is_valid_repo_root: bool,
    detected_from: String,
    cli_path: String,
}

#[derive(Debug, Serialize, Clone)]
struct LogPayload {
    stream: String,
    line: String,
}

/// Holds task lifecycle so concurrent starts cannot race between check and spawn.
enum ActiveTask {
    Starting,
    Running(tokio::process::Child),
}

struct ActiveProcess(Mutex<Option<ActiveTask>>);

fn clear_active_task(state: &tauri::State<'_, ActiveProcess>) {
    let mut guard = state.0.lock().unwrap();
    *guard = None;
}

/// Persists UI log lines (config save, errors, etc.) for the app session.
struct UiSessionLog(Mutex<Option<std::fs::File>>);

fn open_session_log_file(repo_root: &std::path::Path) -> Result<std::fs::File, String> {
    let log_dir = repo_root.join("logs");
    std::fs::create_dir_all(&log_dir)
        .map_err(|e| format!("创建日志目录失败: {e}"))?;
    let filename = format!("youshengshu-session-{}.log", iso_now_compact());
    let path = log_dir.join(&filename);
    let file = std::fs::File::create(&path)
        .map_err(|e| format!("创建会话日志失败: {e}"))?;
    Ok(file)
}

fn append_session_log(state: &UiSessionLog, stream: &str, line: &str) {
    let mut guard = state.0.lock().unwrap();
    if guard.is_none() {
        let repo_root = find_repo_root().unwrap_or_else(|| {
            std::env::current_dir().unwrap_or_else(|_| std::path::PathBuf::from("."))
        });
        if let Ok(file) = open_session_log_file(&repo_root) {
            *guard = Some(file);
        }
    }
    if let Some(ref mut file) = *guard {
        write_log_line(file, stream, line);
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn iso_now() -> String {
    let dur = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default();
    let secs = dur.as_secs();
    // Convert to YYYY-MM-DDTHH:MM:SS+09:00 (JST fixed offset)
    // Days since epoch
    let days = secs / 86400;
    let time_secs = secs % 86400;
    let hours = time_secs / 3600;
    let minutes = (time_secs % 3600) / 60;
    let seconds = time_secs % 60;

    // Gregorian calendar date from days since epoch
    let mut y = 1970i64;
    let mut remaining = days as i64;
    loop {
        let days_in_year = if is_leap(y) { 366 } else { 365 };
        if remaining < days_in_year {
            break;
        }
        remaining -= days_in_year;
        y += 1;
    }
    let month_days = if is_leap(y) {
        [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    } else {
        [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    };
    let mut m = 1usize;
    for &md in month_days.iter() {
        if remaining < md {
            break;
        }
        remaining -= md;
        m += 1;
    }
    let d = remaining + 1;
    // JST = UTC+9
    let jst_hours = (hours + 9) % 24;
    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}+09:00",
        y, m, d, jst_hours, minutes, seconds
    )
}

fn iso_now_compact() -> String {
    // YYYYMMDD-HHMMSS for log filenames
    let full = iso_now();
    full[..19].replace("-", "").replace("T", "-").replace(":", "")
}

fn is_leap(year: i64) -> bool {
    (year % 4 == 0 && year % 100 != 0) || year % 400 == 0
}

fn is_repo_root(path: &std::path::Path) -> bool {
    path.join("src").join("youshengshu").join("cli.py").is_file()
        && path
            .join("desktop")
            .join("src-tauri")
            .join("tauri.conf.json")
            .is_file()
        && path.join("requirements.txt").is_file()
}

fn repo_root_candidates() -> Vec<std::path::PathBuf> {
    let mut candidates = Vec::new();

    if let Ok(value) = std::env::var("YSS_REPO_ROOT") {
        candidates.push(std::path::PathBuf::from(value));
    }

    if let Ok(current_dir) = std::env::current_dir() {
        candidates.push(current_dir);
    }

    if let Ok(current_exe) = std::env::current_exe() {
        if let Some(parent) = current_exe.parent() {
            candidates.push(parent.to_path_buf());
        }
    }

    if let Some(manifest_dir) = option_env!("CARGO_MANIFEST_DIR") {
        candidates.push(std::path::PathBuf::from(manifest_dir));
    }

    candidates
}

fn canonicalize_if_possible(p: std::path::PathBuf) -> std::path::PathBuf {
    let canonical = std::fs::canonicalize(&p).unwrap_or(p);
    // On Windows, std::fs::canonicalize returns paths with \\?\ prefix
    // (extended-length path). This prefix breaks subprocess execution
    // (current_dir, env, etc.) so we strip it.
    let s = canonical.to_string_lossy().to_string();
    if cfg!(windows) && s.starts_with("\\\\?\\") {
        std::path::PathBuf::from(&s[4..])
    } else {
        canonical
    }
}

fn find_repo_root() -> Option<std::path::PathBuf> {
    for candidate in repo_root_candidates() {
        let canonical = canonicalize_if_possible(candidate);

        for ancestor in canonical.ancestors() {
            if is_repo_root(ancestor) {
                return Some(ancestor.to_path_buf());
            }
        }
    }
    None
}

fn detect_source() -> String {
    if std::env::var("YSS_REPO_ROOT").is_ok() {
        "YSS_REPO_ROOT"
    } else if option_env!("CARGO_MANIFEST_DIR").is_some() {
        "CARGO_MANIFEST_DIR"
    } else if let Ok(exe) = std::env::current_exe() {
        if let Some(_parent) = exe.parent() {
            "current_exe"
        } else {
            "current_dir"
        }
    } else {
        "current_dir"
    }
    .to_string()
}

fn default_python_command(repo_root: &std::path::Path) -> String {
    // Prefer .venv on Windows, then .venv/bin on Unix, fallback "python"
    let venv_script = repo_root.join(".venv").join("Scripts").join("python.exe");
    if venv_script.exists() {
        return venv_script.to_string_lossy().to_string();
    }
    let venv_bin = repo_root.join(".venv").join("bin").join("python");
    if venv_bin.exists() {
        return venv_bin.to_string_lossy().to_string();
    }
    "python".to_string()
}

// ---------------------------------------------------------------------------
// Log file writer
// ---------------------------------------------------------------------------

fn resolve_repo_relative_path(repo_root: &str, raw_path: &str) -> std::path::PathBuf {
    let path = std::path::PathBuf::from(raw_path);
    if path.is_absolute() {
        path
    } else {
        std::path::PathBuf::from(repo_root).join(path)
    }
}

struct OpenedLogFile {
    file: std::fs::File,
    path: std::path::PathBuf,
}

fn open_log_file(repo_root: &std::path::Path) -> Result<OpenedLogFile, String> {
    let log_dir = repo_root.join("logs");
    std::fs::create_dir_all(&log_dir)
        .map_err(|e| format!("创建日志目录失败: {e}"))?;
    let filename = format!("youshengshu-ui-{}.log", iso_now_compact());
    let path = log_dir.join(&filename);
    let file = std::fs::File::create(&path)
        .map_err(|e| format!("创建日志文件失败: {e}"))?;
    Ok(OpenedLogFile { file, path })
}

fn write_log_line(file: &mut std::fs::File, stream: &str, line: &str) {
    use std::io::Write;
    let timestamp = iso_now();
    let _ = writeln!(file, "[{}][{}] {}", timestamp, stream, line);
}

// ---------------------------------------------------------------------------
// Command: resolve_app_context
// ---------------------------------------------------------------------------

#[tauri::command]
fn resolve_app_context() -> Result<AppContext, String> {
    let repo_root = find_repo_root()
        .ok_or_else(|| "无法定位项目根目录。请从仓库根目录运行 run_youshengshu.bat。".to_string())?;

    let cli_path = repo_root.join("src").join("youshengshu").join("cli.py");
    let python_cmd = default_python_command(&repo_root);

    Ok(AppContext {
        repo_root: repo_root.to_string_lossy().to_string(),
        config_path: "config/default_config.json".to_string(),
        python_command: python_cmd,
        is_valid_repo_root: true,
        detected_from: detect_source(),
        cli_path: cli_path.to_string_lossy().to_string(),
    })
}

// ---- Backward compat ----

#[tauri::command]
fn get_repo_root() -> String {
    find_repo_root()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|| std::env::current_dir()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string())
}

// ---------------------------------------------------------------------------
// Command: resolve_path
// ---------------------------------------------------------------------------

/// Resolve a potentially relative path against repo_root, returning an absolute path.
#[tauri::command]
fn resolve_path(repo_root: String, raw_path: String) -> Result<String, String> {
    Ok(resolve_repo_relative_path(&repo_root, &raw_path)
        .to_string_lossy()
        .to_string())
}

// ---------------------------------------------------------------------------
// Command: read_youshengshu_config
// ---------------------------------------------------------------------------

#[tauri::command]
fn read_youshengshu_config(
    repo_root: String,
    config_path: String,
) -> Result<serde_json::Value, String> {
    let path_buf = resolve_repo_relative_path(&repo_root, &config_path);
    let path = path_buf.as_path();
    if path.exists() {
        let contents = std::fs::read_to_string(path)
            .map_err(|e| format!("读取配置失败: {} ({e})", path.display()))?;
        serde_json::from_str(&contents)
            .map_err(|e| format!("配置格式错误: {} ({e})", path.display()))
    } else {
        Ok(serde_json::json!({
            "paths": {
                "input_file": "data/input/ReZero_Watching_Him_Die.txt",
                "en_chapters_dir": "data/en_chapters",
                "cn_chapters_dir": "data/cn_chapters",
                "manifest_file": "data/manifests/translation_manifest.json"
            },
            "chapter_split": {
                "strict_chapter_sequence": true,
                "min_valid_chapter_chars": 3000
            },
            "lmstudio": {
                "base_url": "http://localhost:1234/v1",
                "api_key": "lm-studio",
                "model_id": "auto",
                "temperature": 0.2,
                "top_p": 0.85,
                "request_timeout_seconds": 1800,
                "max_retries": 1,
                "retry_sleep_seconds": 5
            },
            "chunking": {
                "min_unit": "paragraph",
                "initial_paragraphs_per_batch": 8,
                "min_paragraphs_per_batch": 1,
                "overflow_backoff_factor": 0.5
            },
            "translation": {
                "skip_existing_done_chapters": true,
                "write_partial_file": true,
                "strip_model_preamble": true
            }
        }))
    }
}

// ---------------------------------------------------------------------------
// Command: write_youshengshu_config
// ---------------------------------------------------------------------------

fn ensure_json_object<'a>(
    parent: &'a mut serde_json::Map<String, serde_json::Value>,
    key: &str,
) -> &'a mut serde_json::Map<String, serde_json::Value> {
    let value = parent
        .entry(key.to_string())
        .or_insert_with(|| serde_json::Value::Object(serde_json::Map::new()));

    if !value.is_object() {
        *value = serde_json::Value::Object(serde_json::Map::new());
    }

    value.as_object_mut().unwrap()
}

#[tauri::command]
fn write_youshengshu_config(paths: UiPaths) -> Result<(), String> {
    if paths.repo_root.trim().is_empty() {
        return Err("项目根目录 repoRoot 为空，请先在 UI 中选择仓库根目录".to_string());
    }

    let repo_root_path = std::path::Path::new(&paths.repo_root);
    let cli_path = repo_root_path.join("src").join("youshengshu").join("cli.py");
    if !cli_path.exists() {
        return Err(format!(
            "项目根目录无效，未找到 Python CLI: {}。请选择包含 src/youshengshu/cli.py 的仓库根目录。",
            cli_path.display()
        ));
    }

    if paths.config_path.trim().is_empty() {
        return Err("配置文件路径为空，请设置 config/default_config.json 或选择配置文件路径".to_string());
    }

    let config_path_buf = resolve_repo_relative_path(&paths.repo_root, &paths.config_path);
    let config_path = config_path_buf.as_path();

    let mut config: serde_json::Value = if config_path.exists() {
        let contents = std::fs::read_to_string(config_path)
            .map_err(|e| format!("读取配置失败: {} ({e})", config_path.display()))?;
        serde_json::from_str(&contents).unwrap_or_default()
    } else {
        serde_json::Value::Null
    };

    let paths_obj = serde_json::json!({
        "input_file": paths.input_file,
        "en_chapters_dir": paths.en_chapters_dir,
        "cn_chapters_dir": paths.cn_chapters_dir,
        "manifest_file": paths.manifest_file,
    });

    if !config.is_object() {
        config = serde_json::json!({
            "chapter_split": {
                "strict_chapter_sequence": true,
                "min_valid_chapter_chars": 3000
            },
            "chunking": {
                "min_unit": "paragraph",
                "initial_paragraphs_per_batch": 8,
                "min_paragraphs_per_batch": 1,
                "overflow_backoff_factor": 0.5
            },
            "translation": {
                "skip_existing_done_chapters": true,
                "write_partial_file": true,
                "strip_model_preamble": true
            }
        });
    }

    if let Some(obj) = config.as_object_mut() {
        obj.insert("paths".to_string(), paths_obj);

        {
            let lm_obj = ensure_json_object(obj, "lmstudio");

            lm_obj.insert(
                "base_url".to_string(),
                serde_json::Value::String(paths.lm_studio_base_url.clone()),
            );
            lm_obj
                .entry("api_key".to_string())
                .or_insert_with(|| serde_json::Value::String("lm-studio".to_string()));
            lm_obj
                .entry("model_id".to_string())
                .or_insert_with(|| serde_json::Value::String("auto".to_string()));
            lm_obj
                .entry("temperature".to_string())
                .or_insert_with(|| serde_json::json!(0.2));
            lm_obj
                .entry("top_p".to_string())
                .or_insert_with(|| serde_json::json!(0.85));

            lm_obj.remove(&format!("max_{}", "output_tokens"));

            lm_obj
                .entry("retry_sleep_seconds".to_string())
                .or_insert_with(|| serde_json::json!(5));
        }

        {
            let chunk_obj = ensure_json_object(obj, "chunking");

            chunk_obj.remove("context_tokens");
            chunk_obj.remove("reserved_prompt_tokens");
            chunk_obj.remove("reserved_output_tokens");
            chunk_obj.remove("safety_ratio");
            chunk_obj.remove("english_chars_per_token");
            chunk_obj.remove("cjk_chars_per_token");
            chunk_obj.remove("split_mode");
            chunk_obj.remove("allow_word_split");

            chunk_obj
                .entry("min_unit".to_string())
                .or_insert_with(|| serde_json::Value::String("paragraph".to_string()));
            chunk_obj
                .entry("initial_paragraphs_per_batch".to_string())
                .or_insert_with(|| serde_json::json!(8));
            chunk_obj
                .entry("min_paragraphs_per_batch".to_string())
                .or_insert_with(|| serde_json::json!(1));
            chunk_obj
                .entry("overflow_backoff_factor".to_string())
                .or_insert_with(|| serde_json::json!(0.5));
        }
    }

    if let Some(parent) = config_path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("创建目录失败: {e}"))?;
    }

    let json_string =
        serde_json::to_string_pretty(&config).map_err(|e| format!("序列化配置失败: {e}"))?;
    std::fs::write(config_path, json_string).map_err(|e| format!("写入配置失败: {e}"))?;

    Ok(())
}

#[tauri::command]
fn append_ui_log(
    stream: String,
    line: String,
    ui_log: tauri::State<'_, UiSessionLog>,
) -> Result<(), String> {
    append_session_log(&ui_log, &stream, &line);
    Ok(())
}

// ---------------------------------------------------------------------------
// Command: build_python_command_spec — centralized command builder
// ---------------------------------------------------------------------------

struct CommandSpec {
    program: String,
    args: Vec<String>,
    cwd: std::path::PathBuf,
    env_pythonpath: std::path::PathBuf,
    display: String,
}

fn build_python_cli_command(
    repo_root: &str,
    python_command: &str,
    cli_command: &str,
    config_path: &str,
    json_output: bool,
    max_chapters: Option<u32>,
    chapter_index: Option<u32>,
) -> Result<CommandSpec, String> {
    let repo_root_path = std::path::PathBuf::from(repo_root);
    let cli_path = repo_root_path.join("src").join("youshengshu").join("cli.py");
    if !cli_path.exists() {
        return Err(format!(
            "项目根目录无效，未找到 Python CLI: {}。请选择包含 src/youshengshu/cli.py 的仓库根目录。",
            cli_path.display()
        ));
    }

    let mut args: Vec<String> = vec![
        "-m".to_string(),
        PYTHON_MODULE_NAME.to_string(),
        "--config".to_string(),
        config_path.to_string(),
        cli_command.to_string(),
    ];

    if json_output {
        args.push("--json".to_string());
    }

    if cli_command == "translate" {
        if let Some(mc) = max_chapters {
            if mc > 0 {
                args.push("--max-chapters".to_string());
                args.push(mc.to_string());
            }
        }

        if let Some(idx) = chapter_index {
            if idx > 0 {
                args.push("--chapter-index".to_string());
                args.push(idx.to_string());
            }
        }
    }

    let src_dir = repo_root_path.join("src");
    let display = format!("{} {}", python_command, args.join(" "));

    Ok(CommandSpec {
        program: python_command.to_string(),
        args,
        cwd: repo_root_path,
        env_pythonpath: src_dir,
        display,
    })
}

// ---------------------------------------------------------------------------
// Command: run_python_cli
// ---------------------------------------------------------------------------

#[tauri::command]
async fn run_python_cli(
    app: tauri::AppHandle,
    repo_root: String,
    python_command: String,
    cli_command: String,
    config_path: String,
    json_output: bool,
    max_chapters: Option<u32>,
    chapter_index: Option<u32>,
    state: tauri::State<'_, ActiveProcess>,
) -> Result<ProcessOutput, String> {
    // Validate command
    let allowed = ["split", "status", "translate", "all", "doctor"];
    if !allowed.contains(&cli_command.as_str()) {
        return Err(format!("不允许的命令: {}", cli_command));
    }

    if repo_root.trim().is_empty() {
        return Err("项目根目录 repoRoot 为空，请先在 UI 中选择仓库根目录".to_string());
    }

    if config_path.trim().is_empty() {
        return Err("配置文件路径为空，请设置 config/default_config.json 或选择配置文件路径".to_string());
    }

    // Concurrency check — reserve slot before spawn
    {
        let mut guard = state.0.lock().unwrap();
        if guard.is_some() {
            return Err("已有任务正在运行，请先停止或等待完成。".to_string());
        }
        *guard = Some(ActiveTask::Starting);
    }

    // Build command spec
    let spec = match build_python_cli_command(
        &repo_root,
        &python_command,
        &cli_command,
        &config_path,
        json_output,
        max_chapters,
        chapter_index,
    ) {
        Ok(spec) => spec,
        Err(e) => {
            clear_active_task(&state);
            return Err(e);
        }
    };

    let started_at = iso_now();

    // Open log file
    let repo_root_path = std::path::PathBuf::from(&repo_root);
    let opened_log = match open_log_file(&repo_root_path) {
        Ok(opened) => opened,
        Err(e) => {
            clear_active_task(&state);
            return Err(e);
        }
    };
    let log_file_path = opened_log.path.to_string_lossy().to_string();
    let log_file = std::sync::Arc::new(std::sync::Mutex::new(opened_log.file));
    write_log_line(&mut *log_file.lock().unwrap(), "system", &format!("Working directory: {}", repo_root));
    write_log_line(&mut *log_file.lock().unwrap(), "system", &format!("Command: {}", spec.display));

    // Emit log to frontend
    let _ = app.emit(
        LOG_EVENT_NAME,
        LogPayload {
            stream: "system".to_string(),
            line: format!("Working directory: {}", repo_root),
        },
    );
    let _ = app.emit(
        LOG_EVENT_NAME,
        LogPayload {
            stream: "system".to_string(),
            line: format!("Command: {}", spec.display),
        },
    );

    // Build and spawn process
    let mut cmd = Command::new(&spec.program);
    cmd.current_dir(&spec.cwd);

    // Force UTF-8 stdio so Chinese JSON output is not corrupted/lost when the
    // child is launched by the GUI process without a console (Windows defaults
    // to the ANSI codepage for piped stdout otherwise).
    cmd.env("PYTHONIOENCODING", "utf-8");
    cmd.env("PYTHONUTF8", "1");
    cmd.env("PYTHONUNBUFFERED", "1");

    // Merge PYTHONPATH: prepend repo's src/ so it takes priority over venv site-packages
    let pythonpath_val = spec.env_pythonpath.to_string_lossy().to_string();
    if let Ok(old) = std::env::var("PYTHONPATH") {
        if !old.trim().is_empty() {
            cmd.env("PYTHONPATH", format!("{};{}", pythonpath_val, old));
        } else {
            cmd.env("PYTHONPATH", &pythonpath_val);
        }
    } else {
        cmd.env("PYTHONPATH", &pythonpath_val);
    }

    // Python module probe: log where youshengshu.cli actually loads from
    let probe_result = std::process::Command::new(&spec.program)
        .current_dir(&spec.cwd)
        .env("PYTHONPATH", &pythonpath_val)
        .env("PYTHONIOENCODING", "utf-8")
        .env("PYTHONUTF8", "1")
        .arg("-c")
        .arg("import youshengshu.cli as c; print('CLI_FILE=' + str(c.__file__)); print('HAS_MAIN=' + str(hasattr(c, 'main')))")
        .output();

    if let Ok(probe) = probe_result {
        let probe_out = String::from_utf8_lossy(&probe.stdout).to_string();
        let probe_err = String::from_utf8_lossy(&probe.stderr).to_string();
        write_log_line(&mut *log_file.lock().unwrap(), "system", &format!("Python probe: {}", probe_out.trim().replace('\n', " | ")));
        let _ = app.emit(LOG_EVENT_NAME, LogPayload {
            stream: "system".to_string(),
            line: format!("Python probe: {}", probe_out.trim()),
        });
        if !probe_err.trim().is_empty() {
            write_log_line(&mut *log_file.lock().unwrap(), "stderr", &probe_err.trim());
            let _ = app.emit(LOG_EVENT_NAME, LogPayload {
                stream: "stderr".to_string(),
                line: format!("Python probe stderr: {}", probe_err.trim()),
            });
        }
    } else if let Err(e) = probe_result {
        write_log_line(&mut *log_file.lock().unwrap(), "stderr", &format!("Python probe failed: {e}"));
    }

    for arg in &spec.args {
        cmd.arg(arg);
    }

    let mut child = cmd
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .map_err(|e| {
            clear_active_task(&state);
            format!("启动进程失败: {e}")
        })?;

    let stdout_handle = child
        .stdout
        .take()
        .ok_or_else(|| "无法获取 stdout".to_string())?;
    let stderr_handle = child
        .stderr
        .take()
        .ok_or_else(|| "无法获取 stderr".to_string())?;

    // Store the actual running child
    {
        let mut guard = state.0.lock().unwrap();
        *guard = Some(ActiveTask::Running(child));
    }

    // Read stdout and stderr concurrently
    let app_handle = app.clone();
    let log_file_clone = log_file.clone();
    let stdout_reader = tokio::spawn(async move {
        let reader = tokio::io::BufReader::new(stdout_handle);
        let mut lines = reader.lines();
        let mut collected = String::new();
        while let Ok(Some(line)) = lines.next_line().await {
            collected.push_str(&line);
            collected.push('\n');
            write_log_line(&mut *log_file_clone.lock().unwrap(), "stdout", &line);
            let payload = LogPayload {
                stream: "stdout".to_string(),
                line: line.clone(),
            };
            let _ = app_handle.emit(LOG_EVENT_NAME, payload);
        }
        collected
    });

    let app_handle2 = app.clone();
    let log_file_clone2 = log_file.clone();
    let stderr_reader = tokio::spawn(async move {
        let reader = tokio::io::BufReader::new(stderr_handle);
        let mut lines = reader.lines();
        let mut collected = String::new();
        while let Ok(Some(line)) = lines.next_line().await {
            collected.push_str(&line);
            collected.push('\n');
            write_log_line(&mut *log_file_clone2.lock().unwrap(), "stderr", &line);
            let payload = LogPayload {
                stream: "stderr".to_string(),
                line: line.clone(),
            };
            let _ = app_handle2.emit(LOG_EVENT_NAME, payload);
        }
        collected
    });

    // Wait for both readers
    let (stdout, stderr) = tokio::join!(stdout_reader, stderr_reader);
    let stdout = stdout.unwrap_or_default();
    let stderr = stderr.unwrap_or_default();

    // Take the child out of the mutex so we can wait without holding the lock
    let mut child_to_wait = {
        let mut guard = state.0.lock().unwrap();
        match guard.take() {
            Some(ActiveTask::Running(child)) => Some(child),
            _ => None,
        }
    };
    let status = if let Some(ref mut child) = child_to_wait {
        child.wait().await.unwrap_or_default()
    } else {
        std::process::ExitStatus::default()
    };
    let code = status.code().unwrap_or(-1);
    let finished_at = iso_now();

    let stdout_len = stdout.len();
    let stderr_len = stderr.len();
    let summary = format!("Process finished: code={}, stdout_len={}, stderr_len={}", code, stdout_len, stderr_len);
    write_log_line(&mut *log_file.lock().unwrap(), "system", &summary);
    let _ = app.emit(
        LOG_EVENT_NAME,
        LogPayload {
            stream: "system".to_string(),
            line: summary,
        },
    );

    Ok(ProcessOutput {
        code,
        stdout,
        stderr,
        command_line: spec.display,
        started_at,
        finished_at,
        log_file_path,
    })
}

// ---------------------------------------------------------------------------
// Command: kill_python_process
// ---------------------------------------------------------------------------

#[tauri::command]
async fn kill_python_process(
    state: tauri::State<'_, ActiveProcess>,
) -> Result<(), String> {
    let child_to_kill = {
        let mut guard = state.0.lock().unwrap();
        match guard.take() {
            Some(ActiveTask::Running(child)) => Some(child),
            Some(ActiveTask::Starting) | None => None,
        }
    };
    if let Some(mut child) = child_to_kill {
        child
            .kill()
            .await
            .map_err(|e| format!("终止进程失败: {e}"))?;
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// App entry
// ---------------------------------------------------------------------------

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .manage(ActiveProcess(Mutex::new(None)))
        .manage(UiSessionLog(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![
            get_repo_root,
            resolve_app_context,
            resolve_path,
            read_youshengshu_config,
            write_youshengshu_config,
            append_ui_log,
            run_python_cli,
            kill_python_process,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detects_is_repo_root_with_markers() {
        // Create a temp dir with the expected marker files
        let dir = std::env::temp_dir().join("yss_test_repo_root");
        let _ = std::fs::remove_dir_all(&dir);

        // Create the marker files
        let src_dir = dir.join("src").join("youshengshu");
        std::fs::create_dir_all(&src_dir).unwrap();
        std::fs::write(src_dir.join("cli.py"), "# test").unwrap();

        let desktop_dir = dir.join("desktop").join("src-tauri");
        std::fs::create_dir_all(&desktop_dir).unwrap();
        std::fs::write(desktop_dir.join("tauri.conf.json"), "{}").unwrap();

        std::fs::write(dir.join("requirements.txt"), "# test").unwrap();

        assert!(is_repo_root(&dir));

        // Cleanup
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn ui_paths_deserializes_lm_studio_base_url() {
        let json = r#"{
            "repoRoot": "D:\\repo",
            "configPath": "config/default_config.json",
            "pythonCommand": "python",
            "inputFile": "data/input/book.txt",
            "enChaptersDir": "data/en_chapters",
            "cnChaptersDir": "data/cn_chapters",
            "manifestFile": "data/manifests/translation_manifest.json",
            "lmStudioBaseUrl": "http://localhost:1234/v1"
        }"#;
        let paths: UiPaths = serde_json::from_str(json).unwrap();
        assert_eq!(paths.lm_studio_base_url, "http://localhost:1234/v1");
    }

    #[test]
    fn rejects_non_repo_root() {
        let dir = std::env::temp_dir().join("yss_test_non_repo");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        assert!(!is_repo_root(&dir));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn find_repo_root_uses_yss_env_var() {
        // Set up a temp directory as a fake repo
        let dir = std::env::temp_dir().join("yss_test_find_root");
        let _ = std::fs::remove_dir_all(&dir);

        let src_dir = dir.join("src").join("youshengshu");
        std::fs::create_dir_all(&src_dir).unwrap();
        std::fs::write(src_dir.join("cli.py"), "# test").unwrap();

        let desktop_dir = dir.join("desktop").join("src-tauri");
        std::fs::create_dir_all(&desktop_dir).unwrap();
        std::fs::write(desktop_dir.join("tauri.conf.json"), "{}").unwrap();

        std::fs::write(dir.join("requirements.txt"), "# test").unwrap();

        // Set env var and test
        std::env::set_var("YSS_REPO_ROOT", dir.to_str().unwrap());
        let found = find_repo_root();
        assert!(found.is_some());
        let found_path = found.unwrap();
        let expected = canonicalize_if_possible(dir.clone());
        let actual = canonicalize_if_possible(found_path);
        assert_eq!(actual, expected);

        std::env::remove_var("YSS_REPO_ROOT");
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn build_python_cli_command_translate_with_chapter_index() {
        let dir = std::env::temp_dir().join("yss_test_build_cmd");
        let _ = std::fs::remove_dir_all(&dir);
        let src_dir = dir.join("src").join("youshengshu");
        std::fs::create_dir_all(&src_dir).unwrap();
        std::fs::write(src_dir.join("cli.py"), "# test").unwrap();

        let spec = build_python_cli_command(
            dir.to_str().unwrap(),
            "python",
            "translate",
            "config/default_config.json",
            false,
            None,
            Some(4),
        )
        .unwrap();

        assert!(spec.args.contains(&"--chapter-index".to_string()));
        assert!(spec.args.contains(&"4".to_string()));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn build_python_cli_command_translate_with_max_and_chapter_index() {
        let dir = std::env::temp_dir().join("yss_test_build_cmd2");
        let _ = std::fs::remove_dir_all(&dir);
        let src_dir = dir.join("src").join("youshengshu");
        std::fs::create_dir_all(&src_dir).unwrap();
        std::fs::write(src_dir.join("cli.py"), "# test").unwrap();

        let spec = build_python_cli_command(
            dir.to_str().unwrap(),
            "python",
            "translate",
            "config/default_config.json",
            false,
            Some(1),
            Some(4),
        )
        .unwrap();

        assert!(spec.args.contains(&"--max-chapters".to_string()));
        assert!(spec.args.contains(&"--chapter-index".to_string()));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn build_python_cli_command_split_omits_chapter_index() {
        let dir = std::env::temp_dir().join("yss_test_build_cmd3");
        let _ = std::fs::remove_dir_all(&dir);
        let src_dir = dir.join("src").join("youshengshu");
        std::fs::create_dir_all(&src_dir).unwrap();
        std::fs::write(src_dir.join("cli.py"), "# test").unwrap();

        let spec = build_python_cli_command(
            dir.to_str().unwrap(),
            "python",
            "split",
            "config/default_config.json",
            true,
            None,
            Some(4),
        )
        .unwrap();

        assert!(!spec.args.iter().any(|a| a.contains("chapter-index")));

        let _ = std::fs::remove_dir_all(&dir);
    }
}
