import type { TtsSettings } from "../../types/app";

interface TtsSourcePanelProps {
  settings: TtsSettings;
  onChange: (patch: Partial<TtsSettings>) => void;
  onPickSource: () => void;
  onPickOutputDir: () => void;
}

export function TtsSourcePanel({
  settings,
  onChange,
  onPickSource,
  onPickOutputDir,
}: TtsSourcePanelProps) {
  const sourceEmpty = settings.sourcePath.trim().length === 0;

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h2 className="text-sm font-semibold">输入来源</h2>

      <div className="mt-3 space-y-3">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            checked={settings.sourceMode === "cn_chapters_dir"}
            onChange={() => onChange({ sourceMode: "cn_chapters_dir", sourcePath: "" })}
          />
          中文章节目录 cn_chapters
        </label>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            checked={settings.sourceMode === "txt_file"}
            onChange={() => onChange({ sourceMode: "txt_file", sourcePath: "" })}
          />
          单 TXT 文件
        </label>

        <div>
          <label className="text-xs text-muted-foreground">来源路径</label>
          <input
            value={settings.sourcePath}
            onChange={(event) => onChange({ sourcePath: event.target.value })}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
          <button
            type="button"
            onClick={onPickSource}
            className="mt-2 w-full rounded-lg border border-border px-3 py-2 text-sm hover:bg-accent"
          >
            {settings.sourceMode === "cn_chapters_dir" ? "选择中文章节目录" : "选择 TXT 文件"}
          </button>
        </div>

        <div>
          <label className="text-xs text-muted-foreground">输出目录</label>
          <input
            value={settings.outputDir}
            onChange={(event) => onChange({ outputDir: event.target.value })}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
          <button
            type="button"
            onClick={onPickOutputDir}
            className="mt-2 w-full rounded-lg border border-border px-3 py-2 text-sm hover:bg-accent"
          >
            选择输出目录
          </button>
        </div>

        {sourceEmpty && (
          <p className="rounded-lg border border-border bg-background p-3 text-xs leading-5 text-muted-foreground">
            还没有选择输入来源。请选择一个中文章节目录或单个 TXT 文件，然后点击“创建有声书项目”。
          </p>
        )}
      </div>
    </section>
  );
}
