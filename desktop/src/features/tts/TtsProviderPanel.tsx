import type { TtsSettings } from "../../types/app";

interface TtsProviderPanelProps {
  settings: TtsSettings;
  onChange: (patch: Partial<TtsSettings>) => void;
  onPickPromptAudio: () => void;
}

function modeDescription(mode: TtsSettings["voiceMode"]): string {
  if (mode === "sft") return "sft：使用 CosyVoice 内置说话人 ID。";
  if (mode === "zero_shot") return "zero_shot：使用提示音频和提示文本克隆音色。";
  if (mode === "cross_lingual") return "cross_lingual：使用提示音频进行跨语言音色迁移。";
  return "instruct：使用说话人 ID + 指令文本控制风格。";
}

export function TtsProviderPanel({
  settings,
  onChange,
  onPickPromptAudio,
}: TtsProviderPanelProps) {
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h2 className="text-sm font-semibold">声音参数</h2>

      <div className="mt-3 space-y-3">
        <div>
          <label className="text-xs text-muted-foreground">Base URL</label>
          <input
            value={settings.providerBaseUrl}
            onChange={(event) => onChange({ providerBaseUrl: event.target.value })}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="text-xs text-muted-foreground">Mode</label>
          <select
            value={settings.voiceMode}
            onChange={(event) =>
              onChange({
                voiceMode: event.target.value as TtsSettings["voiceMode"],
              })
            }
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          >
            <option value="sft">sft</option>
            <option value="zero_shot">zero_shot</option>
            <option value="cross_lingual">cross_lingual</option>
            <option value="instruct">instruct</option>
          </select>
        </div>

        <p className="rounded-lg border border-border bg-background p-3 text-xs leading-5 text-muted-foreground">
          {modeDescription(settings.voiceMode)}
        </p>

        {(settings.voiceMode === "sft" || settings.voiceMode === "instruct") && (
          <div>
            <label className="text-xs text-muted-foreground">spk_id</label>
            <input
              value={settings.spkId}
              onChange={(event) => onChange({ spkId: event.target.value })}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
            />
          </div>
        )}

        {settings.voiceMode === "zero_shot" && (
          <div>
            <label className="text-xs text-muted-foreground">prompt_text</label>
            <textarea
              value={settings.promptText}
              onChange={(event) => onChange({ promptText: event.target.value })}
              className="mt-1 min-h-[72px] w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
            />
          </div>
        )}

        {(settings.voiceMode === "zero_shot" || settings.voiceMode === "cross_lingual") && (
          <div>
            <label className="text-xs text-muted-foreground">prompt_audio_path</label>
            <input
              value={settings.promptAudioPath}
              onChange={(event) => onChange({ promptAudioPath: event.target.value })}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={onPickPromptAudio}
              className="mt-2 w-full rounded-lg border border-border px-3 py-2 text-sm hover:bg-accent"
            >
              选择提示音频
            </button>
          </div>
        )}

        {settings.voiceMode === "instruct" && (
          <div>
            <label className="text-xs text-muted-foreground">instruct_text</label>
            <textarea
              value={settings.instructText}
              onChange={(event) => onChange({ instructText: event.target.value })}
              className="mt-1 min-h-[72px] w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
            />
          </div>
        )}
      </div>
    </section>
  );
}
