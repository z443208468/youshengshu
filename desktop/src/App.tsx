import { useState, useEffect, useCallback, useRef } from "react";
import { motion } from "motion/react";
import { AppHeader } from "@/components/AppHeader";
import { PathSettingsPanel } from "@/components/PathSettingsPanel";
import { ActionPanel } from "@/components/ActionPanel";
import { StatusCards } from "@/components/StatusCards";
import { ChapterTable } from "@/components/ChapterTable";
import { LogConsole } from "@/components/LogConsole";
import { HealthPanel } from "@/components/HealthPanel";
import { CommandPreview } from "@/components/CommandPreview";
import { Toast, useToast } from "@/components/ui/toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getRepoRoot,
  resolveAppContext,
  resolvePath,
  readConfig,
  writeConfig,
  appendUiLog,
  runPythonCli,
  killPythonProcess,
  listenToLogs,
  createLogLine,
} from "@/lib/tauri";
import { DEFAULT_SETTINGS, LOG_VIEW_MAX_LINES } from "@/lib/config";
import {
  parseDoctorJson,
  parseStatusJson,
  parseSplitJson,
  parseStatusErrorJson,
} from "@/lib/status";
import type {
  UiSettings,
  TaskState,
  StatusPayload,
  LogLine,
  DoctorPayload,
  AppContext,
} from "@/types/app";

export default function App() {
  // Settings
  const [settings, setSettings] = useState<UiSettings>(DEFAULT_SETTINGS);
  const [taskState, setTaskState] = useState<TaskState>("idle");
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [currentModel, setCurrentModel] = useState<string | null>(null);
  const [health, setHealth] = useState<DoctorPayload | null>(null);
  const [lastCommand, setLastCommand] = useState<string | null>(null);
  const [logFilePath, setLogFilePath] = useState<string | null>(null);
  const unlistenRef = useRef<(() => void) | null>(null);
  const commandRunningRef = useRef(false);
  const toast = useToast();

  // ---- Merge config into settings (plain function, no hook deps) ----
  function mergeConfigIntoSettings(
    context: AppContext,
    config: Record<string, unknown>,
  ): UiSettings {
    const paths = (config.paths as Record<string, string>) || {};
    const lmstudio = (config.lmstudio as Record<string, unknown>) || {};

    return {
      repoRoot: context.repoRoot,
      configPath: context.configPath,
      pythonCommand: context.pythonCommand,
      inputFile: paths.input_file || DEFAULT_SETTINGS.inputFile,
      enChaptersDir: paths.en_chapters_dir || DEFAULT_SETTINGS.enChaptersDir,
      cnChaptersDir: paths.cn_chapters_dir || DEFAULT_SETTINGS.cnChaptersDir,
      manifestFile: paths.manifest_file || DEFAULT_SETTINGS.manifestFile,
      lmStudioBaseUrl:
        typeof lmstudio.base_url === "string"
          ? lmstudio.base_url
          : DEFAULT_SETTINGS.lmStudioBaseUrl,
    };
  }

  // ---- appendLog must be defined BEFORE runDoctorCmd ----
  const appendLog = useCallback((stream: LogLine["stream"], text: string) => {
    setLogs((prev) => {
      const next = [...prev, createLogLine(stream, text)];
      if (next.length > LOG_VIEW_MAX_LINES) {
        return next.slice(next.length - LOG_VIEW_MAX_LINES);
      }
      return next;
    });
    void appendUiLog(stream, text).catch(() => {});
  }, []);

  // ---- Run doctor command ----
  const runDoctorCmd = useCallback(
    async (
      repoRoot?: string,
      pythonCommand?: string,
      configPath?: string,
    ) => {
      const root = repoRoot || settings.repoRoot;
      const pyCmd = pythonCommand || settings.pythonCommand;
      const cfgPath = configPath || settings.configPath;

      if (!root.trim()) {
        setHealth({ ok: false, canSplit: false, canTranslate: false, checks: [] });
        return;
      }

      appendLog("system", "运行系统诊断...");
      try {
        const result = await runPythonCli({
          repoRoot: root,
          pythonCommand: pyCmd,
          cliCommand: "doctor",
          configPath: cfgPath,
          jsonOutput: true,
        });

        setLastCommand(result.commandLine);
        if (result.logFilePath) {
          setLogFilePath(result.logFilePath);
        }

        appendLog("system", `doctor exit code: ${result.code}`);
        appendLog("system", `doctor stdout length: ${result.stdout?.length ?? 0}`);
        appendLog("system", `doctor stderr length: ${result.stderr?.length ?? 0}`);

        if (!result.stdout || result.stdout.trim().length === 0) {
          appendLog("stderr", "doctor 没有返回 JSON stdout。");
          if (result.stderr?.trim()) {
            appendLog("stderr", `doctor stderr: ${result.stderr}`);
          }
          setHealth({ ok: false, canSplit: false, canTranslate: false, checks: [] });
          return;
        }

        let payload: DoctorPayload;
        try {
          payload = parseDoctorJson(result.stdout);
        } catch (err) {
          appendLog("stderr", `doctor JSON 解析失败: ${String(err)}`);
          appendLog("stderr", `doctor stdout 原文: ${result.stdout}`);
          if (result.stderr?.trim()) {
            appendLog("stderr", `doctor stderr 原文: ${result.stderr}`);
          }
          setHealth({ ok: false, canSplit: false, canTranslate: false, checks: [] });
          return;
        }

        setHealth(payload);
        appendLog(
          "system",
          `能力状态: 分章节=${payload.canSplit ? "可用" : "不可用"}, 翻译=${payload.canTranslate ? "可用" : "不可用"}`,
        );

        if (payload.ok) {
          appendLog("system", "系统诊断: 正常");
        } else {
          const errors = payload.checks.filter((c) => !c.ok && c.severity === "error");
          const warnings = payload.checks.filter((c) => !c.ok && c.severity === "warning");
          if (errors.length > 0) {
            appendLog("system", `系统诊断: ${errors.length} 个错误`);
          }
          if (warnings.length > 0) {
            appendLog("system", `系统诊断: ${warnings.length} 个警告`);
          }
        }
      } catch (err) {
        appendLog("stderr", `诊断失败: ${err}`);
        setHealth({ ok: false, canSplit: false, canTranslate: false, checks: [] });
      }
    },
    [settings, appendLog],
  );

  // ---- Boot: resolve context + read config + run doctor ----
  useEffect(() => {
    (async () => {
      try {
        appendLog("system", "启动桌面程序...");

        // Step 1: resolve app context (repo root, python command, etc.)
        let context: AppContext;
        try {
          context = await resolveAppContext();
        } catch {
          // Fallback to old getRepoRoot for backward compat
          const root = await getRepoRoot();
          context = {
            repoRoot: root,
            configPath: DEFAULT_SETTINGS.configPath,
            pythonCommand: DEFAULT_SETTINGS.pythonCommand,
            isValidRepoRoot: true,
            detectedFrom: "fallback",
            cliPath: "",
          };
        }

        setSettings((prev) => ({
          ...prev,
          repoRoot: context.repoRoot,
          configPath: context.configPath,
          pythonCommand: context.pythonCommand,
        }));
        appendLog(
          "system",
          `项目根目录: ${context.repoRoot} (来自 ${context.detectedFrom})`,
        );

        // Step 2: read config and merge
        try {
          const config = await readConfig(context.repoRoot, context.configPath);
          const merged = mergeConfigIntoSettings(context, config);
          setSettings(merged);
          appendLog("system", "配置已加载");
        } catch {
          appendLog("system", "未找到配置文件，使用默认配置。");
        }

        // Step 3: run doctor (non-blocking — don't await the boot sequence)
        runDoctorCmd(context.repoRoot, context.pythonCommand, context.configPath)
          .catch(() => {});
      } catch (err) {
        appendLog(
          "stderr",
          `启动初始化失败: ${String(err)}`,
        );
        setHealth({
          ok: false,
          canSplit: false,
          canTranslate: false,
          checks: [],
        });
      }
    })();

    // Step 4: register log listener
    (async () => {
      try {
        const unlisten = await listenToLogs((line) => {
          setLogs((prev) => {
            const next = [...prev, line];
            if (next.length > LOG_VIEW_MAX_LINES) {
              return next.slice(next.length - LOG_VIEW_MAX_LINES);
            }
            return next;
          });
          // Extract model name from translate output
          if (
            line.stream === "stdout" &&
            line.text.includes("Using LM Studio model:")
          ) {
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
    })();

    return () => {
      unlistenRef.current?.();
    };
  }, []);

  // ---- Actions ----
  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  const validateRepoRoot = useCallback(() => {
    if (!settings.repoRoot.trim()) {
      appendLog(
        "stderr",
        "项目根目录为空，请先选择包含 src/youshengshu/cli.py 的仓库根目录。",
      );
      toast.show("请先选择项目根目录", "error");
      return false;
    }
    return true;
  }, [settings.repoRoot, appendLog, toast]);

  const runExclusive = useCallback(
    async <T,>(label: string, fn: () => Promise<T>): Promise<T | null> => {
      if (commandRunningRef.current) {
        appendLog("stderr", `已有任务正在运行，忽略重复操作: ${label}`);
        toast.show("已有任务正在运行", "error");
        return null;
      }

      commandRunningRef.current = true;
      try {
        return await fn();
      } finally {
        commandRunningRef.current = false;
      }
    },
    [appendLog, toast],
  );

  const updateSettings = useCallback((next: UiSettings) => {
    setSettings(next);
    setHealth(null);
  }, []);

  const saveConfig = useCallback(async () => {
    if (!validateRepoRoot()) return;

    appendLog("system", "保存配置...");
    try {
      await writeConfig(settings);
      appendLog("system", "配置已保存");
      toast.show("配置已保存", "success");
      await runDoctorCmd(
        settings.repoRoot,
        settings.pythonCommand,
        settings.configPath,
      );
    } catch (err) {
      appendLog("stderr", `保存配置失败: ${err}`);
      toast.show(`保存配置失败: ${err}`, "error");
    }
  }, [settings, appendLog, toast, validateRepoRoot, runDoctorCmd]);

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
      setLastCommand(result.commandLine);
      if (result.logFilePath) {
        setLogFilePath(result.logFilePath);
      }

      if (result.code !== 0) {
        setStatus(null);

        const payload = parseStatusErrorJson(result.stdout);

        if (payload) {
          appendLog("stderr", `状态读取失败: ${payload.error}`);

          if (payload.config_path) {
            appendLog("stderr", `status config: ${payload.config_path}`);
          }

          if (payload.cwd) {
            appendLog("stderr", `status cwd: ${payload.cwd}`);
          }

          if (payload.manifest_file) {
            appendLog("stderr", `status manifest: ${payload.manifest_file}`);
          }

          if (payload.manifest_file_absolute) {
            appendLog(
              "stderr",
              `status manifest absolute: ${payload.manifest_file_absolute}`,
            );
          }

          toast.show("状态读取失败：manifest 不存在或路径不一致", "error");
        } else {
          if (result.stderr?.trim()) {
            appendLog("stderr", result.stderr);
          } else {
            appendLog("stderr", "状态获取失败：status 命令未返回可解析错误。");
          }
          toast.show("状态获取失败", "error");
        }

        setTaskState("idle");
        return;
      }

      const payload = parseStatusJson(result.stdout);
      setStatus(payload);

      appendLog(
        "system",
        `状态已刷新: ${payload.done}/${payload.total} 已完成，待翻译 ${payload.pending}，失败 ${payload.failed}`,
      );

      if (payload.total > 0) {
        appendLog("system", `章节列表已加载: ${payload.chapters.length} 条`);
      }

      toast.show(`状态已刷新: ${payload.done}/${payload.total}`, "success");
    } catch (err) {
      appendLog("stderr", `刷新状态失败: ${err}`);
      toast.show(`刷新状态失败: ${err}`, "error");
    }
    setTaskState("idle");
  }, [settings, appendLog, toast, validateRepoRoot]);

  const runSplit = useCallback(async () => {
    if (!validateRepoRoot()) return;

    await runExclusive("split", async () => {
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
        setLastCommand(result.commandLine);
        if (result.logFilePath) {
          setLogFilePath(result.logFilePath);
        }

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

        if (payload.cwd) {
          appendLog("system", `split cwd: ${payload.cwd}`);
        }

        appendLog(
          "system",
          `split manifest: ${payload.manifest_file_absolute ?? payload.manifest_file}`,
        );

        if (payload.en_chapters_dir_absolute) {
          appendLog("system", `split en dir: ${payload.en_chapters_dir_absolute}`);
        }

        toast.show(`分章节完成: ${payload.chapters} 章`, "success");

        await refreshStatus();
      } catch (err) {
        appendLog("stderr", `分章节失败: ${err}`);
        toast.show(`分章节失败: ${err}`, "error");
        setTaskState("error");
        return;
      }
      setTaskState("idle");
    });
  }, [settings, clearLogs, appendLog, refreshStatus, toast, validateRepoRoot, runExclusive]);

  const runTranslate = useCallback(async () => {
    if (!validateRepoRoot()) return;

    await runExclusive("translate all", async () => {
      setTaskState("translating");
      appendLog("system", "保存配置...");
      try {
        await writeConfig(settings);
      } catch (err) {
        appendLog("stderr", `保存配置失败: ${err}`);
        setTaskState("error");
        return;
      }

      appendLog("system", "连续翻译待处理章节...");
      try {
        const result = await runPythonCli({
          repoRoot: settings.repoRoot,
          pythonCommand: settings.pythonCommand,
          cliCommand: "translate",
          configPath: settings.configPath,
          jsonOutput: false,
        });
        setLastCommand(result.commandLine);
        if (result.logFilePath) {
          setLogFilePath(result.logFilePath);
        }

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
    });
  }, [settings, appendLog, refreshStatus, currentModel, toast, validateRepoRoot, runExclusive]);

  const runTranslateNext = useCallback(async () => {
    if (!validateRepoRoot()) return;

    await runExclusive("translate next", async () => {
      setTaskState("translating");
      appendLog("system", "保存配置...");
      try {
        await writeConfig(settings);
      } catch (err) {
        appendLog("stderr", `保存配置失败: ${err}`);
        setTaskState("error");
        return;
      }

      appendLog("system", "翻译下一个待处理章节...");
      try {
        const result = await runPythonCli({
          repoRoot: settings.repoRoot,
          pythonCommand: settings.pythonCommand,
          cliCommand: "translate",
          configPath: settings.configPath,
          jsonOutput: false,
          maxChapters: 1,
        });
        setLastCommand(result.commandLine);
        if (result.logFilePath) {
          setLogFilePath(result.logFilePath);
        }

        await refreshStatus();

        if (result.code !== 0) {
          toast.show("翻译下一个待处理章节失败", "error");
          setTaskState("error");
          return;
        }

        toast.show("下一个待处理章节翻译完成", "success");
      } catch (err) {
        appendLog("stderr", `翻译下一个待处理章节失败: ${err}`);
        toast.show(`翻译失败: ${err}`, "error");
        setTaskState("error");
        return;
      }
      setTaskState("idle");
    });
  }, [settings, appendLog, refreshStatus, toast, validateRepoRoot, runExclusive]);

  const runTranslateChapter = useCallback(
    async (chapterIndex: number) => {
      if (!validateRepoRoot()) return;

      await runExclusive(`translate chapter ${chapterIndex}`, async () => {
        setTaskState("translating");
        appendLog("system", "保存配置...");
        try {
          await writeConfig(settings);
        } catch (err) {
          appendLog("stderr", `保存配置失败: ${err}`);
          setTaskState("error");
          return;
        }

        appendLog("system", `翻译指定章节: 第 ${chapterIndex} 章...`);
        try {
          const result = await runPythonCli({
            repoRoot: settings.repoRoot,
            pythonCommand: settings.pythonCommand,
            cliCommand: "translate",
            configPath: settings.configPath,
            jsonOutput: false,
            chapterIndex,
          });

          setLastCommand(result.commandLine);
          if (result.logFilePath) {
            setLogFilePath(result.logFilePath);
          }

          await refreshStatus();

          if (result.code !== 0) {
            toast.show(`第 ${chapterIndex} 章翻译失败，已保留断点`, "error");
            setTaskState("error");
            return;
          }

          toast.show(`第 ${chapterIndex} 章翻译完成`, "success");
          setTaskState("idle");
        } catch (err) {
          appendLog("stderr", `指定章节翻译失败: ${err}`);
          toast.show(`指定章节翻译失败: ${err}`, "error");
          setTaskState("error");
        }
      });
    },
    [settings, appendLog, refreshStatus, toast, validateRepoRoot, runExclusive],
  );

  const stopTask = useCallback(async () => {
    appendLog("system", "正在停止当前任务...");
    try {
      await killPythonProcess();
      appendLog(
        "system",
        "已发送停止信号；如果模型进程仍在清理，请等待日志结束。",
      );
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
      const fullPath = await resolvePath(settings.repoRoot, dir);
      await openPath(fullPath);
    } catch {
      // ignore
    }
  }, [settings.repoRoot]);

  const openEnDir = useCallback(() => {
    openDir(settings.enChaptersDir);
  }, [settings, openDir]);

  const openCnDir = useCallback(() => {
    openDir(settings.cnChaptersDir);
  }, [settings, openDir]);

  // ---- Render ----
  return (
    <div className="flex h-screen flex-col">
      <AppHeader currentModel={currentModel} />

      <div className="flex flex-1 overflow-hidden">
        {/* Left panel: health + settings + actions + command preview */}
        <motion.aside
          className="w-[320px] shrink-0 border-r border-border p-4 flex flex-col gap-4 overflow-y-auto"
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
        >
          <HealthPanel health={health} onRerun={() => runDoctorCmd()} />

          <Card>
            <CardHeader className="p-3 pb-0">
              <CardTitle className="text-sm">路径设置</CardTitle>
            </CardHeader>
            <CardContent className="p-3">
              <PathSettingsPanel
                settings={settings}
                onChange={updateSettings}
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
                canSplit={health?.canSplit === true}
                canTranslate={health?.canTranslate === true}
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

          <CommandPreview lastCommand={lastCommand} repoRoot={settings.repoRoot} />
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
              <ChapterTable
                chapters={status?.chapters ?? []}
                onTranslateChapter={runTranslateChapter}
                disabled={
                  taskState === "translating" ||
                  taskState === "splitting" ||
                  taskState === "refreshing"
                }
              />
            </CardContent>
          </Card>

          <Card className="h-[200px] shrink-0">
            <CardContent className="p-3 h-full">
              <LogConsole logs={logs} onClear={clearLogs} logFilePath={logFilePath} />
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
