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
  configPath: string,
): Promise<Record<string, unknown>> {
  return invoke<Record<string, unknown>>("read_youshengshu_config", {
    configPath,
  });
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
}): Promise<ProcessOutput> {
  return invoke<ProcessOutput>("run_python_cli", {
    repoRoot: params.repoRoot,
    pythonCommand: params.pythonCommand,
    cliCommand: params.cliCommand,
    configPath: params.configPath,
    jsonOutput: params.jsonOutput,
    maxChapters: params.maxChapters ?? null,
  });
}

export async function killPythonProcess(): Promise<void> {
  return invoke<void>("kill_python_process");
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
