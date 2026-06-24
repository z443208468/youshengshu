import type { FeatureModule } from "../../types/app";
import { MODULE_CARDS } from "./moduleSpec";

interface ModuleHomeProps {
  onSelectModule: (module: FeatureModule) => void;
}

function ModuleEntryCard({
  title,
  subtitle,
  statusLabel,
  description,
  primaryAction,
  onClick,
}: {
  title: string;
  subtitle: string;
  statusLabel: string;
  description: string;
  primaryAction: string;
  onClick: () => void;
}) {
  return (
    <section className="flex min-h-[220px] flex-col justify-between rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">{title}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          </div>
          <span className="shrink-0 rounded-full border border-border px-2 py-1 text-xs text-muted-foreground">
            {statusLabel}
          </span>
        </div>

        <p className="text-sm leading-6 text-muted-foreground">{description}</p>
      </div>

      <button
        type="button"
        onClick={onClick}
        className="mt-6 rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground"
      >
        {primaryAction}
      </button>
    </section>
  );
}

export function ModuleHome({ onSelectModule }: ModuleHomeProps) {
  return (
    <div className="h-full w-full overflow-y-auto p-6">
      <section className="mb-6">
        <h1 className="text-2xl font-semibold">有声书工作台</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          选择一个模块开始：翻译、TTS 生成或 RVC 声线转换。
        </p>
      </section>

      <div className="grid grid-cols-3 gap-4">
        {MODULE_CARDS.map((card) => (
          <ModuleEntryCard
            key={card.id}
            title={card.title}
            subtitle={card.subtitle}
            statusLabel={card.statusLabel}
            description={card.description}
            primaryAction={card.primaryAction}
            onClick={() => onSelectModule(card.id)}
          />
        ))}
      </div>
    </div>
  );
}
