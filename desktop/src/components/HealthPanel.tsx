import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, CheckCircle, XCircle, RefreshCw, Copy } from "lucide-react";
import type { DoctorPayload } from "@/types/app";

interface HealthPanelProps {
  health: DoctorPayload | null;
  onRerun: () => void;
}

export function HealthPanel({ health, onRerun }: HealthPanelProps) {
  const handleCopy = () => {
    if (!health) return;
    const text = health.checks
      .map((c) => `[${c.severity.toUpperCase()}] ${c.name}: ${c.ok ? "PASS" : "FAIL"} — ${c.message}`)
      .join("\n");
    navigator.clipboard.writeText(text).catch(() => {});
  };

  if (!health) {
    return (
      <Card>
        <CardHeader className="p-3 pb-0">
          <CardTitle className="text-sm">系统健康检查</CardTitle>
        </CardHeader>
        <CardContent className="p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">正在检查系统状态...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="p-3 pb-0 flex flex-row items-center justify-between">
        <CardTitle className="text-sm">系统健康检查</CardTitle>
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={handleCopy}
            title="复制诊断结果"
          >
            <Copy className="h-3 w-3" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={onRerun}
            title="重新检查"
          >
            <RefreshCw className="h-3 w-3" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-3 space-y-1">
        <div className="flex items-center gap-2 mb-2">
          {health.ok ? (
            <>
              <CheckCircle className="h-4 w-4 text-emerald-400" />
              <span className="text-xs font-medium text-emerald-400">系统正常</span>
            </>
          ) : (
            <>
              <XCircle className="h-4 w-4 text-red-400" />
              <span className="text-xs font-medium text-red-400">系统异常</span>
            </>
          )}
          <span className="text-xs text-muted-foreground ml-auto">
            分章节: {health.canSplit ? "可用" : "不可用"} | 翻译:{" "}
            {health.canTranslate ? "可用" : "不可用"}
          </span>
        </div>

        {health.checks.map((check) => {
          let icon = <CheckCircle className="h-3 w-3 text-emerald-400" />;
          let badgeVariant: "default" | "secondary" | "destructive" | "outline" = "outline";
          let badgeText = "正常";

          if (!check.ok) {
            if (check.severity === "error") {
              icon = <XCircle className="h-3 w-3 text-red-400" />;
              badgeVariant = "destructive";
              badgeText = "错误";
            } else if (check.severity === "warning") {
              icon = <AlertTriangle className="h-3 w-3 text-yellow-400" />;
              badgeVariant = "secondary";
              badgeText = "警告";
            }
          }

          return (
            <div key={check.name} className="flex items-center gap-2 text-xs">
              {icon}
              <span className="flex-1 truncate text-muted-foreground">
                {check.name}
              </span>
              <Badge variant={badgeVariant} className="text-[10px] px-1 py-0">
                {badgeText}
              </Badge>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
