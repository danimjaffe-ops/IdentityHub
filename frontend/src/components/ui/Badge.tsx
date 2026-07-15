import type { ReactNode } from "react";

interface BadgeProps {
  variant: "success" | "warning" | "neutral";
  children: ReactNode;
}

const variantClasses: Record<string, string> = {
  success: "bg-green-100 text-green-800",
  warning: "bg-yellow-100 text-yellow-800",
  neutral: "bg-gray-100 text-gray-800",
};

export function Badge({ variant, children }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${variantClasses[variant]}`}
    >
      {children}
    </span>
  );
}
