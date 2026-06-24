interface RvcWorkbenchProps {
  repoRoot: string;
}

export function RvcWorkbench({ repoRoot }: RvcWorkbenchProps) {
  return (
    <div className="h-full w-full overflow-y-auto p-6">
      <section className="max-w-3xl rounded-xl border border-border bg-card p-6">
        <div className="mb-4">
          <h1 className="text-2xl font-semibold">RVC 工坊</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            音频 → 声线转换。当前状态：预留入口，尚未接入。
          </p>
        </div>

        <div className="space-y-3 rounded-lg border border-border bg-background p-4 text-sm">
          <p>TTS = 文本 → 语音</p>
          <p>RVC = 语音 → 换声</p>
          <p className="text-muted-foreground">
            当前仓库：{repoRoot}
          </p>
        </div>

        <div className="mt-4 space-y-3">
          <label className="text-xs text-muted-foreground">本地 RVC 项目路径</label>
          <input
            disabled
            value=""
            placeholder="例如 D:\\project\\rvc"
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm opacity-60"
          />

          <button
            type="button"
            disabled
            className="rounded-lg border border-border px-4 py-2 text-sm opacity-50"
          >
            检查 RVC 环境
          </button>
        </div>
      </section>
    </div>
  );
}
