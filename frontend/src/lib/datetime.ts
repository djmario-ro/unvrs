/**
 * Convert a `<input type="datetime-local">` value (naive local wall-clock)
 * to a UTC ISO-8601 string the backend can store unambiguously, or null.
 */
export function toIsoOrNull(local: string): string | null {
  if (!local) return null;
  const d = new Date(local); // datetime-local is parsed as local time
  return isNaN(d.getTime()) ? null : d.toISOString();
}
