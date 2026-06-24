import { invoke } from "@tauri-apps/api/core";
import { listen, UnlistenFn } from "@tauri-apps/api/event";
import type {
  UiSettings,
  LogLine,
  ProcessOutput,
  AppContext,
} from "@/types/app";

let logCounter = 0;
function nextLogId(): string {
  return `${Date.now()}-${logCounter++}`;
}

export function createLogLine(
  stream: LogLine["stream"],
  text: string,
): LogLine {
  return { id: nextLogId(), stream, text, createdAt: Date.now() };
}

// ---- Tauri Commands ----

export async function getRepoRoot(): Promise<string> {
  return invoke<string>("get_repo_root");
}

export async function resolveAppContext(): Promise<AppContext> {
  return invoke<AppContext>("resolve_app_context");
}

export async function resolvePath(
  repoRoot: string,
  rawPath: string,
): Promise<string> {
  return invoke<string>("resolve_path", { repoRoot, rawPath });
}

export async function readConfig(
  repoRoot: string,
  configPath: string,
): Promise<Record<string, unknown>> {
  return invoke<Record<string, unknown>>("read_youshengshu_config", {
    repoRoot,
    configPath,
  });
}

export async function appendUiLog(
  stream: LogLine["stream"],
  line: string,
): Promise<void> {
  return invoke<void>("append_ui_log", { stream, line });
}

export async function writeConfig(settings: UiSettings): Promise<void> {
  return invoke<void>("write_youshengshu_config", { paths: settings });
}

export async function runPythonCli(params: {
  repoRoot: string;
  pythonCommand: string;
  cliCommand: string;
  configPath: string;
  jsonOutput: boolean;
  maxChapters?: number;
  chapterIndex?: number;
}): Promise<ProcessOutput> {
  return invoke<ProcessOutput>("run_python_cli", {
    repoRoot: params.repoRoot,
    pythonCommand: params.pythonCommand,
    cliCommand: params.cliCommand,
    configPath: params.configPath,
    jsonOutput: params.jsonOutput,
    maxChapters: params.maxChapters ?? null,
    chapterIndex: params.chapterIndex ?? null,
  });
}

export async function killPythonProcess(): Promise<void> {
  return invoke<void>("kill_python_process");
}

export async function writeJsonConfig(
  repoRoot: string,
  configPath: string,
  payload: Record<string, unknown>,
): Promise<void> {
  return invoke<void>("write_json_config", {
    repoRoot,
    configPath,
    payload,
  });
}

export async function runTtsCli(params: {
  repoRoot: string;
  pythonCommand: string;
  cliCommand: string;
  configPath: string;
  jsonOutput: boolean;
  chapterIndex?: number;
}): Promise<ProcessOutput> {
  return invoke<ProcessOutput>("run_tts_cli", {
    repoRoot: params.repoRoot,
    pythonCommand: params.pythonCommand,
    cliCommand: params.cliCommand,
    configPath: params.configPath,
    jsonOutput: params.jsonOutput,
    chapterIndex: params.chapterIndex ?? null,
  });
}

export async function killTtsProcess(): Promise<void> {
  return invoke<void>("kill_tts_process");
}

export interface CosyVoiceRuntimeStatus {
  repoRoot: string;
  cosyvoiceDir: string;
  fastapiServerPath: string;
  venvPython: string;
  modelDir: string;
  repoExists: boolean;
  gitExists: boolean;
  fastapiServerExists: boolean;
  venvPythonExists: boolean;
  modelDirExists: boolean;
  modelFilesExist: boolean;
  ready: boolean;
  missing: string[];
}

export async function checkCosyVoiceRuntime(
  repoRoot: string,
): Promise<CosyVoiceRuntimeStatus> {
  return invoke<CosyVoiceRuntimeStatus>("check_cosyvoice_runtime", { repoRoot });
}

export async function bootstrapCosyVoiceRuntime(
  repoRoot: string,
): Promise<ProcessOutput> {
  return invoke<ProcessOutput>("bootstrap_cosyvoice_runtime", {
    repoRoot,
  });
}

export async function killCosyVoiceBootstrap(): Promise<void> {
  return invoke<void>("kill_cosyvoice_bootstrap");
}

export async function startCosyVoiceService(
  repoRoot: string,
  pythonCommand: string,
): Promise<void> {
  await invoke("start_cosyvoice_service", { repoRoot, pythonCommand });
}

export async function killCosyVoiceService(): Promise<void> {
  await invoke("kill_cosyvoice_service");
}

// ---- Event listeners ----

export async function listenToLogs(
  callback: (line: LogLine) => void,
): Promise<UnlistenFn> {
  return listen<{ stream: string; line: string }>(
    "youshengshu-log",
    (event) => {
      const line = createLogLine(
        event.payload.stream as LogLine["stream"],
        event.payload.line,
      );
      callback(line);
    },
  );
}
