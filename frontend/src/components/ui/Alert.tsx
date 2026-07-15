interface AlertProps {
  variant: "error" | "success" | "info" | "warning";
  message: string;
  onDismiss?: () => void;
}

const variantClasses: Record<string, string> = {
  error: "bg-red-50 text-red-800 border-red-200",
  success: "bg-green-50 text-green-800 border-green-200",
  info: "bg-blue-50 text-blue-800 border-blue-200",
  warning: "bg-amber-50 text-amber-800 border-amber-200",
};

export function Alert({ variant, message, onDismiss }: AlertProps) {
  return (
    <div
      className={`rounded-lg border px-4 py-3 text-sm flex items-center justify-between ${variantClasses[variant]}`}
      role="alert"
    >
      <span>{message}</span>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="ml-3 text-current opacity-50 hover:opacity-100 transition-opacity"
          aria-label="Dismiss"
        >
          &times;
        </button>
      )}
    </div>
  );
}
