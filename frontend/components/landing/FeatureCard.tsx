import type { FeatureItem } from "@/lib/types";

interface FeatureCardProps {
  feature: FeatureItem;
}

/**
 * Single reusable card for a product feature. Used across Core Features
 * and can be reused anywhere else a feature needs to be presented.
 */
export function FeatureCard({ feature }: FeatureCardProps) {
  const { icon: Icon, title, description } = feature;

  return (
    <div className="group flex flex-col gap-4 rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md">
      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-secondary text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </div>
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      <p className="text-sm leading-relaxed text-muted-foreground">
        {description}
      </p>
    </div>
  );
}
