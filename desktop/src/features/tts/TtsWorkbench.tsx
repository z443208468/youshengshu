import { useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { revealItemInDir } from "@tauri-apps/plugin-opener";

import type {
  CosyVoiceRuntimeStatus,
  TtsChapterRow,
  TtsServiceStatus,
  TtsSettings,
  TtsStatusPayload,
  TtsTaskState,
} from "../../types/app";
import {
  bootstrapCosyVoiceRuntime,
  checkCosyVoiceRuntime,
  killTtsProcess,
  resolvePath,
  runTtsCli,
  startCosyVoiceService,
  writeJsonConfig,
} from "../../lib/tauri";

import { TtsActionPanel } from "./TtsActionPanel";
import { TtsChapterTable } from "./TtsChapterTable";
import { TtsProviderPanel } from "./TtsProviderPanel";
import { TtsServiceStatusCard } from "./TtsServiceStatusCard";
import { TtsSourcePanel } from "./TtsSourcePanel";
import { TtsStatusCards } from "./TtsStatusCards";

interface TtsWorkbenchProps {
  runtimeMismatch: unknown;
  repoRoot: string;
  pythonCommand: string;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function TtsWorkbench({
  runtimeMismatch,
  repoRoot,
  pythonCommand,
}: TtsWorkbenchProps) {
  void runtimeMismatch;

  const [ttsSettings, setTtsSettings] = useState<TtsSettings>({
    repoRoot,
    ttsConfigPath: "config/tts_config.json",
    sourceMode: "cn_chapters_dir",
    sourcePath: "data/cn_chapters",
    outputDir: "data/audio_projects/default",
    provider: "cosyvoice_http",
    providerBaseUrl: "http://127.0.0.1:50000",
    voiceMode: "sft",
    spkId: "中文女",
    promptText: "",
    promptAudioPath: "",
    instructText: "用自然、稳定的有声书旁白语气朗读。",
  });

  const [taskState, setTaskState] = useState<TtsTaskState>("idle");
  const [serviceStatus, setServiceStatus] = useState<TtsServiceStatus>("unchecked");
  const [serviceError, setServiceError] = useState<string | null>(null);
  const [cosyVoiceRuntime, setCosyVoiceRuntime] =
    useState<CosyVoiceRuntimeStatus | null>(null);
  void cosyVoiceRuntime;
  const [ttsStatus, setTtsStatus] = useState<TtsStatusPayload | null>(null);
  const [ttsLogs, setTtsLogs] = useState<string[]>([]);

  function appendTtsLog(message: string) {
    const timestamp = new Date().toLocaleTimeString();
    setTtsLogs((current) => [...current, `[${timestamp}] ${message}`]);
  }

  function errorToMessage(error: unknown): string {
    return error instanceof Error ? error.message : String(error);
  }

  const patchTtsSettings = (patch: Partial<TtsSettings>) => {
    setTtsSettings((current) => ({ ...current, ...patch }));
  };

  async function buildTtsConfigPayload(settings: TtsSettings) {
    const actualSourcePath = await resolvePath(settings.repoRoot, settings.sourcePath);
    const actualOutputDir = await resolvePath(settings.repoRoot, settings.outputDir);
    const promptAudioPath = settings.promptAudioPath.trim().length > 0
      ? await resolvePath(settings.repoRoot, settings.promptAudioPath)
      : "";

    return {
      paths: {
        source_mode: settings.sourceMode,
        source_path: actualSourcePath,
        output_dir: actualOutputDir,
        manifest_file: `${actualOutputDir.replace(/\\/g, "/")}/audio_manifest.json`,
      },
      segmentation: {
        target_chars_min: 80,
        target_chars_max: 180,
        hard_chars_max: 240,
        punctuation: "。！？；……\n",
      },
      cosyvoice: {
        base_url: settings.providerBaseUrl,
        mode: settings.voiceMode,
        spk_id: settings.spkId,
        prompt_text: settings.promptText,
        prompt_audio_path: promptAudioPath,
        instruct_text: settings.instructText,
        model_profile: "cosyvoice_300m_sft",
        request_timeout_seconds: 120,
        max_retries: 2,
        retry_sleep_seconds: 2,
        sample_rate: 22050,
      },
      audio: {
        output_format: "wav",
        sample_rate: 22050,
      },
    };
  }

  async function saveTtsConfigOnly() {
    const payload = await buildTtsConfigPayload(ttsSettings);

    await writeJsonConfig(
      ttsSettings.repoRoot,
      ttsSettings.ttsConfigPath,
      payload,
    );
    appendTtsLog(`TTS 配置已保存: ${ttsSettings.ttsConfigPath}`);
  }

  async function handleSaveConfig() {
    setTaskState("saving_config");
    try {
      await saveTtsConfigOnly();
      setTaskState("idle");
    } catch (error) {
      const message = errorToMessage(error);
      appendTtsLog(`保存 TTS 配置失败: ${message}`);
      setTaskState("error");
    }
  }

  async function refreshTtsStatusOnly() {
    const output = await runTtsCli({
      repoRoot: ttsSettings.repoRoot,
      pythonCommand,
      cliCommand: "status",
      configPath: ttsSettings.ttsConfigPath,
      jsonOutput: true,
    });

    const payload = JSON.parse(output.stdout) as TtsStatusPayload;
    setTtsStatus(payload);

    patchTtsSettings({
      sourcePath: payload.source_path.replace(/\\/g, "/"),
      outputDir: payload.output_dir.replace(/\\/g, "/"),
    });

    appendTtsLog(
      `TTS 状态已刷新: total=${payload.total}, done=${payload.done}, pending=${payload.pending}, failed=${payload.failed}`,
    );
  }

  async function handleCreateProject() {
    setTaskState("creating_project");
    try {
      await saveTtsConfigOnly();

      appendTtsLog("开始创建有声书项目。");
      await runTtsCli({
        repoRoot: ttsSettings.repoRoot,
        pythonCommand,
        cliCommand: "create-project",
        configPath: ttsSettings.ttsConfigPath,
        jsonOutput: true,
      });

      appendTtsLog("有声书项目创建完成，开始刷新状态。");
      await refreshTtsStatusOnly();

      setTaskState("idle");
    } catch (error) {
      const message = errorToMessage(error);
      appendTtsLog(`创建有声书项目失败: ${message}`);
      setTaskState("error");
    }
  }

  async function handleRefreshStatus() {
    setTaskState("refreshing");
    try {
      await refreshTtsStatusOnly();
      setTaskState("idle");
    } catch (error) {
      const message = errorToMessage(error);
      appendTtsLog(`刷新 TTS 状态失败: ${message}`);
      setTaskState("error");
    }
  }

  async function handleSynthesizeNext() {
    setTaskState("synthesizing");
    try {
      appendTtsLog("开始生成下一个待处理章节。");
      await runTtsCli({
        repoRoot: ttsSettings.repoRoot,
        pythonCommand,
        cliCommand: "synthesize-next",
        configPath: ttsSettings.ttsConfigPath,
        jsonOutput: true,
      });

      appendTtsLog("下一个待处理章节生成完成，开始刷新状态。");
      await refreshTtsStatusOnly();

      setTaskState("idle");
    } catch (error) {
      const message = errorToMessage(error);
      appendTtsLog(`生成下一个待处理章节失败: ${message}`);
      setTaskState("error");
    }
  }

  async function handleSynthesizeAll() {
    setTaskState("synthesizing");
    try {
      appendTtsLog("开始连续生成待处理章节。");
      await runTtsCli({
        repoRoot: ttsSettings.repoRoot,
        pythonCommand,
        cliCommand: "synthesize-all",
        configPath: ttsSettings.ttsConfigPath,
        jsonOutput: true,
      });

      appendTtsLog("连续生成任务完成，开始刷新状态。");
      await refreshTtsStatusOnly();

      setTaskState("idle");
    } catch (error) {
      const message = errorToMessage(error);
      appendTtsLog(`连续生成待处理章节失败: ${message}`);
      setTaskState("error");
    }
  }

  async function handleSynthesizeChapter(chapterIndex: number) {
    setTaskState("synthesizing");
    try {
      appendTtsLog(`开始生成第 ${chapterIndex} 章。`);
      await runTtsCli({
        repoRoot: ttsSettings.repoRoot,
        pythonCommand,
        cliCommand: "synthesize",
        configPath: ttsSettings.ttsConfigPath,
        jsonOutput: true,
        chapterIndex,
      });

      appendTtsLog(`第 ${chapterIndex} 章生成完成，开始刷新状态。`);
      await refreshTtsStatusOnly();

      setTaskState("idle");
    } catch (error) {
      const message = errorToMessage(error);
      appendTtsLog(`生成第 ${chapterIndex} 章失败: ${message}`);
      setTaskState("error");
    }
  }

  async function handleStop() {
    setTaskState("stopping");
    try {
      appendTtsLog("正在停止 TTS 任务。");
      await killTtsProcess();
      appendTtsLog("TTS 任务已停止。");
      setTaskState("idle");
    } catch (error) {
      const message = errorToMessage(error);
      appendTtsLog(`停止 TTS 任务失败: ${message}`);
      setTaskState("error");
    }
  }

  async function checkCosyVoiceDocs(): Promise<boolean> {
    try {
      const response = await fetch(
        `${ttsSettings.providerBaseUrl.replace(/\/$/, "")}/docs`,
        { method: "GET" },
      );
      return response.ok;
    } catch {
      return false;
    }
  }

  async function ensureCosyVoiceRuntimeAndServiceReady() {
    setServiceStatus("checking_runtime");
    setServiceError(null);
    appendTtsLog("正在检查 CosyVoice 运行环境。");

    let runtime = await checkCosyVoiceRuntime(ttsSettings.repoRoot);
    setCosyVoiceRuntime(runtime);

    if (!runtime.ready) {
      setServiceStatus("bootstrapping_runtime");
      appendTtsLog(`CosyVoice 运行环境缺失: ${runtime.missing.join(", ")}`);
      appendTtsLog("开始自动安装 CosyVoice 运行环境。");

      try {
        const bootstrapOutput = await bootstrapCosyVoiceRuntime(ttsSettings.repoRoot);

        if (bootstrapOutput.code !== 0) {
          throw new Error(
            `CosyVoice runtime bootstrap failed with code ${bootstrapOutput.code}: ${
              bootstrapOutput.stderr || bootstrapOutput.stdout || bootstrapOutput.commandLine
            }`,
          );
        }
      } catch (error) {
        const message = errorToMessage(error);
        setServiceStatus("error");
        setServiceError(message);
        appendTtsLog(`CosyVoice 运行环境自动安装失败: ${message}`);
        return;
      }

      runtime = await checkCosyVoiceRuntime(ttsSettings.repoRoot);
      setCosyVoiceRuntime(runtime);

      if (!runtime.ready) {
        const message = `CosyVoice 运行环境安装后仍不完整: ${runtime.missing.join(", ")}`;
        setServiceStatus("error");
        setServiceError(message);
        appendTtsLog(message);
        return;
      }

      appendTtsLog("CosyVoice 运行环境已准备完成。");
    }

    setServiceStatus("checking");
    appendTtsLog("正在检查 CosyVoice FastAPI 服务。");

    const alreadyConnected = await checkCosyVoiceDocs();

    if (alreadyConnected) {
      setServiceStatus("connected");
      appendTtsLog("CosyVoice FastAPI 服务已连接。");
      return;
    }

    setServiceStatus("starting");
    appendTtsLog("CosyVoice FastAPI 服务未连接，开始自动启动。");

    try {
      await startCosyVoiceService(ttsSettings.repoRoot, pythonCommand);
    } catch (error) {
      const message = errorToMessage(error);
      setServiceStatus("error");
      setServiceError(message);
      appendTtsLog(`CosyVoice FastAPI 服务自动启动失败: ${message}`);
      return;
    }

    for (let attempt = 1; attempt <= 180; attempt += 1) {
      appendTtsLog(`等待 CosyVoice FastAPI 服务启动: ${attempt}/180`);
      await sleep(1000);

      const connected = await checkCosyVoiceDocs();

      if (connected) {
        setServiceStatus("connected");
        setServiceError(null);
        appendTtsLog("CosyVoice FastAPI 服务已自动启动并连接。");
        return;
      }
    }

    const message = "CosyVoice FastAPI 服务启动超时，180 秒内未连通 /docs。";
    setServiceStatus("error");
    setServiceError(message);
    appendTtsLog(message);
  }

  useEffect(() => {
    void ensureCosyVoiceRuntimeAndServiceReady();
  }, []);

  async function handleCheckService() {
    await ensureCosyVoiceRuntimeAndServiceReady();
  }

  async function handlePickSource() {
    const defaultPath = await resolvePath(ttsSettings.repoRoot, ttsSettings.sourcePath);

    const selected = await open({
      directory: ttsSettings.sourceMode === "cn_chapters_dir",
      multiple: false,
      defaultPath,
      filters:
        ttsSettings.sourceMode === "txt_file"
          ? [{ name: "Text", extensions: ["txt"] }]
          : undefined,
    });

    if (typeof selected !== "string") {
      appendTtsLog("未选择 TTS 输入来源。");
      return;
    }

    patchTtsSettings({ sourcePath: selected.replace(/\\/g, "/") });
    appendTtsLog(`TTS 输入来源已选择: ${selected}`);
  }

  async function handlePickOutputDir() {
    const defaultPath = await resolvePath(ttsSettings.repoRoot, ttsSettings.outputDir);

    const selected = await open({
      directory: true,
      multiple: false,
      defaultPath,
    });

    if (typeof selected !== "string") {
      appendTtsLog("未选择 TTS 输出目录。");
      return;
    }

    patchTtsSettings({ outputDir: selected.replace(/\\/g, "/") });
    appendTtsLog(`TTS 输出目录已选择: ${selected}`);
  }

  async function handlePickPromptAudio() {
    const defaultPath =
      ttsSettings.promptAudioPath.trim().length > 0
        ? dirname(await resolvePath(ttsSettings.repoRoot, ttsSettings.promptAudioPath))
        : await resolvePath(ttsSettings.repoRoot, "data");

    const selected = await open({
      directory: false,
      multiple: false,
      defaultPath,
      filters: [{ name: "WAV Audio", extensions: ["wav"] }],
    });

    if (typeof selected !== "string") {
      appendTtsLog("未选择提示音频。");
      return;
    }

    patchTtsSettings({ promptAudioPath: selected.replace(/\\/g, "/") });
    appendTtsLog(`提示音频已选择: ${selected}`);
  }

  function dirname(path: string): string {
    const normalized = path.replace(/\\/g, "/");
    const index = normalized.lastIndexOf("/");
    if (index <= 0) return normalized;
    return normalized.slice(0, index);
  }

  async function handleOpenAudioDir(chapterIndex: number) {
    const row = ttsStatus?.chapters.find(
      (chapter: TtsChapterRow) => chapter.index === chapterIndex,
    );

    if (!row?.chapter_wav_path) {
      appendTtsLog(`第 ${chapterIndex} 章还没有可打开的音频文件。`);
      return;
    }

    const actualPath = row.chapter_wav_path.replace(/\\/g, "/");
    appendTtsLog(`正在打开第 ${chapterIndex} 章音频文件位置: ${actualPath}`);
    await revealItemInDir(actualPath);
  }

  return (
    <div className="flex h-full w-full overflow-hidden">
      <aside className="w-[320px] shrink-0 border-r border-border p-4 flex flex-col gap-4 overflow-y-auto">
        <TtsServiceStatusCard
          providerBaseUrl={ttsSettings.providerBaseUrl}
          voiceMode={ttsSettings.voiceMode}
          status={serviceStatus}
          error={serviceError}
          onCheck={handleCheckService}
        />

        <TtsSourcePanel
          settings={ttsSettings}
          onChange={patchTtsSettings}
          onPickSource={handlePickSource}
          onPickOutputDir={handlePickOutputDir}
        />

        <TtsProviderPanel
          settings={ttsSettings}
          onChange={patchTtsSettings}
          onPickPromptAudio={handlePickPromptAudio}
        />

        <TtsActionPanel
          taskState={taskState}
          sourcePath={ttsSettings.sourcePath}
          hasManifest={Boolean(ttsStatus)}
          serviceStatus={serviceStatus}
          onSaveConfig={handleSaveConfig}
          onCreateProject={handleCreateProject}
          onRefreshStatus={handleRefreshStatus}
          onSynthesizeNext={handleSynthesizeNext}
          onSynthesizeAll={handleSynthesizeAll}
          onStop={handleStop}
        />
      </aside>

      <main className="flex-1 flex flex-col gap-4 overflow-hidden p-4">
        <TtsStatusCards status={ttsStatus} />

        <TtsChapterTable
          rows={ttsStatus?.chapters ?? []}
          running={!["idle", "error"].includes(taskState)}
          onSynthesizeChapter={handleSynthesizeChapter}
          onOpenAudioDir={handleOpenAudioDir}
        />

        <section className="h-[220px] overflow-auto rounded-xl border border-border bg-card p-4">
          <h2 className="mb-3 text-sm font-semibold">TTS 日志</h2>
          {ttsLogs.length === 0 ? (
            <p className="text-xs text-muted-foreground">暂无 TTS 日志。</p>
          ) : (
            <pre className="whitespace-pre-wrap text-xs leading-5">
              {ttsLogs.join("\n")}
            </pre>
          )}
        </section>
      </main>
    </div>
  );
}
