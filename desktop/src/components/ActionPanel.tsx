import { Button } from "@/components/ui/button";
import type { TaskState } from "@/types/app";
import {
  Save,
  Scissors,
  RefreshCw,
  Play,
  Square,
  FolderOpen,
  StepForward,
} from "lucide-react";

interface ActionPanelProps {
  taskState: TaskState;
  onSaveConfig: () => void;
  onSplit: () => void;
  onRefresh: () => void;
  onTranslate: () => void;
  onTranslateNext: () => void;
  onStop: () => void;
  onOpenEnDir: () => void;
  onOpenCnDir: () => void;
  showStopButton: boolean;
  canSplit?: boolean;
  canTranslate?: boolean;
}

export function ActionPanel({
  taskState,
  onSaveConfig,
  onSplit,
  onRefresh,
  onTranslate,
  onTranslateNext,
  onStop,
  onOpenEnDir,
  onOpenCnDir,
  showStopButton,
  canSplit = true,
  canTranslate = true,
}: ActionPanelProps) {
  const isRunning =
    taskState === "splitting" ||
    taskState === "translating" ||
    taskState === "refreshing";

  return (
    <div className="space-y-2">
      <Button
        variant="outline"
        size="sm"
        className="w-full justify-start text-xs"
        disabled={isRunning}
        onClick={onSaveConfig}
      >
        <Save className="mr-2 h-3.5 w-3.5" />
        保存配置
      </Button>

      <Button
        variant="outline"
        size="sm"
        className="w-full justify-start text-xs"
        disabled={isRunning || !canSplit}
        title={!canSplit ? "输入 TXT 或基础环境未就绪，请保存配置后重新检查" : undefined}
        onClick={onSplit}
      >
        {taskState === "splitting" ? (
          <RefreshCw className="mr-2 h-3.5 w-3.5 animate-spin" />
        ) : (
          <Scissors className="mr-2 h-3.5 w-3.5" />
        )}
        分章节
      </Button>

      <Button
        variant="outline"
        size="sm"
        className="w-full justify-start text-xs"
        disabled={isRunning}
        onClick={onRefresh}
      >
        {taskState === "refreshing" ? (
          <RefreshCw className="mr-2 h-3.5 w-3.5 animate-spin" />
        ) : (
          <RefreshCw className="mr-2 h-3.5 w-3.5" />
        )}
        刷新状态
      </Button>

      <Button
        variant="default"
        size="sm"
        className="w-full justify-start text-xs"
        disabled={isRunning || !canTranslate}
        title={!canTranslate ? "翻译条件未就绪：需要输入 TXT 正常且 LM Studio 已加载模型" : undefined}
        onClick={onTranslate}
      >
        {taskState === "translating" ? (
          <RefreshCw className="mr-2 h-3.5 w-3.5 animate-spin" />
        ) : (
          <Play className="mr-2 h-3.5 w-3.5" />
        )}
        开始翻译
      </Button>

      <Button
        variant="secondary"
        size="sm"
        className="w-full justify-start text-xs"
        disabled={isRunning || !canTranslate}
        title={!canTranslate ? "翻译条件未就绪：需要输入 TXT 正常且 LM Studio 已加载模型" : undefined}
        onClick={onTranslateNext}
      >
        <StepForward className="mr-2 h-3.5 w-3.5" />
        只翻译下一章
      </Button>

      {showStopButton && (
        <Button
          variant="destructive"
          size="sm"
          className="w-full justify-start text-xs"
          disabled={!isRunning}
          onClick={onStop}
        >
          <Square className="mr-2 h-3.5 w-3.5" />
          停止当前任务
        </Button>
      )}

      <Button
        variant="ghost"
        size="sm"
        className="w-full justify-start text-xs"
        onClick={onOpenEnDir}
      >
        <FolderOpen className="mr-2 h-3.5 w-3.5" />
        打开英文分章目录
      </Button>

      <Button
        variant="ghost"
        size="sm"
        className="w-full justify-start text-xs"
        onClick={onOpenCnDir}
      >
        <FolderOpen className="mr-2 h-3.5 w-3.5" />
        打开中文译文目录
      </Button>
    </div>
  );
}
