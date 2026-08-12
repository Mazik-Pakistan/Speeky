"use client";

import { cn } from "@/lib/utils";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const BIRD_OFFSET_X = 14;
const BIRD_OFFSET_Y = 24;

export function SpeekyBirdCompanion() {
  const pathname = usePathname();
  const [position, setPosition] = useState({ x: 28, y: 32 });
  const targetRef = useRef({ x: 28, y: 32 }); // Used ref (mouse-position) to reduce re-renders.
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    function handlePointerMove(event: PointerEvent) {
      targetRef.current = {
        x: Math.min(92, Math.max(8, (event.clientX / window.innerWidth) * 100)),
        y: Math.min(
          88,
          Math.max(12, (event.clientY / window.innerHeight) * 100),
        ),
      };
    }
    
    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
    };
  }, []);

  useEffect(() => {
    let frame: number = 0;

    function tick() {
      const target = targetRef.current;

      setPosition((current) => ({
        x: current.x + (target.x - current.x) * 0.065,
        y: current.y + (target.y - current.y) * 0.065,
      }));

      frame = requestAnimationFrame(tick);
    }

    tick();
    return () => cancelAnimationFrame(frame);
  }, []);

  if (pathname === "/") return null;

  return (
    <div
      className={cn("pointer-events-none fixed z-[60] hidden h-12 w-12 -translate-x-1/2 -translate-y-1/2 select-none lg:block transition-opacity", loaded ? "opacity-80" : "opacity-0")}
      style={{
        left: `calc(${position.x}% + ${BIRD_OFFSET_X}px)`,
        top: `calc(${position.y}% + ${BIRD_OFFSET_Y}px)`,
      }}
      aria-hidden="true"
    >
      <div className="animate-[speeky-bird-float_2.4s_ease-in-out_infinite] rounded-full bg-surface/70 p-2 shadow-lg shadow-primary/10 backdrop-blur-sm">
        <Image
          src="/logo-icon.png"
          alt=""
          width={32}
          height={32}
          className="object-contain"
          onLoad = {() => setTimeout(() => setLoaded(true), 200)}
        />
      </div>
    </div>
  );
}
