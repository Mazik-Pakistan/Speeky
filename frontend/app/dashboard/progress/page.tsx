import { TrendingUp } from "lucide-react";

export default function ProgressPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-border p-12 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-full bg-secondary text-primary">
        <TrendingUp className="h-6 w-6" aria-hidden="true" />
      </span>
      <div className="flex flex-col gap-1">
        <h1 className="font-serif text-2xl font-semibold text-foreground">
          Progress
        </h1>
        <p className="max-w-sm text-sm text-muted-foreground">
          Detailed progress analytics are coming soon.
        </p>
      </div>
    </div>
  );
}
