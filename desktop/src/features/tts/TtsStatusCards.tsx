import type { TtsStatusPayload } from "../../types/app";

interface TtsStatusCardsProps {
  status: TtsStatusPayload | null;
}

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </section>
  );
}

export function TtsStatusCards({ status }: TtsStatusCardsProps) {
  if (!status) {
    return (
      <section className="rounded-xl border border-border bg-card p-4">
        <p className="text-sm font-semibold">尚未创建 TTS 项目。</p>
        <p className="mt-1 text-sm text-muted-foreground">
          请选择输入来源，然后点击“创建有声书项目”。
        </p>
      </section>
    );
  }

  return (
    <div className="grid grid-cols-4 gap-4">
      <StatCard label="总章节" value={status.total} />
      <StatCard label="已完成" value={status.done} />
      <StatCard label="待处理" value={status.pending} />
      <StatCard label="失败" value={status.failed} />
    </div>
  );
}
