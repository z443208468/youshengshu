use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::Emitter;
use tokio::io::AsyncBufReadExt;
use tokio::process::{Child, Command};

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
    lmstudio_base_url: String,
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

/// Holds an optional reference to a running child process so we can kill it.
struct ActiveProcess(Mutex<Option<Child>>);

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
    std::fs::canonicalize(&p).unwrap_or(p)
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

fn open_log_file(repo_root: &std::path::Path) -> Result<std::fs::File, String> {
    let log_dir = repo_root.join("logs");
    std::fs::create_dir_all(&log_dir)
        .map_err(|e| format!("创建日志目录失败: {e}"))?;
    let filename = format!("youshengshu-ui-{}.log", iso_now_compact());
    let path = log_dir.join(&filename);
    let file = std::fs::File::create(&path)
        .map_err(|e| format!("创建日志文件失败: {e}"))?;
    Ok(file)
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
    let root = std::path::PathBuf::from(&repo_root);
    let path = std::path::PathBuf::from(&raw_path);

    if path.is_absolute() {
        Ok(path.to_string_lossy().to_string())
    } else {
        let resolved = root.join(&path);
        Ok(resolved.to_string_lossy().to_string())
    }
}

// ---------------------------------------------------------------------------
// Command: read_youshengshu_config
// ---------------------------------------------------------------------------

#[tauri::command]
fn read_youshengshu_config(config_path: String) -> Result<serde_json::Value, String> {
    let path = std::path::Path::new(&config_path);
    if path.exists() {
        let contents =
            std::fs::read_to_string(path).map_err(|e| format!("读取配置失败: {e}"))?;
        serde_json::from_str(&contents).map_err(|e| format!("配置格式错误: {e}"))
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
                "max_output_tokens": 4096,
                "request_timeout_seconds": 600,
                "max_retries": 3,
                "retry_sleep_seconds": 5
            },
            "chunking": {
                "context_tokens": 8192,
                "reserved_prompt_tokens": 1800,
                "reserved_output_tokens": 4096,
                "safety_ratio": 0.72,
                "english_chars_per_token": 4.0,
                "cjk_chars_per_token": 1.2
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

    let config_path = std::path::Path::new(&paths.config_path);

    let mut config: serde_json::Value = if config_path.exists() {
        let contents =
            std::fs::read_to_string(config_path).map_err(|e| format!("读取配置失败: {e}"))?;
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
                "context_tokens": 8192,
                "reserved_prompt_tokens": 1800,
                "reserved_output_tokens": 4096,
                "safety_ratio": 0.72,
                "english_chars_per_token": 4.0,
                "cjk_chars_per_token": 1.2
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
        let lmstudio = serde_json::json!({
            "base_url": paths.lmstudio_base_url,
            "api_key": "lm-studio",
            "model_id": "auto",
            "temperature": 0.2,
            "top_p": 0.85,
            "max_output_tokens": 4096,
            "request_timeout_seconds": 600,
            "max_retries": 3,
            "retry_sleep_seconds": 5
        });
        obj.insert("lmstudio".to_string(), lmstudio);
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
) -> Result<CommandSpec, String> {
    let repo_root_path = std::path::PathBuf::from(repo_root);
    let cli_path = repo_root_path.join("src").join("youshengshu").join("cli.py");
    if !cli_path.exists() {
        return Err(format!(
            "项目根目录无效，未找到 Python CLI: {}。请选择包含 src/youshengshu/cli.py 的仓库根目录。",
            cli_path.display()
        ));
    }

    let args_str = format!("{}", cli_command);
    let mut args: Vec<String> = vec![
        "-m".to_string(),
        PYTHON_MODULE_NAME.to_string(),
        cli_command.to_string(),
        "--config".to_string(),
        config_path.to_string(),
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
    }

    let src_dir = repo_root_path.join("src");
    let display = format!("{} -m youshengshu.cli {} --config {}", python_command, args_str, config_path);

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

    // Concurrency check
    {
        let guard = state.0.lock().unwrap();
        if guard.is_some() {
            return Err("已有任务正在运行，请先停止或等待完成。".to_string());
        }
    }

    // Build command spec
    let spec = build_python_cli_command(
        &repo_root,
        &python_command,
        &cli_command,
        &config_path,
        json_output,
        max_chapters,
    )?;

    let started_at = iso_now();

    // Open log file
    let repo_root_path = std::path::PathBuf::from(&repo_root);
    let mut log_file = open_log_file(&repo_root_path)?;
    write_log_line(&mut log_file, "system", &format!("Working directory: {}", repo_root));
    write_log_line(&mut log_file, "system", &format!("Command: {}", spec.display));

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
    cmd.current_dir(&spec.cwd)
        .env("PYTHONPATH", &spec.env_pythonpath);

    for arg in &spec.args {
        cmd.arg(arg);
    }

    let mut child = cmd
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .map_err(|e| format!("启动进程失败: {e}"))?;

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
        *guard = Some(child);
    }

    // Read stdout and stderr concurrently
    let app_handle = app.clone();
    let stdout_reader = tokio::spawn(async move {
        let reader = tokio::io::BufReader::new(stdout_handle);
        let mut lines = reader.lines();
        let mut collected = String::new();
        while let Ok(Some(line)) = lines.next_line().await {
            collected.push_str(&line);
            collected.push('\n');
            let payload = LogPayload {
                stream: "stdout".to_string(),
                line: line.clone(),
            };
            let _ = app_handle.emit(LOG_EVENT_NAME, payload);
        }
        collected
    });

    let app_handle2 = app.clone();
    let stderr_reader = tokio::spawn(async move {
        let reader = tokio::io::BufReader::new(stderr_handle);
        let mut lines = reader.lines();
        let mut collected = String::new();
        while let Ok(Some(line)) = lines.next_line().await {
            collected.push_str(&line);
            collected.push('\n');
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
        guard.take()
    };
    let status = if let Some(ref mut child) = child_to_wait {
        child.wait().await.unwrap_or_default()
    } else {
        std::process::ExitStatus::default()
    };
    let code = status.code().unwrap_or(-1);
    let finished_at = iso_now();

    Ok(ProcessOutput {
        code,
        stdout,
        stderr,
        command_line: spec.display,
        started_at,
        finished_at,
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
        guard.take()
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
        .invoke_handler(tauri::generate_handler![
            get_repo_root,
            resolve_app_context,
            resolve_path,
            read_youshengshu_config,
            write_youshengshu_config,
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
        assert_eq!(found.unwrap(), dir);

        std::env::remove_var("YSS_REPO_ROOT");
        let _ = std::fs::remove_dir_all(&dir);
    }
}
