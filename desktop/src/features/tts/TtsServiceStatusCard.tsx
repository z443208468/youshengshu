import type { TtsServiceStatus } from "../../types/app";

interface TtsServiceStatusCardProps {
  providerBaseUrl: string;
  voiceMode: string;
  status: TtsServiceStatus;
  error: string | null;
  onCheck: () => void;
}

function statusText(status: TtsServiceStatus, error: string | null): string {
  if (status === "unchecked") return "尚未检查 CosyVoice 运行环境。";
  if (status === "checking_runtime") return "正在检查 CosyVoice 源码、环境和模型。";
  if (status === "bootstrapping_runtime") return "正在自动安装 CosyVoice 运行环境，请等待。";
  if (status === "checking") return "正在检查 CosyVoice FastAPI 服务。";
  if (status === "starting") return "正在自动启动 CosyVoice FastAPI 服务。";
  if (status === "connected") return "CosyVoice FastAPI 服务已连接。";
  if (status === "disconnected") return "CosyVoice FastAPI 服务未连接，应用正在自动处理。";
  return `CosyVoice 自动处理失败：${error ?? "未知错误"}`;
}

export function TtsServiceStatusCard({
  providerBaseUrl,
  voiceMode,
  status,
  error,
  onCheck,
}: TtsServiceStatusCardProps) {
  const busy =
    status === "checking_runtime" ||
    status === "bootstrapping_runtime" ||
    status === "checking" ||
    status === "starting";

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
        {busy ? "处理中..." : "重新检查 / 自动修复"}
      </button>
    </section>
  );
}
