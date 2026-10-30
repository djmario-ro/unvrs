import type { QueryClient } from "@tanstack/react-query";

/**
 * Everything that renders bookings: the bookings list, the dashboard floor
 * plan (room status derives from bookings) and per-room views.
 * Call after any mutation that creates, edits or deletes a booking.
 */
export function invalidateBookingViews(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: ["assignments"] });
  qc.invalidateQueries({ queryKey: ["dashboard"] });
  qc.invalidateQueries({ queryKey: ["room"] });
}

/** Rooms changed (fields, images, deletion): room lists, room views and the floor plan. */
export function invalidateRoomViews(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: ["rooms"] });
  qc.invalidateQueries({ queryKey: ["room"] });
  qc.invalidateQueries({ queryKey: ["dashboard"] });
}

/** A guest changed or was deleted (which cascades to their bookings). */
export function invalidateGuestViews(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: ["guests"] });
  invalidateBookingViews(qc);
}
