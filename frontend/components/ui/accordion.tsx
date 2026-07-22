"use client";

import * as React from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface AccordionItemData {
  id: string;
  trigger: React.ReactNode;
  content: React.ReactNode;
}

interface AccordionProps {
  items: AccordionItemData[];
  className?: string;
}

/**
 * Custom single-open accordion. No shadcn/ui or Radix dependency —
 * plain state + CSS grid trick for the height transition.
 */
export function Accordion({ items, className }: AccordionProps) {
  const [openId, setOpenId] = React.useState<string | null>(null);

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {items.map((item) => {
        const isOpen = openId === item.id;
        const contentId = `${item.id}-content`;
        const triggerId = `${item.id}-trigger`;

        return (
          <div
            key={item.id}
            className="rounded-2xl border border-border bg-surface-elevated shadow-sm"
          >
            <h3>
              <button
                id={triggerId}
                type="button"
                className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left text-sm font-medium text-foreground"
                aria-expanded={isOpen}
                aria-controls={contentId}
                onClick={() => setOpenId(isOpen ? null : item.id)}
              >
                {item.trigger}
                <ChevronDown
                  className={cn(
                    "h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200",
                    isOpen && "rotate-180",
                  )}
                  aria-hidden="true"
                />
              </button>
            </h3>
            <div
              id={contentId}
              role="region"
              aria-labelledby={triggerId}
              className={cn(
                "grid transition-all duration-200 ease-out",
                isOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
              )}
            >
              <div className="overflow-hidden px-5">
                <p className="pb-4 text-sm text-muted-foreground">
                  {item.content}
                </p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
