"use client";

import * as React from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export interface CheckboxProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "className" | "type"> {
  label: React.ReactNode;
  error?: string;
}

/**
 * Custom checkbox — no shadcn/Radix. Used for consent-style fields
 * (e.g. "I agree to the Terms & Conditions") where `label` can contain
 * an inline link.
 */
export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ label, error, id, ...props }, ref) => {
    const generatedId = React.useId();
    const inputId = id ?? generatedId;

    return (
      <div className="flex flex-col gap-1.5">
        <label
          htmlFor={inputId}
          className="flex items-start gap-2.5 text-sm text-muted-foreground"
        >
          <span className="relative mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center">
            <input
              id={inputId}
              ref={ref}
              type="checkbox"
              aria-invalid={Boolean(error)}
              aria-describedby={error ? `${inputId}-error` : undefined}
              className={cn(
                "peer absolute inset-0 h-5 w-5 cursor-pointer appearance-none rounded-md border border-input bg-surface transition-colors checked:border-primary checked:bg-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
                error && "border-danger",
              )}
              {...props}
            />
            <Check
              className="pointer-events-none h-3.5 w-3.5 text-primary-foreground opacity-0 peer-checked:opacity-100"
              aria-hidden="true"
            />
          </span>
          <span>{label}</span>
        </label>
        {error ? (
          <p id={`${inputId}-error`} className="text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
    );
  },
);

Checkbox.displayName = "Checkbox";
