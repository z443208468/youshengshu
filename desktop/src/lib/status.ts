import type { CheckResult, DoctorPayload, StatusPayload } from "@/types/app";

function parseJsonObject(stdout: string, label: string): Record<string, unknown> {
  const text = stdout.trim();

  if (!text) {
    throw new Error(`${label} stdout is empty`);
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (err) {
    throw new Error(
      `${label} stdout is not valid JSON: ${String(err)}\nstdout=${text}`,
    );
  }

  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${label} JSON root must be an object`);
  }

  return parsed as Record<string, unknown>;
}

function readBoolean(value: unknown, fallback: boolean): boolean {
  if (typeof value === "boolean") return value;
  return fallback;
}

function readString(value: unknown, fallback = ""): string {
  if (typeof value === "string") return value;
  return fallback;
}

function readOptionalString(value: unknown): string | undefined {
  if (typeof value === "string" && value.length > 0) return value;
  return undefined;
}

function readNumber(value: unknown, fallback: number): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  return fallback;
}

function normalizeCheckResult(value: unknown): CheckResult {
  const obj =
    value && typeof value === "object" && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : {};

  const rawSeverity = obj.severity;
  const severity =
    rawSeverity === "warning" || rawSeverity === "error" || rawSeverity === "info"
      ? rawSeverity
      : "error";

  const detail =
    obj.detail && typeof obj.detail === "object" && !Array.isArray(obj.detail)
      ? (obj.detail as Record<string, unknown>)
      : {};

  return {
    name: readString(obj.name, "unknown"),
    ok: readBoolean(obj.ok, false),
    severity,
    message: readString(obj.message, ""),
    detail,
  };
}

export function parseDoctorJson(stdout: string): DoctorPayload {
  const raw = parseJsonObject(stdout, "doctor");

  const checksRaw = Array.isArray(raw.checks) ? raw.checks : [];

  return {
    ok: readBoolean(raw.ok, false),
    canSplit: readBoolean(raw.canSplit ?? raw.can_split, false),
    canTranslate: readBoolean(raw.canTranslate ?? raw.can_translate, false),
    checks: checksRaw.map(normalizeCheckResult),
  };
}

export function parseStatusJson(stdout: string): StatusPayload {
  const raw = parseJsonObject(stdout, "status");
  return raw as unknown as StatusPayload;
}

export interface SplitPayload {
  source: string;
  source_absolute?: string;
  chapters: number;
  en_chapters_dir: string;
  en_chapters_dir_absolute?: string;
  manifest_file: string;
  manifest_file_absolute?: string;
  cwd?: string;
}

export function parseSplitJson(stdout: string): SplitPayload {
  const raw = parseJsonObject(stdout, "split");

  return {
    source: readString(raw.source),
    source_absolute: readOptionalString(raw.source_absolute),
    // Safe display fallback only; backend still validates real split result.
    chapters: readNumber(raw.chapters, 0),
    en_chapters_dir: readString(raw.en_chapters_dir),
    en_chapters_dir_absolute: readOptionalString(raw.en_chapters_dir_absolute),
    manifest_file: readString(raw.manifest_file),
    manifest_file_absolute: readOptionalString(raw.manifest_file_absolute),
    cwd: readOptionalString(raw.cwd),
  };
}

export interface StatusErrorPayload {
  error: string;
  config_path?: string;
  manifest_file?: string;
  manifest_file_absolute?: string;
  cwd?: string;
}

export function parseStatusErrorJson(stdout: string): StatusErrorPayload | null {
  if (!stdout || stdout.trim().length === 0) {
    return null;
  }

  let raw: Record<string, unknown>;
  try {
    raw = parseJsonObject(stdout, "status-error");
  } catch {
    return null;
  }

  const error = readOptionalString(raw.error);
  if (!error) return null;

  return {
    error,
    config_path: readOptionalString(raw.config_path),
    manifest_file: readOptionalString(raw.manifest_file),
    manifest_file_absolute: readOptionalString(raw.manifest_file_absolute),
    cwd: readOptionalString(raw.cwd),
  };
}
