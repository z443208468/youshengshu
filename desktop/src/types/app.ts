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
  gitHead: string;
  gitShortHead: string;
  gitBranch: string;
}

export interface RuntimeMismatch {
  frontendHead: string;
  runtimeHead: string;
  frontendRepoRoot: string;
  runtimeRepoRoot: string;
}

export interface CheckResult {
  name: string;
  ok: boolean;
  severity: "info" | "warning" | "error";
  message: string;
  detail: Record<string, unknown>;
}

export interface DoctorPayloadRaw {
  ok?: unknown;
  can_split?: unknown;
  can_translate?: unknown;
  canSplit?: unknown;
  canTranslate?: unknown;
  checks?: unknown;
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
  source_paragraph_count: number | null;
  translated_paragraph_count: number | null;
  translated_batch_count: number | null;
  partial_path: string | null;
  resume_state_path: string | null;
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
  logFilePath: string;
}

export type FeatureModule = "translation" | "tts" | "rvc";
export type WorkspaceModule = "home" | FeatureModule;

export interface ModuleCardInfo {
  id: FeatureModule;
  title: string;
  subtitle: string;
  statusLabel: string;
  description: string;
  primaryAction: string;
}

export type TtsTaskState =
  | "idle"
  | "saving_config"
  | "checking_service"
  | "creating_project"
  | "refreshing"
  | "synthesizing"
  | "stopping"
  | "error";

export type TtsServiceStatus =
  | "unchecked"
  | "checking"
  | "starting"
  | "connected"
  | "disconnected"
  | "error";

export type TtsChapterStatus =
  | "pending"
  | "segmented"
  | "in_progress"
  | "done"
  | "failed";

export interface TtsSettings {
  repoRoot: string;
  ttsConfigPath: string;
  sourceMode: "txt_file" | "cn_chapters_dir";
  sourcePath: string;
  outputDir: string;
  provider: "cosyvoice_http";
  providerBaseUrl: string;
  voiceMode: "sft" | "zero_shot" | "cross_lingual" | "instruct";
  spkId: string;
  promptText: string;
  promptAudioPath: string;
  instructText: string;
}

export interface TtsChapterRow {
  index: number;
  title: string;
  source_path: string;
  status: TtsChapterStatus;
  segment_count: number;
  done_segment_count: number;
  failed_segment_count: number;
  chapter_wav_path: string | null;
  chapter_mp3_path: string | null;
  error: string | null;
}

export interface TtsStatusPayload {
  project_id: string;
  source_mode: "txt_file" | "cn_chapters_dir";
  source_path: string;
  output_dir: string;
  total: number;
  done: number;
  pending: number;
  failed: number;
  in_progress: number;
  chapters: TtsChapterRow[];
}
