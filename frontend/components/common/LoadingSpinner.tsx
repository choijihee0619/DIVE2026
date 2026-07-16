import { Loader2 } from "lucide-react";

interface LoadingSpinnerProps {
  size?: number;
  label?: string;
}

export function LoadingSpinner({ size = 20, label }: LoadingSpinnerProps) {
  return (
    <div role="status" className="flex items-center gap-2 text-sm text-neutral-600">
      <Loader2 size={size} className="animate-spin text-accent-600" aria-hidden="true" />
      {label ? <span>{label}</span> : <span className="sr-only">로딩 중</span>}
    </div>
  );
}
