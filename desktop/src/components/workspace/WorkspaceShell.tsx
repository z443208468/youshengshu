import type { ReactNode } from "react";
import type { WorkspaceModule } from "../../types/app";
import { ModuleNav } from "./ModuleNav";

interface WorkspaceShellProps {
  activeModule: WorkspaceModule;
  onChangeModule: (module: WorkspaceModule) => void;
  runtimeBlocking: boolean;
  children: ReactNode;
}

export function WorkspaceShell({
  activeModule,
  onChangeModule,
  runtimeBlocking,
  children,
}: WorkspaceShellProps) {
  return (
    <div className="flex flex-1 overflow-hidden">
      <aside className="w-[220px] shrink-0 border-r border-border p-4">
        <ModuleNav
          activeModule={activeModule}
          onChangeModule={onChangeModule}
          disabled={runtimeBlocking}
        />
      </aside>

      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
