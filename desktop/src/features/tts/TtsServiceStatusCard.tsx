import type { TtsServiceStatus } from "../../types/app";

interface TtsServiceStatusCardProps {
  providerBaseUrl: string;
  voiceMode: string;
  status: TtsServiceStatus;
  error: string | null;
  onCheck: () => void;
}

function statusText(status: TtsServiceStatus, error: string | null): string {
  if (status === "unchecked") return "尚未检查 CosyVoice 服务。";
  if (status === "checking") return "正在检查 CosyVoice 服务...";
  if (status === "starting") return "正在自动启动 CosyVoice 服务，请等待连接完成。";
  if (status === "connected") return "CosyVoice 服务已连接。";
  if (status === "disconnected") return "CosyVoice 服务未连接，应用正在尝试自动启动。";
  return `CosyVoice 服务自动启动失败：${error ?? "未知错误"}`;
}

export function TtsServiceStatusCard({
  providerBaseUrl,
  voiceMode,
  status,
  error,
  onCheck,
}: TtsServiceStatusCardProps) {
  const busy = status === "checking" || status === "starting";

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">TTS 服务状态</h2>
          <p className="mt-1 text-xs text-muted-foreground">Provider: CosyVoice HTTP</p>
        </div>
        <span className="rounded-full border border-border px-2 py-1 text-xs text-muted-foreground">
          {status}
        </span>
      </div>

      <dl className="space-y-2 text-xs text-muted-foreground">
        <div className="flex justify-between gap-3">
          <dt>Base URL</dt>
          <dd className="truncate text-right">{providerBaseUrl}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt>Mode</dt>
          <dd>{voiceMode}</dd>
        </div>
      </dl>

      <p className="mt-3 rounded-lg border border-border bg-background p-3 text-xs leading-5">
        {statusText(status, error)}
      </p>

      <button
        type="button"
        onClick={onCheck}
        disabled={busy}
        aria-busy={busy}
        className="mt-3 w-full rounded-lg border border-border px-3 py-2 text-sm font-medium hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
      >
        {busy ? "处理中..." : "检查服务"}
      </button>
    </section>
  );
}
