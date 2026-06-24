import type { WorkspaceModule } from "../../types/app";

interface ModuleNavProps {
  activeModule: WorkspaceModule;
  onChangeModule: (module: WorkspaceModule) => void;
  disabled?: boolean;
}

const NAV_ITEMS: Array<{
  id: WorkspaceModule;
  title: string;
  subtitle: string;
}> = [
  {
    id: "home",
    title: "工作台首页",
    subtitle: "选择功能模块",
  },
  {
    id: "translation",
    title: "翻译工坊",
    subtitle: "英文 → 中文章节",
  },
  {
    id: "tts",
    title: "TTS 工坊",
    subtitle: "文本 → 人声音频",
  },
  {
    id: "rvc",
    title: "RVC 工坊",
    subtitle: "音频 → 声线转换",
  },
];

function navItemClass(active: boolean, disabled: boolean): string {
  const base =
    "w-full rounded-xl border px-3 py-3 text-left transition focus:outline-none focus:ring-2 focus:ring-ring";
  const enabledState = active
    ? "border-primary bg-primary/10 text-foreground"
    : "border-border bg-card text-foreground hover:bg-accent hover:text-accent-foreground";
  const disabledState = disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer";

  return `${base} ${enabledState} ${disabledState}`;
}

export function ModuleNav({
  activeModule,
  onChangeModule,
  disabled = false,
}: ModuleNavProps) {
  return (
    <nav className="flex h-full flex-col gap-3">
      {NAV_ITEMS.map((item, index) => {
        const active = activeModule === item.id;

        return (
          <button
            key={item.id}
            type="button"
            className={navItemClass(active, disabled)}
            onClick={() => onChangeModule(item.id)}
            disabled={disabled}
            aria-current={active ? "page" : undefined}
            title={disabled ? "任务运行中，暂不可切换模块" : item.title}
          >
            <span className="block text-sm font-semibold">{item.title}</span>
            <span className="mt-1 block text-xs text-muted-foreground">
              {item.subtitle}
            </span>
            {index === 0 && <span className="mt-3 block h-px bg-border" />}
          </button>
        );
      })}
    </nav>
  );
}
