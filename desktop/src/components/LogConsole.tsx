import { useRef, useEffect } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Copy, Trash2 } from "lucide-react";
import type { LogLine } from "@/types/app";

interface LogConsoleProps {
  logs: LogLine[];
  onClear: () => void;
}

export function LogConsole({ logs, onClear }: LogConsoleProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const handleCopy = () => {
    const text = logs.map((l) => `[${l.stream}] ${l.text}`).join("\n");
    navigator.clipboard.writeText(text).catch(() => {
      // ignore clipboard errors
    });
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-muted-foreground">
          日志 ({logs.length} 行)
        </span>
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={handleCopy}
            title="复制日志"
          >
            <Copy className="h-3 w-3" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={onClear}
            title="清空日志"
          >
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1 rounded-md border bg-black/30 p-2 font-mono text-xs leading-relaxed">
        {logs.length === 0 ? (
          <p className="text-muted-foreground">暂无日志...</p>
        ) : (
          logs.map((line) => {
            let colorClass = "text-gray-300";
            if (line.stream === "stderr") colorClass = "text-red-400";
            else if (line.stream === "system")
              colorClass = "text-yellow-400";

            return (
              <div key={line.id} className={`${colorClass} whitespace-pre-wrap`}>
                {line.text}
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </ScrollArea>
    </div>
  );
}
