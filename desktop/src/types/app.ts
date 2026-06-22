export type TaskState =
  | "idle"
  | "splitting"
  | "translating"
  | "refreshing"
  | "error";

export type ChapterStatus = "pending" | "in_progress" | "done" | "failed";

export interface UiSettings {
  repoRoot: string;
  configPath: string;
  pythonCommand: string;
  inputFile: string;
  enChaptersDir: string;
  cnChaptersDir: string;
  manifestFile: string;
  lmStudioBaseUrl: string;
}

export interface AppContext {
  repoRoot: string;
  configPath: string;
  pythonCommand: string;
  isValidRepoRoot: boolean;
  detectedFrom: string;
  cliPath: string;
}

export interface CheckResult {
  name: string;
  ok: boolean;
  severity: "info" | "warning" | "error";
  message: string;
  detail: Record<string, unknown>;
}

export interface DoctorPayload {
  ok: boolean;
  canSplit: boolean;
  canTranslate: boolean;
  checks: CheckResult[];
}

export interface ChapterRow {
  index: number;
  title: string;
  en_path: string;
  cn_path: string;
  translation_status: ChapterStatus;
  translated_at: string | null;
  translation_model: string | null;
  chunk_count: number | null;
  error: string | null;
}

export interface StatusPayload {
  total: number;
  done: number;
  pending: number;
  failed: number;
  in_progress: number;
  next_chapter: number | null;
  failed_list: Array<{
    index: number;
    en_path: string;
    error: string;
  }>;
  chapters: ChapterRow[];
}

export interface LogLine {
  id: string;
  stream: "stdout" | "stderr" | "system";
  text: string;
  createdAt: number;
}

export interface ProcessOutput {
  code: number;
  stdout: string;
  stderr: string;
  commandLine: string;
  startedAt: string;
  finishedAt: string;
}
