import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type { ChapterRow } from "@/types/app";

interface ChapterTableProps {
  chapters: ChapterRow[];
}

const STATUS_MAP: Record<
  string,
  { label: string; variant: "secondary" | "default" | "destructive" | "success" }
> = {
  pending: { label: "待翻译", variant: "secondary" },
  in_progress: { label: "翻译中", variant: "default" },
  done: { label: "已完成", variant: "success" },
  failed: { label: "失败", variant: "destructive" },
};

export function ChapterTable({ chapters }: ChapterTableProps) {
  if (chapters.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-sm text-muted-foreground">
        尚未生成章节。请选择原始 TXT 后点击"分章节"。
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">章节</TableHead>
            <TableHead>标题</TableHead>
            <TableHead className="w-20">状态</TableHead>
            <TableHead className="w-24">英文文件</TableHead>
            <TableHead className="w-24">中文文件</TableHead>
            <TableHead className="w-14 text-right">Chunk</TableHead>
            <TableHead className="hidden md:table-cell">模型</TableHead>
            <TableHead className="hidden lg:table-cell">错误</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {chapters.map((ch) => {
            const info = STATUS_MAP[ch.translation_status] ?? STATUS_MAP.pending;
            return (
              <TableRow key={ch.index}>
                <TableCell className="font-mono text-xs">
                  {ch.index}
                </TableCell>
                <TableCell
                  className="max-w-[140px] truncate text-xs"
                  title={ch.title}
                >
                  {ch.title || "-"}
                </TableCell>
                <TableCell>
                  <Badge variant={info.variant} className="text-[10px]">
                    {info.label}
                  </Badge>
                </TableCell>
                <TableCell
                  className="max-w-[100px] truncate text-xs"
                  title={ch.en_path}
                >
                  {ch.en_path.split("/").pop() || ch.en_path}
                </TableCell>
                <TableCell
                  className="max-w-[100px] truncate text-xs"
                  title={ch.cn_path}
                >
                  {ch.cn_path.split("/").pop() || ch.cn_path}
                </TableCell>
                <TableCell className="text-right text-xs">
                  {ch.chunk_count ?? "-"}
                </TableCell>
                <TableCell className="hidden md:table-cell max-w-[100px] truncate text-xs">
                  {ch.translation_model || "-"}
                </TableCell>
                <TableCell className="hidden lg:table-cell max-w-[120px] truncate text-xs text-red-400">
                  {ch.error || "-"}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
