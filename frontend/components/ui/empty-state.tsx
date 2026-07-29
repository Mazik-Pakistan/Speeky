import * as React from "react";
import Image from "next/image";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  title: string;
  description: string;
  imageSrc?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  title,
  description,
  imageSrc,
  icon,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-border bg-surface/50 px-6 py-12 text-center",
        className
      )}
    >
      {imageSrc ? (
        <Image 
          src={imageSrc} 
          alt="" 
          width={120} 
          height={120} 
          className="mb-2 opacity-80" 
        />
      ) : icon ? (
        <div className="mb-2 flex h-16 w-16 items-center justify-center rounded-full bg-secondary text-primary">
          {icon}
        </div>
      ) : null}
      
      <div className="flex max-w-sm flex-col gap-1">
        <h3 className="font-serif text-lg font-semibold text-foreground">
          {title}
        </h3>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}