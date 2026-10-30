import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate, Link } from "react-router-dom";
import { format, addDays, startOfDay } from "date-fns";
import {
  BedDouble,
  DoorOpen,
  DoorClosed,
  Building2,
  Trash2,
  Sparkles,
  CalendarClock,
} from "lucide-react";
import { clsx } from "clsx";
import toast from "react-hot-toast";

import { getFloors } from "../api/dashboard";
import { getAssignments, updateAssignment, deleteAssignment } from "../api/assignments";
import { getRooms, markRoomCleaned } from "../api/rooms";
import type { Assignment, Floor, FloorRoom } from "../api/types";
import { toIsoOrNull } from "../lib/datetime";
import Modal from "../components/Modal";
import Spinner from "../components/Spinner";
import ConfirmDialog from "../components/ConfirmDialog";
import ErrorState from "../components/ErrorState";
import PinReveal from "../components/PinReveal";
import { invalidateBookingViews } from "../lib/queries";
import retreat from "../assets/retreat.webp";
import { ROOM_STATUS, ROOM_STATUS_ORDER, withAlpha } from "../lib/roomStatus";

const floorCode = (n: number) =>
  n === 0 ? "GROUND" : n < 0 ? `BSMT ${-n}` : `FLOOR ${String(n).padStart(2, "0")}`;
const toLocalInput = (iso: string) => format(new Date(iso), "yyyy-MM-dd'T'HH:mm");

const GRID_BG = {
  backgroundColor: "#0a1b33",
  backgroundImage:
    "linear-gradient(rgba(56,189,248,0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(56,189,248,0.07) 1px, transparent 1px)",
  backgroundSize: "22px 22px",
};


function StatTile({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string;
  value: number;
  icon: typeof BedDouble;
  tone: "brand" | "cyan" | "violet" | "emerald" | "rose";
}) {
  const tones = {
    brand: "text-brand-600 bg-brand-50",
    cyan: "text-cyan-600 bg-cyan-50",
    violet: "text-violet-600 bg-violet-50",
    emerald: "text-emerald-600 bg-emerald-50",
    rose: "text-rose-600 bg-rose-50",
  };
  return (
    <div className="card p-5 flex items-center gap-4">
      <div className={clsx("w-11 h-11 rounded-xl flex items-center justify-center", tones[tone])}>
        <Icon size={22} />
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900 leading-none">{value}</p>
        <p className="text-sm text-gray-500 mt-1">{label}</p>
      </div>
    </div>
  );
}

function RoomUnit({ r, onOpen }: { r: FloorRoom; onOpen: (r: FloorRoom) => void }) {
  const st = ROOM_STATUS[r.status];
  const free = r.status === "available";
  const hint =
    r.status === "checked_in"
      ? `occupied by ${r.guest} (click to edit)`
      : r.status === "booked"
      ? `reserved for ${r.guest} — not checked in (click to edit)`
      : r.status === "checked_out"
      ? "checked out — needs cleaning (click to clean)"
      : "available (click to book)";
  return (
    <button
      onClick={() => onOpen(r)}
      title={`${r.name}${r.room_type ? " · " + r.room_type : ""} — ${hint}`}
      className="relative flex-shrink-0 w-[76px] h-[58px] rounded-sm font-mono transition-all cursor-pointer border-2 hover:brightness-125"
      style={{
        borderColor: st.hex,
        backgroundColor: withAlpha(st.hex, free ? 0.06 : 0.55),
        backgroundImage: free
          ? undefined
          : `repeating-linear-gradient(45deg, transparent, transparent 5px, ${withAlpha(
              st.dot,
              0.3
            )} 5px, ${withAlpha(st.dot, 0.3)} 6px)`,
      }}
    >
      <span
        className="absolute top-1 left-1.5 text-[11px] font-bold leading-none max-w-[52px] truncate drop-shadow-[0_1px_2px_rgba(0,0,0,0.6)]"
        style={{ color: free ? st.dot : "#ffffff" }}
      >
        {r.name}
      </span>
      <span
        className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full"
        style={{ backgroundColor: st.dot, boxShadow: `0 0 6px ${st.dot}` }}
      />
      <span
        className="absolute bottom-0 left-2 w-3 h-3 border-r border-t rounded-tr-full"
        style={{ borderColor: withAlpha(st.hex, 0.6) }}
      />
      <span
        className="absolute bottom-1 right-1.5 text-[9px] font-bold uppercase tracking-wider drop-shadow-[0_1px_2px_rgba(0,0,0,0.6)]"
        style={{ color: free ? st.dot : "rgba(255,255,255,0.95)" }}
      >
        {st.short}
      </span>
    </button>
  );
}

function BlueprintFloor({ floor, onOpen }: { floor: Floor; onOpen: (r: FloorRoom) => void }) {
  return (
    <div className="flex items-stretch border-b border-cyan-500/15 last:border-b-0">
      <div className="w-28 flex-shrink-0 flex flex-col justify-center px-3 border-r border-cyan-500/15">
        <span className="text-cyan-300 font-mono text-xs tracking-widest">
          {floorCode(floor.floor)}
        </span>
        <span className="text-cyan-500/60 font-mono text-[10px]">{floor.total} UNITS</span>
      </div>
      <div className="flex-1 min-w-0 overflow-x-auto py-3 px-3">
        <div className="flex gap-2">
          {floor.rooms.map((r) => (
            <RoomUnit key={r.id} r={r} onOpen={onOpen} />
          ))}
        </div>
      </div>
      <div className="w-16 flex-shrink-0 flex items-center justify-center border-l border-cyan-500/15">
        <span
          className={clsx(
            "font-mono text-sm font-bold",
            floor.available > 0 ? "text-cyan-300" : "text-amber-300/70"
          )}
        >
          {floor.available}/{floor.total}
        </span>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const nav = useNavigate();
  const qc = useQueryClient();

  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ["dashboard", "floors"], queryFn: getFloors });
  const { data: assignments = [] } = useQuery({ queryKey: ["assignments"], queryFn: getAssignments });
  const { data: rooms = [] } = useQuery({ queryKey: ["rooms"], queryFn: getRooms });

  const now = new Date();

  const newBooking = (roomId: number) => {
    const t = startOfDay(now);
    const p = new URLSearchParams({
      room_id: String(roomId),
      check_in: format(t, "yyyy-MM-dd'T'14:00"),
      check_out: format(addDays(t, 1), "yyyy-MM-dd'T'11:00"),
    });
    nav(`/app/booking?${p.toString()}`);
  };

  // edit reservation modal
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
  const invalidateAll = () => invalidateBookingViews(qc);
  const editMutation = useMutation({
    mutationFn: () =>
      updateAssignment(editTarget!.id, {
        room_id: Number(editForm.room_id),
        check_in: toIsoOrNull(editForm.check_in),
        check_out: toIsoOrNull(editForm.check_out),
      }),
    onSuccess: () => {
      invalidateAll();
      toast.success("Booking updated");
      setEditTarget(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const deleteMutation = useMutation({
    mutationFn: () => deleteAssignment(editTarget!.id),
    onSuccess: () => {
      invalidateAll();
      toast.success("Booking removed");
      setEditTarget(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // housekeeping (checked-out) modal
  const [cleanTarget, setCleanTarget] = useState<FloorRoom | null>(null);
  const cleanMutation = useMutation({
    mutationFn: () => markRoomCleaned(cleanTarget!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dashboard", "floors"] });
      toast.success("Room marked cleaned");
      setCleanTarget(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // The ongoing stay (checked in, not yet checked out) if any, else the earliest
  // still-pending reservation for the room — mirrors the dashboard status logic.
  const reservationFor = (roomId: number) => {
    const mine = assignments.filter((a) => a.room_id === roomId);
    const ended = (a: Assignment) => !!a.check_out && new Date(a.check_out) < now;
    const staying = mine.find((a) => a.checked_in_at && !ended(a));
    if (staying) return staying;
    return mine
      .filter((a) => !a.checked_in_at && !ended(a))
      .sort(
        (a, b) =>
          (a.check_in ? +new Date(a.check_in) : 0) -
          (b.check_in ? +new Date(b.check_in) : 0)
      )[0];
  };

  const handleOpen = (r: FloorRoom) => {
    if (r.status === "checked_in" || r.status === "booked") {
      const a = reservationFor(r.id);
      return a ? openEdit(a) : newBooking(r.id);
    }
    if (r.status === "checked_out") return setCleanTarget(r);
    return newBooking(r.id);
  };

  const guestName = (b: Assignment) =>
    b.guest ? `${b.guest.firstname} ${b.guest.lastname}` : `Guest #${b.guest_id}`;

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <div className="relative overflow-hidden rounded-2xl border border-[#ddd0bd] bg-[#ebe1d7] mb-6">
        <img
          src={retreat}
          loading="lazy"
          alt=""
          aria-hidden
          className="pointer-events-none select-none absolute right-0 top-1/2 -translate-y-1/2 h-[190%] object-contain hidden sm:block"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-[#ebe1d7] via-[#ebe1d7]/85 to-transparent sm:to-[#ebe1d7]/10" />
        <div className="relative px-6 py-6 sm:py-8">
          <p className="text-[11px] font-semibold uppercase tracking-[0.3em] text-[#b8492e]">
            Retreat 480
          </p>
          <h1 className="font-serif text-3xl text-[#3f342a] mt-1">Dashboard</h1>
          <p className="text-sm text-[#7c6b57] mt-1">Room availability by floor</p>
        </div>
      </div>

      {isError ? (
        <ErrorState what="the floor plan" error={error} onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="flex justify-center py-20">
          <Spinner size={32} />
        </div>
      ) : !data || data.totals.total === 0 ? (
        <div className="card p-12 text-center text-gray-400">
          <Building2 size={40} className="mx-auto mb-3 opacity-40" />
          <p>No rooms yet. Add rooms in Property → Rooms.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 max-w-6xl mb-8">
            <StatTile label="Rooms" value={data.totals.total} icon={BedDouble} tone="brand" />
            <StatTile label="Available" value={data.totals.available} icon={DoorOpen} tone="cyan" />
            <StatTile label="Booked" value={data.totals.booked} icon={CalendarClock} tone="violet" />
            <StatTile label="Checked in" value={data.totals.occupied} icon={DoorClosed} tone="emerald" />
            <StatTile label="To clean" value={data.totals.cleaning} icon={Sparkles} tone="rose" />
          </div>

          <div className="max-w-5xl">
            <div className="flex items-center gap-2 mb-3 text-sm font-medium text-gray-500">
              <Building2 size={16} /> Building — floor plan
            </div>

            <div
              className="relative rounded-lg border-2 border-cyan-500/30 shadow-2xl overflow-hidden"
              style={GRID_BG}
            >
              <span className="pointer-events-none absolute top-1.5 left-1.5 w-3 h-3 border-l border-t border-cyan-400/60" />
              <span className="pointer-events-none absolute top-1.5 right-1.5 w-3 h-3 border-r border-t border-cyan-400/60" />
              <span className="pointer-events-none absolute bottom-1.5 left-1.5 w-3 h-3 border-l border-b border-cyan-400/60" />
              <span className="pointer-events-none absolute bottom-1.5 right-1.5 w-3 h-3 border-r border-b border-cyan-400/60" />

              <div className="m-2 border border-cyan-500/20">
                {data.floors.map((f) => (
                  <BlueprintFloor key={f.floor} floor={f} onOpen={handleOpen} />
                ))}

                <div className="flex items-center justify-between px-3 py-2 border-t border-cyan-500/20 bg-cyan-500/5 font-mono text-[10px] text-cyan-400/70 gap-3 flex-wrap">
                  <span className="tracking-widest">RETREAT 480 — FLOOR PLAN</span>
                  <span className="flex items-center gap-3 flex-wrap">
                    {ROOM_STATUS_ORDER.map((s) => {
                      const st = ROOM_STATUS[s];
                      const free = s === "available";
                      return (
                        <span key={s} className="flex items-center gap-1.5 uppercase">
                          <span
                            className="w-3 h-3 rounded-sm border-2"
                            style={{
                              borderColor: st.hex,
                              backgroundColor: withAlpha(st.hex, free ? 0 : 0.55),
                            }}
                          />
                          {st.full}
                        </span>
                      );
                    })}
                    <span className="text-cyan-500/50">REV 1.0</span>
                  </span>
                </div>
              </div>
            </div>
            <p className="text-xs text-gray-400 mt-3">
              Click a vacant unit to book, a booked or checked-in one to edit the reservation,
              or a checked-out one to mark it cleaned.
            </p>
          </div>
        </>
      )}

      {/* Housekeeping modal */}
      <Modal
        open={!!cleanTarget}
        onClose={() => setCleanTarget(null)}
        title={cleanTarget ? `Room ${cleanTarget.name}` : "Room"}
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            This room is{" "}
            <span className="font-medium text-rose-600">checked out</span> and awaiting
            cleaning.
          </p>
          <div className="flex items-center justify-between gap-3">
            <button
              className="btn-secondary"
              onClick={() => {
                const id = cleanTarget!.id;
                setCleanTarget(null);
                newBooking(id);
              }}
            >
              New booking
            </button>
            <button
              className="btn-primary"
              onClick={() => cleanMutation.mutate()}
              disabled={cleanMutation.isPending}
            >
              <Sparkles size={15} /> {cleanMutation.isPending ? "…" : "Mark as cleaned"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Edit reservation modal */}
      <Modal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={editTarget ? `Reservation — ${guestName(editTarget)}` : "Reservation"}
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
                PIN <PinReveal pin={editTarget.pin} /> · manage delivery from Bookings.
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
