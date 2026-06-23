import type { UiSettings } from "@/types/app";

export const DEFAULT_SETTINGS: UiSettings = {
  repoRoot: "",
  configPath: "config/default_config.json",
  pythonCommand: "python",
  inputFile: "data/input/ReZero_Watching_Him_Die.txt",
  enChaptersDir: "data/en_chapters",
  cnChaptersDir: "data/cn_chapters",
  manifestFile: "data/manifests/translation_manifest.json",
  lmStudioBaseUrl: "http://localhost:1234/v1",
};

// UI panel keeps the last N lines. Full UI events go to logs/youshengshu-session-*.log;
// each Python CLI task also writes logs/youshengshu-ui-*.log.
export const LOG_VIEW_MAX_LINES = 2000;
