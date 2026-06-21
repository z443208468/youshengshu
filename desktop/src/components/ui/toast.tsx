import * as React from "react";

interface ToasterProps {
  // Sonner-style toast via simple state
  message: string | null;
  type?: "success" | "error" | "info";
  onDismiss: () => void;
}

function Toast({ message, type = "info", onDismiss }: ToasterProps) {
  if (!message) return null;

  const bgMap = {
    success: "bg-emerald-700",
    error: "bg-red-700",
    info: "bg-zinc-800",
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 animate-in fade-in slide-in-from-bottom-4">
      <div
        className={`${bgMap[type]} rounded-lg px-4 py-3 shadow-lg text-white text-sm flex items-center gap-3`}
      >
        <span>{message}</span>
        <button
          onClick={onDismiss}
          className="ml-2 hover:opacity-70 text-lg leading-none"
        >
          &times;
        </button>
      </div>
    </div>
  );
}

// Simple toast hook
export function useToast() {
  const [toast, setToast] = React.useState<{
    message: string;
    type: "success" | "error" | "info";
  } | null>(null);

  const show = React.useCallback(
    (message: string, type: "success" | "error" | "info" = "info") => {
      setToast({ message, type });
    },
    [],
  );

  const dismiss = React.useCallback(() => {
    setToast(null);
  }, []);

  return { toast, show, dismiss };
}

export { Toast };
