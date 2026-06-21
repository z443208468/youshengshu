import { useState, useEffect, useCallback, useRef } from "react";
import { motion } from "motion/react";
import { AppHeader } from "@/components/AppHeader";
import { PathSettingsPanel } from "@/components/PathSettingsPanel";
import { ActionPanel } from "@/components/ActionPanel";
import { StatusCards } from "@/components/StatusCards";
import { ChapterTable } from "@/components/ChapterTable";
import { LogConsole } from "@/components/LogConsole";
import { Toast, useToast } from "@/components/ui/toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getRepoRoot,
  writeConfig,
  runPythonCli,
  killPythonProcess,
  listenToLogs,
  createLogLine,
} from "@/lib/tauri";
import { DEFAULT_SETTINGS } from "@/lib/config";
import { parseStatusJson, parseSplitJson } from "@/lib/status";
import type {
  UiSettings,
  TaskState,
  StatusPayload,
  LogLine,
} from "@/types/app";

export default function App() {
  // Settings
  const [settings, setSettings] = useState<UiSettings>(DEFAULT_SETTINGS);
  const [taskState, setTaskState] = useState<TaskState>("idle");
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [currentModel, setCurrentModel] = useState<string | null>(null);
  const unlistenRef = useRef<(() => void) | null>(null);
  const toast = useToast();

  // ---- Init ----
  useEffect(() => {
    (async () => {
      try {
        const root = await getRepoRoot();
        setSettings((prev) => ({ ...prev, repoRoot: root }));
      } catch {
        // Not running inside Tauri
      }

      try {
        const unlisten = await listenToLogs((line) => {
          setLogs((prev) => {
            const next = [...prev, line];
            // Keep last 2000 lines
            if (next.length > 2000) {
              return next.slice(next.length - 2000);
            }
            return next;
          });
          // Extract model name from translate output
          if (line.stream === "stdout" && line.text.includes("Using LM Studio model:")) {
            const match = line.text.match(/Using LM Studio model:\s*(.+)/);
            if (match) {
              setCurrentModel(match[1].trim());
            }
          }
        });
        unlistenRef.current = unlisten;
      } catch {
        // Not running inside Tauri
      }

      return () => {
        unlistenRef.current?.();
      };
    })();
  }, []);

  // ---- Actions ----
  const appendLog = useCallback((stream: LogLine["stream"], text: string) => {
    setLogs((prev) => {
      const next = [...prev, createLogLine(stream, text)];
      if (next.length > 2000) {
        return next.slice(next.length - 2000);
      }
      return next;
    });
  }, []);

  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  const validateRepoRoot = useCallback(() => {
    if (!settings.repoRoot.trim()) {
      appendLog("stderr", "项目根目录为空，请先选择包含 src/youshengshu/cli.py 的仓库根目录。");
      toast.show("请先选择项目根目录", "error");
      return false;
    }
    return true;
  }, [settings.repoRoot, appendLog, toast]);

  const saveConfig = useCallback(async () => {
    if (!validateRepoRoot()) return;

    appendLog("system", "保存配置...");
    try {
      await writeConfig(settings);
      appendLog("system", "配置已保存");
      toast.show("配置已保存", "success");
    } catch (err) {
      appendLog("stderr", `保存配置失败: ${err}`);
      toast.show(`保存配置失败: ${err}`, "error");
    }
  }, [settings, appendLog, toast, validateRepoRoot]);

  const refreshStatus = useCallback(async () => {
    if (!validateRepoRoot()) return;

    setTaskState("refreshing");
    appendLog("system", "刷新状态...");
    try {
      const result = await runPythonCli({
        repoRoot: settings.repoRoot,
        pythonCommand: settings.pythonCommand,
        cliCommand: "status",
        configPath: settings.configPath,
        jsonOutput: true,
      });

      if (result.code !== 0) {
        // If manifest doesn't exist, show empty state
        try {
          const payload = JSON.parse(result.stdout);
          if (payload.error) {
            setStatus(null);
            appendLog("system", "尚未分章节，请先点击分章节。");
            toast.show("请先分章节", "info");
          }
        } catch {
          setStatus(null);
          appendLog("stderr", result.stderr || "状态获取失败");
          toast.show("状态获取失败", "error");
        }
        setTaskState("idle");
        return;
      }

      const payload = parseStatusJson(result.stdout);
      setStatus(payload);
      appendLog(
        "system",
        `状态已刷新: ${payload.done}/${payload.total} 已完成`,
      );
      toast.show(`状态已刷新: ${payload.done}/${payload.total}`, "success");
    } catch (err) {
      appendLog("stderr", `刷新状态失败: ${err}`);
      toast.show(`刷新状态失败: ${err}`, "error");
    }
    setTaskState("idle");
  }, [settings, appendLog, toast, validateRepoRoot]);

  const runSplit = useCallback(async () => {
    if (!validateRepoRoot()) return;

    setTaskState("splitting");
    clearLogs();
    appendLog("system", "保存配置...");
    try {
      await writeConfig(settings);
    } catch (err) {
      appendLog("stderr", `保存配置失败: ${err}`);
      setTaskState("error");
      return;
    }

    appendLog("system", "开始分章节...");
    try {
      const result = await runPythonCli({
        repoRoot: settings.repoRoot,
        pythonCommand: settings.pythonCommand,
        cliCommand: "split",
        configPath: settings.configPath,
        jsonOutput: true,
      });

      if (result.code !== 0) {
        appendLog("stderr", result.stderr || "分章节失败");
        toast.show("分章节失败", "error");
        setTaskState("error");
        return;
      }

      const payload = parseSplitJson(result.stdout);
      appendLog(
        "system",
        `分章节完成: ${payload.chapters} 章 -> ${payload.en_chapters_dir}`,
      );
      toast.show(`分章节完成: ${payload.chapters} 章`, "success");

      await refreshStatus();
    } catch (err) {
      appendLog("stderr", `分章节失败: ${err}`);
      toast.show(`分章节失败: ${err}`, "error");
      setTaskState("error");
      return;
    }
    setTaskState("idle");
  }, [settings, clearLogs, appendLog, refreshStatus, toast, validateRepoRoot]);

  const runTranslate = useCallback(async () => {
    if (!validateRepoRoot()) return;

    setTaskState("translating");
    appendLog("system", "保存配置...");
    try {
      await writeConfig(settings);
    } catch (err) {
      appendLog("stderr", `保存配置失败: ${err}`);
      setTaskState("error");
      return;
    }

    appendLog("system", "开始翻译...");
    try {
      const result = await runPythonCli({
        repoRoot: settings.repoRoot,
        pythonCommand: settings.pythonCommand,
        cliCommand: "translate",
        configPath: settings.configPath,
        jsonOutput: false,
      });

      // Extract model from stdout if not already captured
      if (!currentModel) {
        const modelMatch = result.stdout.match(/Using LM Studio model:\s*(.+)/);
        if (modelMatch) {
          setCurrentModel(modelMatch[1].trim());
        }
      }

      await refreshStatus();

      if (result.code !== 0) {
        toast.show("翻译过程中出现错误", "error");
        setTaskState("error");
        return;
      }

      toast.show("翻译完成!", "success");
    } catch (err) {
      appendLog("stderr", `翻译失败: ${err}`);
      toast.show(`翻译失败: ${err}`, "error");
      setTaskState("error");
      return;
    }
    setTaskState("idle");
  }, [settings, appendLog, refreshStatus, currentModel, toast, validateRepoRoot]);

  const runTranslateNext = useCallback(async () => {
    if (!validateRepoRoot()) return;

    setTaskState("translating");
    appendLog("system", "保存配置...");
    try {
      await writeConfig(settings);
    } catch (err) {
      appendLog("stderr", `保存配置失败: ${err}`);
      setTaskState("error");
      return;
    }

    appendLog("system", "翻译下一章...");
    try {
      const result = await runPythonCli({
        repoRoot: settings.repoRoot,
        pythonCommand: settings.pythonCommand,
        cliCommand: "translate",
        configPath: settings.configPath,
        jsonOutput: false,
        maxChapters: 1,
      });

      await refreshStatus();

      if (result.code !== 0) {
        toast.show("翻译下一章失败", "error");
        setTaskState("error");
        return;
      }

      toast.show("下一章翻译完成!", "success");
    } catch (err) {
      appendLog("stderr", `翻译下一章失败: ${err}`);
      toast.show(`翻译失败: ${err}`, "error");
      setTaskState("error");
      return;
    }
    setTaskState("idle");
  }, [settings, appendLog, refreshStatus, toast, validateRepoRoot]);

  const stopTask = useCallback(async () => {
    appendLog("system", "正在停止当前任务...");
    try {
      await killPythonProcess();
      appendLog("system", "已发送停止信号；如果模型进程仍在清理，请等待日志结束。");
      toast.show("已发送停止信号", "info");
    } catch (err) {
      appendLog("stderr", `停止任务失败: ${err}`);
      toast.show("停止任务失败", "error");
    }
    setTaskState("idle");
  }, [appendLog, toast]);

  const openDir = useCallback(async (dir: string) => {
    try {
      const { openPath } = await import("@tauri-apps/plugin-opener");
      await openPath(dir);
    } catch {
      // ignore
    }
  }, []);

  const openEnDir = useCallback(() => {
    const fullPath = settings.repoRoot
      ? `${settings.repoRoot}/${settings.enChaptersDir}`
      : settings.enChaptersDir;
    openDir(fullPath);
  }, [settings, openDir]);

  const openCnDir = useCallback(() => {
    const fullPath = settings.repoRoot
      ? `${settings.repoRoot}/${settings.cnChaptersDir}`
      : settings.cnChaptersDir;
    openDir(fullPath);
  }, [settings, openDir]);

  // ---- Render ----
  return (
    <div className="flex h-screen flex-col">
      <AppHeader currentModel={currentModel} />

      <div className="flex flex-1 overflow-hidden">
        {/* Left panel: settings + actions */}
        <motion.aside
          className="w-[320px] shrink-0 border-r border-border p-4 flex flex-col gap-4 overflow-y-auto"
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
        >
          <Card>
            <CardHeader className="p-3 pb-0">
              <CardTitle className="text-sm">路径设置</CardTitle>
            </CardHeader>
            <CardContent className="p-3">
              <PathSettingsPanel
                settings={settings}
                onChange={setSettings}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="p-3 pb-0">
              <CardTitle className="text-sm">操作</CardTitle>
            </CardHeader>
            <CardContent className="p-3">
              <ActionPanel
                taskState={taskState}
                onSaveConfig={saveConfig}
                onSplit={runSplit}
                onRefresh={refreshStatus}
                onTranslate={runTranslate}
                onTranslateNext={runTranslateNext}
                onStop={stopTask}
                onOpenEnDir={openEnDir}
                onOpenCnDir={openCnDir}
                showStopButton={true}
              />
            </CardContent>
          </Card>
        </motion.aside>

        {/* Right panel: status + chapters + logs */}
        <motion.main
          className="flex-1 flex flex-col p-4 gap-4 overflow-hidden"
          initial={{ opacity: 0, x: 8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
        >
          <StatusCards status={status} currentModel={currentModel} />

          <Card className="flex-1 flex flex-col min-h-0">
            <CardHeader className="p-3 pb-0">
              <CardTitle className="text-sm">章节列表</CardTitle>
            </CardHeader>
            <CardContent className="p-3 flex-1 overflow-auto">
              <ChapterTable chapters={status?.chapters ?? []} />
            </CardContent>
          </Card>

          <Card className="h-[180px] shrink-0">
            <CardContent className="p-3 h-full">
              <LogConsole logs={logs} onClear={clearLogs} />
            </CardContent>
          </Card>
        </motion.main>
      </div>

      <Toast
        message={toast.toast?.message ?? null}
        type={toast.toast?.type}
        onDismiss={toast.dismiss}
      />
    </div>
  );
}
