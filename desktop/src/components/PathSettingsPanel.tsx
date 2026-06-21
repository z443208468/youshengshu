import { open, save } from "@tauri-apps/plugin-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import type { UiSettings } from "@/types/app";

interface PathSettingsPanelProps {
  settings: UiSettings;
  onChange: (settings: UiSettings) => void;
}

interface PathField {
  key: keyof UiSettings;
  label: string;
  kind: "file" | "dir" | "save";
  filter?: { name: string; extensions: string[] };
}

const PATH_FIELDS: PathField[] = [
  {
    key: "repoRoot",
    label: "项目根目录",
    kind: "dir",
  },
  {
    key: "inputFile",
    label: "原始 TXT 文件",
    kind: "file",
    filter: { name: "文本文件", extensions: ["txt"] },
  },
  {
    key: "enChaptersDir",
    label: "英文分章输出目录",
    kind: "dir",
  },
  {
    key: "cnChaptersDir",
    label: "中文译文输出目录",
    kind: "dir",
  },
  {
    key: "manifestFile",
    label: "Manifest 进度文件",
    kind: "save",
    filter: { name: "JSON 文件", extensions: ["json"] },
  },
  {
    key: "configPath",
    label: "配置文件路径",
    kind: "save",
    filter: { name: "JSON 文件", extensions: ["json"] },
  },
];

export function PathSettingsPanel({
  settings,
  onChange,
}: PathSettingsPanelProps) {
  const handleBrowse = async (field: PathField) => {
    try {
      let selected: string | null = null;
      if (field.kind === "file") {
        selected = await open({
          multiple: false,
          directory: false,
          filters: field.filter ? [field.filter] : undefined,
        });
      } else if (field.kind === "dir") {
        selected = await open({
          multiple: false,
          directory: true,
        });
      } else if (field.kind === "save") {
        selected = await save({
          filters: field.filter ? [field.filter] : undefined,
        });
      }
      if (selected) {
        onChange({ ...settings, [field.key]: selected });
      }
    } catch {
      // Tauri dialog not available (e.g. in browser dev)
    }
  };

  return (
    <div className="space-y-3">
      {PATH_FIELDS.map((field) => (
        <div key={field.key} className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">
            {field.label}
          </Label>
          <div className="flex gap-2">
            <Input
              value={settings[field.key]}
              onChange={(e) =>
                onChange({ ...settings, [field.key]: e.target.value })
              }
              className="flex-1 h-8 text-xs"
              placeholder={field.label}
            />
            <Button
              variant="outline"
              size="sm"
              className="shrink-0 h-8 text-xs"
              onClick={() => handleBrowse(field)}
            >
              选择{field.kind === "dir" ? "目录" : "文件"}
            </Button>
          </div>
        </div>
      ))}

      <Separator className="my-3" />

      <div className="space-y-1.5">
        <Label className="text-xs text-muted-foreground">Python 命令</Label>
        <Input
          value={settings.pythonCommand}
          onChange={(e) =>
            onChange({ ...settings, pythonCommand: e.target.value })
          }
          className="h-8 text-xs"
          placeholder="python"
        />
      </div>

      <div className="space-y-1.5">
        <Label className="text-xs text-muted-foreground">
          LM Studio API 地址
        </Label>
        <Input
          value={settings.lmStudioBaseUrl}
          onChange={(e) =>
            onChange({ ...settings, lmStudioBaseUrl: e.target.value })
          }
          className="h-8 text-xs"
          placeholder="http://localhost:1234/v1"
        />
      </div>
    </div>
  );
}
