import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  addDays,
  addWeeks,
  addMonths,
  startOfDay,
  startOfWeek,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  differenceInCalendarDays,
  format,
  isWeekend,
  isSameDay,
} from "date-fns";
import { ChevronLeft, ChevronRight, BedDouble, Trash2 } from "lucide-react";
import { clsx } from "clsx";
import toast from "react-hot-toast";

import { getAssignments, updateAssignment, deleteAssignment } from "../api/assignments";
import { getRooms } from "../api/rooms";
import type { Assignment, RoomStatus } from "../api/types";
import { toIsoOrNull } from "../lib/datetime";
import { ROOM_STATUS, ROOM_STATUS_ORDER } from "../lib/roomStatus";
import Modal from "../components/Modal";
import Spinner from "../components/Spinner";
import ConfirmDialog from "../components/ConfirmDialog";
import ErrorState from "../components/ErrorState";
import PinReveal from "../components/PinReveal";
import { invalidateBookingViews } from "../lib/queries";

type View = "day" | "week" | "month";

const ROOM_LABEL = 150;
const ROW_H = 44;
const EXPIRED_HEX = "#94a3b8"; // no-show / lapsed reservation

const guestName = (b: Assignment) =>
  b.guest ? `${b.guest.firstname} ${b.guest.lastname}` : `Guest #${b.guest_id}`;
const dayOf = (iso: string) => startOfDay(new Date(iso));
const toLocalInput = (iso: string) => format(new Date(iso), "yyyy-MM-dd'T'HH:mm");

// A booking's live status, mirroring the dashboard's event-driven derivation.
const bookingStatus = (b: Assignment, now: Date): RoomStatus | "expired" => {
  const ended = b.check_out ? new Date(b.check_out) < now : false;
  if (b.checked_in_at) return ended ? "checked_out" : "checked_in";
  return ended ? "expired" : "booked";
};
const bookingColor = (b: Assignment, now: Date): string => {
  const s = bookingStatus(b, now);
  return s === "expired" ? EXPIRED_HEX : ROOM_STATUS[s].hex;
};

export default function CalendarPage() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [view, setView] = useState<View>("week");
  const [anchor, setAnchor] = useState(() => startOfDay(new Date()));

  const { data: rooms = [], isLoading: roomsLoading, isError: roomsError, error: roomsErr, refetch: refetchRooms } = useQuery({
    queryKey: ["rooms"],
    queryFn: getRooms,
  });
  const { data: bookings = [], isLoading: bookingsLoading, isError: bookingsError, error: bookingsErr, refetch: refetchBookings } = useQuery({
    queryKey: ["assignments"],
    queryFn: getAssignments,
  });

  const today = startOfDay(new Date());
  const now = new Date();
  const days = useMemo(
    () =>
      view === "day"
        ? [startOfDay(anchor)]
        : view === "week"
        ? eachDayOfInterval({
            start: startOfWeek(anchor, { weekStartsOn: 1 }),
            end: addDays(startOfWeek(anchor, { weekStartsOn: 1 }), 6),
          })
        : eachDayOfInterval({ start: startOfMonth(anchor), end: endOfMonth(anchor) }),
    [view, anchor]
  );

  const col = view === "week" ? 120 : 44; // px per day column
  const trackWidth = days.length * col;

  const dated = bookings.filter((b) => b.check_in && b.check_out);
  const datedByRoom = new Map<number, Assignment[]>();
  for (const b of dated) {
    const list = datedByRoom.get(b.room_id);
    if (list) list.push(b);
    else datedByRoom.set(b.room_id, [b]);
  }
  const undated = bookings.length - dated.length;
  const total = rooms.length;

  const occupantOf = (roomId: number, day: Date): Assignment | null =>
    (datedByRoom.get(roomId) ?? []).find(
      (b) => day >= dayOf(b.check_in as string) && day < dayOf(b.check_out as string)
    ) ?? null;

  // ---- drag-to-select a date range in a room row ----
  const [sel, setSel] = useState<{ roomId: number; a: number; b: number } | null>(null);
  const dragging = useRef(false);
  const finalize = useRef<(s: { roomId: number; a: number; b: number }) => void>();
  finalize.current = (s) => {
    const start = Math.min(s.a, s.b);
    const end = Math.max(s.a, s.b);
    newBooking(s.roomId, days[start], addDays(days[end], 1));
  };
  useEffect(() => {
    const onUp = () => {
      if (!dragging.current) return;
      dragging.current = false;
      setSel((cur) => {
        if (cur) finalize.current?.(cur);
        return null;
      });
    };
    window.addEventListener("mouseup", onUp);
    return () => window.removeEventListener("mouseup", onUp);
  }, []);

  const newBooking = (roomId: number, ci: Date, co: Date) => {
    const p = new URLSearchParams({
      room_id: String(roomId),
      check_in: format(ci, "yyyy-MM-dd'T'14:00"),
      check_out: format(co, "yyyy-MM-dd'T'11:00"),
    });
    nav(`/app/booking?${p.toString()}`);
  };

  // ---- edit modal ----
  const [editTarget, setEditTarget] = useState<Assignment | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [editForm, setEditForm] = useState({ room_id: "", check_in: "", check_out: "" });
  const openEdit = (b: Assignment) => {
    setEditForm({
      room_id: String(b.room_id),
      check_in: b.check_in ? toLocalInput(b.check_in) : "",
      check_out: b.check_out ? toLocalInput(b.check_out) : "",
    });
    setEditTarget(b);
  };
  const editMutation = useMutation({
    mutationFn: () =>
      updateAssignment(editTarget!.id, {
        room_id: Number(editForm.room_id),
        check_in: toIsoOrNull(editForm.check_in),
        check_out: toIsoOrNull(editForm.check_out),
      }),
    onSuccess: () => {
      invalidateBookingViews(qc);
      toast.success("Booking updated");
      setEditTarget(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const deleteMutation = useMutation({
    mutationFn: () => deleteAssignment(editTarget!.id),
    onSuccess: () => {
      invalidateBookingViews(qc);
      toast.success("Booking removed");
      setEditTarget(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // ---- drag to move / resize a booking bar (day-column offsets vs days[0]) ----
  const ciOff = (b: Assignment) => differenceInCalendarDays(dayOf(b.check_in as string), days[0]);
  const coOff = (b: Assignment) => differenceInCalendarDays(dayOf(b.check_out as string), days[0]);

  type Drag = {
    b: Assignment;
    roomId: number;
    mode: "move" | "l" | "r";
    startX: number;
    delta: number;
  };
  const [drag, setDrag] = useState<Drag | null>(null);
  const dragRef = useRef<Drag | null>(null);
  dragRef.current = drag;

  // Preview [start, end) day offsets for a drag, keeping a minimum 1-night span.
  const preview = (d: Drag, delta: number) => {
    const s0 = ciOff(d.b);
    const e0 = coOff(d.b);
    if (d.mode === "move") return { s: s0 + delta, e: e0 + delta };
    if (d.mode === "l") return { s: Math.min(s0 + delta, e0 - 1), e: e0 };
    return { s: s0, e: Math.max(e0 + delta, s0 + 1) };
  };
  const overlaps = (roomId: number, s: number, e: number, selfId: number) =>
    (datedByRoom.get(roomId) ?? []).some(
      (o) => o.id !== selfId && s < coOff(o) && ciOff(o) < e
    );

  const moveMutation = useMutation({
    mutationFn: (v: { id: number; check_in: string; check_out: string }) =>
      updateAssignment(v.id, { check_in: v.check_in, check_out: v.check_out }),
    onSuccess: () => toast.success("Booking updated"),
    onError: (e: Error) => {
      toast.error(e.message);
      invalidateBookingViews(qc);
    },
    onSettled: () => invalidateBookingViews(qc),
  });

  // Global listeners live only while a drag is active (deps stable during drag).
  useEffect(() => {
    if (!drag) return;
    const onMove = (ev: MouseEvent) => {
      const d = dragRef.current;
      if (!d) return;
      const delta = Math.round((ev.clientX - d.startX) / col);
      if (delta !== d.delta) setDrag({ ...d, delta });
    };
    const onUp = () => {
      const d = dragRef.current;
      if (!d) return;
      const { s, e } = preview(d, d.delta);
      const moved = s !== ciOff(d.b) || e !== coOff(d.b);
      if (!moved) {
        setDrag(null);
        openEdit(d.b); // a click without movement opens the editor
        return;
      }
      if (overlaps(d.roomId, s, e, d.b.id)) {
        toast.error("Overlaps another booking");
        setDrag(null);
        return;
      }
      const newCI = addDays(new Date(d.b.check_in as string), s - ciOff(d.b));
      const newCO = addDays(new Date(d.b.check_out as string), e - coOff(d.b));
      const ci = newCI.toISOString();
      const co = newCO.toISOString();
      setDrag(null);
      qc.setQueryData<Assignment[]>(["assignments"], (old) =>
        (old ?? []).map((x) => (x.id === d.b.id ? { ...x, check_in: ci, check_out: co } : x))
      );
      moveMutation.mutate({ id: d.b.id, check_in: ci, check_out: co });
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [!!drag, col, days]);

  const shift = (dir: 1 | -1) =>
    setAnchor((a) =>
      view === "day" ? addDays(a, dir) : view === "week" ? addWeeks(a, dir) : addMonths(a, dir)
    );
  const label =
    view === "day"
      ? format(anchor, "EEEE, dd MMM yyyy")
      : view === "week"
      ? `${format(days[0], "dd MMM")} – ${format(days[days.length - 1], "dd MMM yyyy")}`
      : format(anchor, "MMMM yyyy");

  const loading = roomsLoading || bookingsLoading;
  const freeOn = (day: Date) => rooms.filter((r) => !occupantOf(r.id, day)).length;

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Calendar</h1>
          <p className="text-sm text-gray-500 mt-1">{label}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="inline-flex rounded-lg border border-gray-200 bg-white p-0.5">
            {(["day", "week", "month"] as View[]).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={clsx(
                  "px-3 py-1 rounded-md text-sm font-medium capitalize transition-colors",
                  view === v ? "bg-brand-50 text-brand-700" : "text-gray-500 hover:text-gray-700"
                )}
              >
                {v}
              </button>
            ))}
          </div>
          <button className="btn-secondary px-2" onClick={() => shift(-1)} aria-label="Previous">
            <ChevronLeft size={16} />
          </button>
          <button className="btn-secondary" onClick={() => setAnchor(today)}>
            Today
          </button>
          <button className="btn-secondary px-2" onClick={() => shift(1)} aria-label="Next">
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      <div className="flex items-center gap-4 mb-3 text-xs text-gray-500 flex-wrap">
        {ROOM_STATUS_ORDER.filter((s) => s !== "available").map((s) => (
          <span key={s} className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: ROOM_STATUS[s].hex }} />
            {ROOM_STATUS[s].full}
          </span>
        ))}
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: EXPIRED_HEX }} /> No-show
        </span>
        <span className="text-gray-400 hidden sm:inline">
          · drag a bar to move it, drag its edges to resize
        </span>
      </div>

      {roomsError || bookingsError ? (
        <ErrorState
          what={roomsError ? "rooms" : "bookings"}
          error={roomsError ? roomsErr : bookingsErr}
          onRetry={() => {
            refetchRooms();
            refetchBookings();
          }}
        />
      ) : loading ? (
        <div className="flex justify-center py-20">
          <Spinner size={32} />
        </div>
      ) : rooms.length === 0 ? (
        <div className="card p-12 text-center text-gray-400">
          <BedDouble size={40} className="mx-auto mb-3 opacity-40" />
          <p>No rooms yet.</p>
        </div>
      ) : view === "day" ? (
        <div className="max-w-2xl">
          <div className="flex items-center justify-between mb-2 px-1">
            <span className="text-sm text-gray-500">Room availability — click a room to book</span>
            <span
              className={clsx(
                "text-xs font-semibold",
                freeOn(days[0]) > 0 ? "text-green-600" : "text-gray-400"
              )}
            >
              {freeOn(days[0])}/{total} free
            </span>
          </div>
          <div className="card divide-y divide-gray-100">
            {rooms.map((room) => {
              const b = occupantOf(room.id, days[0]);
              return (
                <div
                  key={room.id}
                  onClick={() => (b ? openEdit(b) : newBooking(room.id, days[0], addDays(days[0], 1)))}
                  className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors"
                >
                  <span className="font-medium text-gray-900">{room.name}</span>
                  {b ? (
                    <span className="flex items-center gap-2 text-sm">
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: bookingColor(b, now) }}
                      />
                      <span className="text-gray-700">{guestName(b)}</span>
                      <span className="text-gray-400">
                        {format(dayOf(b.check_in as string), "dd MMM")} →{" "}
                        {format(dayOf(b.check_out as string), "dd MMM")}
                      </span>
                    </span>
                  ) : (
                    <span className="flex items-center gap-2 text-sm" style={{ color: ROOM_STATUS.available.hex }}>
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: ROOM_STATUS.available.hex }}
                      />
                      Available
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="card overflow-x-auto select-none">
          <div style={{ minWidth: ROOM_LABEL + trackWidth }}>
            {/* Header: one column per day, with the free/total count */}
            <div className="flex border-b border-gray-200 bg-gray-50">
              <div
                style={{ width: ROOM_LABEL }}
                className="sticky left-0 z-20 bg-gray-50 px-3 py-2 flex items-center text-xs font-medium text-gray-500 uppercase tracking-wide"
              >
                Room
              </div>
              {days.map((day) => {
                const free = freeOn(day);
                const isToday = isSameDay(day, today);
                return (
                  <div
                    key={day.toISOString()}
                    style={{ width: col }}
                    className={clsx(
                      "flex-shrink-0 text-center py-1.5 border-l border-gray-100",
                      isWeekend(day) && "bg-gray-100",
                      isToday && "bg-brand-50"
                    )}
                  >
                    <div className="text-[10px] uppercase text-gray-400">{format(day, "EEE")}</div>
                    <div
                      className={clsx(
                        "text-sm leading-tight",
                        isToday ? "font-bold text-brand-700" : "text-gray-700"
                      )}
                    >
                      {format(day, "d")}
                    </div>
                    <div
                      className={clsx(
                        "text-[10px] font-semibold tabular-nums",
                        free > 0 ? "text-green-600" : "text-gray-400"
                      )}
                      title={`${free} of ${total} free`}
                    >
                      {free}/{total}
                      {col >= 100 ? " free" : ""}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* One row per room */}
            {rooms.map((room) => {
              const roomBookings = datedByRoom.get(room.id) ?? [];
              return (
                <div key={room.id} className="flex border-b border-gray-50 last:border-b-0" style={{ height: ROW_H }}>
                  <div
                    style={{ width: ROOM_LABEL }}
                    className="sticky left-0 z-10 bg-white flex items-center px-3 border-r border-gray-100 text-sm font-medium text-gray-800 truncate"
                  >
                    {room.name}
                  </div>
                  <div className="relative flex-shrink-0" style={{ width: trackWidth }}>
                    {/* Day cells: drag targets + grid */}
                    <div className="flex h-full">
                      {days.map((day, i) => (
                        <div
                          key={i}
                          style={{ width: col }}
                          onMouseDown={() => {
                            dragging.current = true;
                            setSel({ roomId: room.id, a: i, b: i });
                          }}
                          onMouseEnter={() => {
                            if (dragging.current)
                              setSel((s) => (s && s.roomId === room.id ? { ...s, b: i } : s));
                          }}
                          className={clsx(
                            "flex-shrink-0 border-l border-gray-100 cursor-pointer transition-colors hover:bg-brand-50/50",
                            isWeekend(day) && "bg-gray-50/70",
                            isSameDay(day, today) && "bg-brand-50/40"
                          )}
                        />
                      ))}
                    </div>

                    {/* Drag selection highlight */}
                    {sel && sel.roomId === room.id && (
                      <div
                        className="absolute top-1 bottom-1 rounded bg-brand-500/25 border-2 border-brand-500 pointer-events-none"
                        style={{
                          left: Math.min(sel.a, sel.b) * col,
                          width: (Math.abs(sel.a - sel.b) + 1) * col,
                        }}
                      />
                    )}

                    {/* Merged booking bars — draggable to move, edges to resize */}
                    {roomBookings.map((b) => {
                      const isDragging = drag?.b.id === b.id;
                      const { s, e } = isDragging
                        ? preview(drag!, drag!.delta)
                        : { s: ciOff(b), e: coOff(b) };
                      if (!isDragging && (e <= 0 || s >= days.length)) return null;
                      const cs = Math.max(s, 0);
                      const ce = Math.min(e, days.length);
                      if (ce <= cs) return null;
                      const color = bookingColor(b, now);
                      const invalid = isDragging && overlaps(room.id, s, e, b.id);
                      const startHandle = (mode: "move" | "l" | "r") => (ev: React.MouseEvent) => {
                        ev.stopPropagation();
                        ev.preventDefault();
                        setDrag({ b, roomId: room.id, mode, startX: ev.clientX, delta: 0 });
                      };
                      return (
                        <div
                          key={b.id}
                          onMouseDown={startHandle("move")}
                          title={`${guestName(b)} · drag to move, edges to resize`}
                          className="absolute top-1 bottom-1 rounded-md text-white text-xs flex items-center overflow-hidden whitespace-nowrap shadow-sm cursor-grab active:cursor-grabbing"
                          style={{
                            left: cs * col + 2,
                            width: Math.max((ce - cs) * col - 4, 10),
                            backgroundColor: color,
                            zIndex: isDragging ? 30 : 10,
                            filter: isDragging ? "brightness(1.08)" : undefined,
                            outline: invalid ? "2px solid #ef4444" : undefined,
                          }}
                        >
                          <span
                            onMouseDown={startHandle("l")}
                            className="absolute left-0 top-0 bottom-0 w-1.5 cursor-ew-resize bg-black/10 hover:bg-black/30"
                          />
                          <span className="px-2 truncate pointer-events-none">
                            {guestName(b)}
                          </span>
                          <span
                            onMouseDown={startHandle("r")}
                            className="absolute right-0 top-0 bottom-0 w-1.5 cursor-ew-resize bg-black/10 hover:bg-black/30"
                          />
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {undated > 0 && (
        <p className="text-xs text-gray-400 mt-2">
          {undated} booking{undated > 1 ? "s" : ""} without dates {undated > 1 ? "are" : "is"} not shown.
        </p>
      )}

      {/* Edit booking modal */}
      <Modal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={editTarget ? `Edit booking — ${guestName(editTarget)}` : "Edit booking"}
        size="sm"
      >
        <div className="space-y-4">
          <div>
            <label className="label">Room</label>
            <select
              className="input"
              value={editForm.room_id}
              onChange={(e) => setEditForm((f) => ({ ...f, room_id: e.target.value }))}
            >
              {rooms.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Check-in</label>
              <input
                type="datetime-local"
                className="input"
                value={editForm.check_in}
                onChange={(e) => setEditForm((f) => ({ ...f, check_in: e.target.value }))}
              />
            </div>
            <div>
              <label className="label">Check-out</label>
              <input
                type="datetime-local"
                className="input"
                value={editForm.check_out}
                onChange={(e) => setEditForm((f) => ({ ...f, check_out: e.target.value }))}
              />
            </div>
          </div>
          {editTarget && (
            <div className="flex items-center justify-between text-xs text-gray-400">
              <span>
                PIN <PinReveal pin={editTarget.pin} /> · manage delivery from
                Bookings.
              </span>
              <Link
                to={`/app/rooms/${editTarget.room_id}`}
                className="text-brand-600 hover:underline font-medium"
              >
                View room →
              </Link>
            </div>
          )}
          <div className="flex items-center justify-between gap-3 pt-2">
            <button
              className="btn-danger"
              onClick={() => setConfirmDelete(true)}
              disabled={deleteMutation.isPending}
            >
              <Trash2 size={15} /> Delete
            </button>
            <div className="flex gap-3">
              <button className="btn-secondary" onClick={() => setEditTarget(null)}>
                Cancel
              </button>
              <button
                className="btn-primary"
                onClick={() => editMutation.mutate()}
                disabled={editMutation.isPending}
              >
                {editMutation.isPending ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        </div>
      </Modal>
      <ConfirmDialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => {
          setConfirmDelete(false);
          deleteMutation.mutate();
        }}
        title="Delete booking?"
        message="The booking and its PIN are removed. This cannot be undone."
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
