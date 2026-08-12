"use client";

import Image from "next/image";

import { cn } from "@/lib/utils";

const AI_AVATAR_THUMBNAIL_SRC = "/ai-scenario-thumbnail.png";

interface AiScenarioCardArtProps {
  title: string;
  locked?: boolean;
}

export function AiScenarioCardArt({
  title,
  locked = false,
}: AiScenarioCardArtProps) {
  return (
    <>
      {/* Mobile (<sm): the full bleed panel below has no room on a narrow card, so it's
          sm:block-only — this was leaving mobile with no avatar at all instead of a
          smaller one. A round badge, same visual language as AiCoachAvatar's chat
          avatar, fits inside the card's own p-6 padding without needing the
          sm:pr-[46%] reserved space the desktop panel depends on. Bottom-right corner:
          every card's top row (icon, optional "Voice" tag) and CTA row (left-aligned
          "Start") leave it empty, so the badge never sits under other content — no
          z-index tug-of-war needed against the content div's z-10. */}
      <div
        className={cn(
          "pointer-events-none absolute bottom-4 right-4 h-14 w-14 overflow-hidden rounded-full shadow-md ring-2 ring-background sm:hidden",
          locked && "opacity-70",
        )}
        aria-hidden="true"
      >
        <Image
          src={AI_AVATAR_THUMBNAIL_SRC}
          alt=""
          fill
          sizes="56px"
          className="object-cover object-center saturate-95 dark:opacity-90"
        />
        <span className="sr-only">{`${title} AI coach avatar`}</span>
      </div>

      <div
        className={cn(
          "pointer-events-none absolute bottom-0 right-0 top-0 hidden w-[43%] overflow-hidden sm:block",
          locked && "opacity-70",
        )}
        aria-hidden="true"
      >
        <span className="absolute inset-0 bg-secondary/70 dark:bg-secondary/25" />
        <Image
          src={AI_AVATAR_THUMBNAIL_SRC}
          alt=""
          fill
          sizes="(min-width: 1024px) 300px, 43vw"
          className="object-cover object-center opacity-90 saturate-95 transition-transform duration-500 group-hover:scale-[1.04] dark:opacity-80"
        />
        <span
          className="absolute inset-y-0 -left-10 w-20 bg-surface-elevated"
          style={{ clipPath: "polygon(0 0, 52% 0, 100% 100%, 0 100%)" }}
        />
        <span
          className="absolute inset-y-0 -left-11 w-24 border-l border-border/80"
          style={{ clipPath: "polygon(46% 0, 54% 0, 100% 100%, 92% 100%)" }}
        />
        <span className="absolute inset-0 bg-gradient-to-l from-transparent via-transparent to-surface-elevated/20" />
        <span className="sr-only">{`${title} AI coach avatar`}</span>
      </div>
    </>
  );
}
