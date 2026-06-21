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
