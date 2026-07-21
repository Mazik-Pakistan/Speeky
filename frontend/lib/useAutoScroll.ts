import * as React from "react";

/** Keeps a scrollable chat container pinned to its latest message. Attach the
 * returned ref to the `overflow-y-auto` container; pass a value that changes
 * per new message (e.g. `turns.length`) as `dep`. */
export function useAutoScroll<T>(dep: T) {
  const ref = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [dep]);
  return ref;
}
