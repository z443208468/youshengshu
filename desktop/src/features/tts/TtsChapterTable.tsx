import type { TtsChapterRow } from "../../types/app";

interface TtsChapterTableProps {
  rows: TtsChapterRow[];
  onSynthesizeChapter: (chapterIndex: number) => void;
  onOpenAudioDir: (chapterIndex: number) => void;
  running: boolean;
}

function statusLabel(status: TtsChapterRow["status"]): string {
  if (status === "pending") return "待处理";
  if (status === "segmented") return "已分段";
  if (status === "in_progress") return "生成中";
  if (status === "done") return "完成";
  return "失败";
}

function progressText(row: TtsChapterRow): string {
  if (row.segment_count === 0) return "未分段";
  return `${row.done_segment_count} / ${row.segment_count}`;
}

function shortError(error: string | null): string {
  if (!error) return "-";
  return error.length > 120 ? `${error.slice(0, 120)}...` : error;
}

export function TtsChapterTable({
  rows,
  onSynthesizeChapter,
  onOpenAudioDir,
  running,
}: TtsChapterTableProps) {
  if (rows.length === 0) {
    return (
      <section className="flex-1 rounded-xl border border-border bg-card p-4">
        <p className="text-sm font-semibold">还没有章节。</p>
        <p className="mt-1 text-sm text-muted-foreground">请先创建 TTS 项目。</p>
      </section>
    );
  }

  return (
    <section className="flex-1 overflow-hidden rounded-xl border border-border bg-card">
      <div className="border-b border-border p-4">
        <h2 className="text-sm font-semibold">TTS 章节表</h2>
      </div>

      <div className="h-full overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-card">
            <tr className="border-b border-border text-left text-xs text-muted-foreground">
              <th className="px-4 py-3">章节</th>
              <th className="px-4 py-3">标题</th>
              <th className="px-4 py-3">状态</th>
              <th className="px-4 py-3">片段进度</th>
              <th className="px-4 py-3">音频文件</th>
              <th className="px-4 py-3">错误</th>
              <th className="px-4 py-3 text-right">操作</th>
            </tr>
          </thead>

          <tbody>
            {rows.map((row) => (
              <tr key={row.index} className="border-b border-border">
                <td className="px-4 py-3">第 {row.index} 章</td>
                <td className="px-4 py-3">{row.title}</td>
                <td className="px-4 py-3">
                  <span className="rounded-full border border-border px-2 py-1 text-xs">
                    {statusLabel(row.status)}
                  </span>
                </td>
                <td className="px-4 py-3">{progressText(row)}</td>
                <td className="px-4 py-3">
                  {row.chapter_wav_path ? row.chapter_wav_path : "-"}
                </td>
                <td className="max-w-[260px] px-4 py-3 text-xs text-muted-foreground">
                  {shortError(row.error)}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      disabled={running}
                      onClick={() => onSynthesizeChapter(row.index)}
                      className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {row.status === "failed" ? `继续第 ${row.index} 章` : `生成第 ${row.index} 章`}
                    </button>
                    <button
                      type="button"
                      disabled={!row.chapter_wav_path}
                      onClick={() => onOpenAudioDir(row.index)}
                      className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      打开目录
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
