import type { StatusPayload } from "@/types/app";

export function parseStatusJson(stdout: string): StatusPayload {
  return JSON.parse(stdout) as StatusPayload;
}

export function parseSplitJson(stdout: string): {
  source: string;
  chapters: number;
  en_chapters_dir: string;
  manifest_file: string;
} {
  return JSON.parse(stdout);
}
