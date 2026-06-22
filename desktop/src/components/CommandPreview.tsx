import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface CommandPreviewProps {
  lastCommand: string | null;
  repoRoot: string;
}

export function CommandPreview({ lastCommand, repoRoot }: CommandPreviewProps) {
  if (!lastCommand) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="p-3 pb-0">
        <CardTitle className="text-sm">最近命令</CardTitle>
      </CardHeader>
      <CardContent className="p-3">
        <div className="space-y-1 text-xs font-mono text-muted-foreground">
          <div>
            <span className="text-yellow-400">工作目录:</span> {repoRoot}
          </div>
          <div>
            <span className="text-yellow-400">实际命令:</span> {lastCommand}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
