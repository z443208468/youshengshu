import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { motion } from "motion/react";
import type { StatusPayload } from "@/types/app";

interface StatusCardsProps {
  status: StatusPayload | null;
  currentModel: string | null;
}

export function StatusCards({ status, currentModel }: StatusCardsProps) {
  if (!status) {
    return (
      <Card>
        <CardContent className="p-4">
          <p className="text-sm text-muted-foreground">
            尚未加载状态。请先点击分章节，或点击刷新状态；若已分章节仍为空，请查看日志中的 manifest 路径。
          </p>
        </CardContent>
      </Card>
    );
  }

  const progressValue =
    status.total > 0
      ? Math.round((status.done / status.total) * 100)
      : 0;

  const cards = [
    { label: "总章节", value: status.total, color: "text-foreground" },
    { label: "已完成", value: status.done, color: "text-emerald-400" },
    { label: "待翻译", value: status.pending, color: "text-muted-foreground" },
    { label: "失败", value: status.failed, color: "text-red-400" },
    { label: "进行中", value: status.in_progress, color: "text-blue-400" },
    {
      label: "下一章",
      value: status.next_chapter ?? "-",
      color: "text-foreground",
    },
  ];

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        {cards.map((card) => (
          <motion.div
            key={card.label}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
          >
            <Card>
              <CardContent className="p-3 text-center">
                <p className="text-xs text-muted-foreground">{card.label}</p>
                <p className={`text-lg font-bold ${card.color}`}>
                  {card.value}
                </p>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      <div className="space-y-1">
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>翻译进度</span>
          <span>{progressValue}%</span>
        </div>
        <Progress value={progressValue} />
      </div>

      {currentModel && (
        <p className="text-xs text-muted-foreground">
          模型: {currentModel}
        </p>
      )}
    </div>
  );
}
