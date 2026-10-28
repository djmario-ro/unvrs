import type { RoomStatus } from "../api/types";

export interface StatusStyle {
  /** Short tag shown inside compact cells (blueprint units). */
  short: string;
  /** Full label for legends and chips. */
  full: string;
  /** Canonical accent colour — the single source of truth shared by every surface. */
  hex: string;
  /** Lighter accent for dots / glows. */
  dot: string;
}

// The one place room-status colours are defined. Dashboard blueprint and the
// calendar both derive their styles from here so the palette always matches.
export const ROOM_STATUS: Record<RoomStatus, StatusStyle> = {
  available: { short: "FREE", full: "Vacant", hex: "#06b6d4", dot: "#22d3ee" },
  booked: { short: "RES", full: "Booked", hex: "#8b5cf6", dot: "#c4b5fd" },
  checked_in: { short: "IN", full: "Checked-in", hex: "#10b981", dot: "#6ee7b7" },
  checked_out: { short: "OUT", full: "Checked-out", hex: "#f43f5e", dot: "#fda4af" },
};

export const ROOM_STATUS_ORDER: RoomStatus[] = [
  "available",
  "booked",
  "checked_in",
  "checked_out",
];

/** `#rrggbb` + alpha → `rgba(...)`. */
export function withAlpha(hex: string, alpha: number): string {
  const n = hex.replace("#", "");
  const r = parseInt(n.slice(0, 2), 16);
  const g = parseInt(n.slice(2, 4), 16);
  const b = parseInt(n.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
