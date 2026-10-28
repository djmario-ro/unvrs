import { useEffect, useState } from "react";

import type { ViewMode } from "../components/ViewToggle";

// localStorage throws in private mode and when site data is blocked, and this
// is only a display preference — never let it break the page.
function read(key: string): ViewMode | null {
  try {
    const stored = localStorage.getItem(key);
    return stored === "cards" || stored === "list" ? stored : null;
  } catch {
    return null;
  }
}

function write(key: string, value: ViewMode) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // preference simply won't persist
  }
}

/** View preference (cards/list) persisted in localStorage per page key. */
export function useViewMode(key: string, initial: ViewMode = "cards") {
  const storageKey = `view:${key}`;
  const [view, setView] = useState<ViewMode>(() => read(storageKey) ?? initial);
  useEffect(() => {
    write(storageKey, view);
  }, [storageKey, view]);
  return [view, setView] as const;
}
