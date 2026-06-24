import { motion } from "motion/react";
import { BookAudio } from "lucide-react";

interface AppHeaderProps {
  currentModel: string | null;
  frontendHead: string;
  runtimeHead: string | null;
  runtimeRepoRoot: string | null;
  mismatch: boolean;
}

export function AppHeader({
  currentModel,
  frontendHead,
  runtimeHead,
  mismatch,
}: AppHeaderProps) {
  return (
    <motion.header
      className="flex items-center justify-between border-b border-border px-6 py-3"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
    >
      <div className="flex items-center gap-3">
        <BookAudio className="h-5 w-5 text-primary" />
        <h1 className="text-lg font-semibold tracking-tight">
          有声书翻译工坊
        </h1>
      </div>
      <div className="flex items-center gap-4">
        <div className="flex flex-col text-[11px] text-muted-foreground">
          <span>UI: {frontendHead}</span>
          <span className={mismatch ? "text-red-500 font-semibold" : ""}>
            Repo: {runtimeHead ?? "unknown"}
          </span>
        </div>
        {mismatch && (
          <span className="rounded bg-red-500/10 px-2 py-1 text-xs font-semibold text-red-500">
            UI/Repo 版本不一致
          </span>
        )}
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
          <span>
            {currentModel
              ? `LM Studio: ${currentModel}`
              : "LM Studio: 未连接"}
          </span>
        </div>
      </div>
    </motion.header>
  );
}
