import type { TtsServiceStatus, TtsTaskState } from "../../types/app";

interface TtsActionPanelProps {
  taskState: TtsTaskState;
  sourcePath: string;
  hasManifest: boolean;
  serviceStatus: TtsServiceStatus;
  onSaveConfig: () => void;
  onCreateProject: () => void;
  onRefreshStatus: () => void;
  onSynthesizeNext: () => void;
  onSynthesizeAll: () => void;
  onStop: () => void;
}

function isRunning(taskState: TtsTaskState): boolean {
  return !["idle", "error"].includes(taskState);
}

function buttonClass(): string {
  return "w-full rounded-lg border border-border px-3 py-2 text-sm font-medium hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50";
}

export function TtsActionPanel({
  taskState,
  sourcePath,
  hasManifest,
  serviceStatus,
  onSaveConfig,
  onCreateProject,
  onRefreshStatus,
  onSynthesizeNext,
  onSynthesizeAll,
  onStop,
}: TtsActionPanelProps) {
  const running = isRunning(taskState);
  const sourceMissing = sourcePath.trim().length === 0;
  const serviceReady = serviceStatus === "connected";

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h2 className="text-sm font-semibold">操作</h2>

      <div className="mt-3 space-y-4">
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">项目</p>
          <button
            type="button"
            onClick={onSaveConfig}
            disabled={running}
            className={buttonClass()}
          >
            {taskState === "saving_config" ? "保存中..." : "保存 TTS 配置"}
          </button>

          <button
            type="button"
            onClick={onCreateProject}
            disabled={running || sourceMissing}
            className={buttonClass()}
          >
            {taskState === "creating_project" ? "创建中..." : "创建有声书项目"}
          </button>

          <button
            type="button"
            onClick={onRefreshStatus}
            disabled={running}
            className={buttonClass()}
          >
            {taskState === "refreshing" ? "刷新中..." : "刷新 TTS 状态"}
          </button>
        </div>

        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">生成</p>
          <button
            type="button"
            onClick={onSynthesizeNext}
            disabled={running || !hasManifest || !serviceReady}
            className={buttonClass()}
          >
            {taskState === "synthesizing" ? "生成中..." : "生成下一个待处理章节"}
          </button>

          <button
            type="button"
            onClick={onSynthesizeAll}
            disabled={running || !hasManifest || !serviceReady}
            className={buttonClass()}
          >
            {taskState === "synthesizing" ? "生成中..." : "连续生成待处理章节"}
          </button>
        </div>

        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">控制</p>
          <button
            type="button"
            onClick={onStop}
            disabled={!running}
            className={buttonClass()}
          >
            {taskState === "stopping" ? "停止中..." : "停止 TTS"}
          </button>
        </div>
      </div>
    </section>
  );
}
