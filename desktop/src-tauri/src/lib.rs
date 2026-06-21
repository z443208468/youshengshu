use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use tauri::Emitter;
use tokio::io::AsyncBufReadExt;
use tokio::process::{Child, Command};

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
struct ProcessOutput {
    code: i32,
    stdout: String,
    stderr: String,
}

#[derive(Debug, Serialize, Clone)]
struct LogPayload {
    stream: String,
    line: String,
}

/// Holds an optional reference to a running child process so we can kill it.
struct ActiveProcess(Mutex<Option<Child>>);

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

/// Detect repo root: use CARGO_MANIFEST_DIR at dev time, or fall back to
/// the current working directory.
#[tauri::command]
fn get_repo_root() -> String {
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()))
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_default());

    // Walk up looking for src/youshengshu as a heuristic
    let mut candidate = exe_dir.clone();
    for _ in 0..5 {
        if candidate.join("src").join("youshengshu").exists() {
            return candidate.to_string_lossy().to_string();
        }
        if !candidate.pop() {
            break;
        }
    }
    std::env::current_dir()
        .unwrap_or_default()
        .to_string_lossy()
        .to_string()
}

/// Read the config JSON file and return it as a generic JSON value.
/// If the file doesn't exist, return a default shape.
#[tauri::command]
fn read_youshengshu_config(config_path: String) -> Result<serde_json::Value, String> {
    let path = std::path::Path::new(&config_path);
    if path.exists() {
        let contents =
            std::fs::read_to_string(path).map_err(|e| format!("读取配置失败: {e}"))?;
        serde_json::from_str(&contents).map_err(|e| format!("配置格式错误: {e}"))
    } else {
        // Return a default config shape
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

/// Write the UI settings into the config JSON file, preserving the existing
/// schema and keeping all non-path/non-lmstudio fields.
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

    // Try to load existing config to preserve non-overridden fields
    let mut config: serde_json::Value = if config_path.exists() {
        let contents =
            std::fs::read_to_string(config_path).map_err(|e| format!("读取配置失败: {e}"))?;
        serde_json::from_str(&contents).unwrap_or_default()
    } else {
        serde_json::Value::Null
    };

    // Patch the paths section
    let paths_obj = serde_json::json!({
        "input_file": paths.input_file,
        "en_chapters_dir": paths.en_chapters_dir,
        "cn_chapters_dir": paths.cn_chapters_dir,
        "manifest_file": paths.manifest_file,
    });

    // If config is null or not an object, start from default
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

    // Overwrite paths
    if let Some(obj) = config.as_object_mut() {
        obj.insert("paths".to_string(), paths_obj);
        // Overwrite lmstudio base_url
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

    // Ensure parent dir exists
    if let Some(parent) = config_path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("创建目录失败: {e}"))?;
    }

    let json_string =
        serde_json::to_string_pretty(&config).map_err(|e| format!("序列化配置失败: {e}"))?;
    std::fs::write(config_path, json_string).map_err(|e| format!("写入配置失败: {e}"))?;

    Ok(())
}

/// Run a Python CLI command, streaming stdout/stderr to the frontend via events.
/// Valid cli_commands: "split", "status", "translate", "all"
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
    let allowed = ["split", "status", "translate", "all"];
    if !allowed.contains(&cli_command.as_str()) {
        return Err(format!("不允许的命令: {}", cli_command));
    }

    if repo_root.trim().is_empty() {
        return Err("项目根目录 repoRoot 为空，请先在 UI 中选择仓库根目录".to_string());
    }

    let repo_root_path = std::path::PathBuf::from(&repo_root);
    let cli_path = repo_root_path.join("src").join("youshengshu").join("cli.py");
    if !cli_path.exists() {
        return Err(format!(
            "项目根目录无效，未找到 Python CLI: {}。请选择包含 src/youshengshu/cli.py 的仓库根目录。",
            cli_path.display()
        ));
    }

    if config_path.trim().is_empty() {
        return Err("配置文件路径为空，请设置 config/default_config.json 或选择配置文件路径".to_string());
    }

    let src_dir = repo_root_path.join("src");
    let mut cmd = Command::new(&python_command);
    cmd.current_dir(&repo_root_path)
        .env("PYTHONPATH", &src_dir)
        .arg("-m")
        .arg("youshengshu.cli")
        .arg(&cli_command)
        .arg("--config")
        .arg(&config_path);

    if json_output {
        cmd.arg("--json");
    }

    if cli_command == "translate" {
        if let Some(mc) = max_chapters {
            if mc > 0 {
                cmd.arg("--max-chapters");
                cmd.arg(mc.to_string());
            }
        }
    }

    // Spawn process with piped stdout/stderr
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
            // Emit event for real-time log display
            let payload = LogPayload {
                stream: "stdout".to_string(),
                line: line.clone(),
            };
            let _ = app_handle.emit("youshengshu-log", payload);
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
            let _ = app_handle2.emit("youshengshu-log", payload);
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

    Ok(ProcessOutput { code, stdout, stderr })
}

/// Kill the currently running Python process if any.
/// If no process is running, return success (no-op).
#[tauri::command]
async fn kill_python_process(
    state: tauri::State<'_, ActiveProcess>,
) -> Result<(), String> {
    // Take the child out of the mutex so we can kill without holding the lock
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
            read_youshengshu_config,
            write_youshengshu_config,
            run_python_cli,
            kill_python_process,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
