import { Fragment, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  UserPlus,
  BedDouble,
  KeyRound,
  Send,
  CheckCircle2,
  ArrowLeft,
  ArrowRight,
  Smartphone,
  MessageCircle,
  PartyPopper,
} from "lucide-react";
import toast from "react-hot-toast";
import { invalidateBookingViews } from "../../lib/queries";
import { format } from "date-fns";
import { clsx } from "clsx";

import { getGuests, createGuest } from "../../api/guests";
import { getRooms, getRoomQrUrl } from "../../api/rooms";
import { createAssignment } from "../../api/assignments";
import { sendPin } from "../../api/messaging";
import { toIsoOrNull } from "../../lib/datetime";
import type { Assignment, Channel, Guest, MessageLog } from "../../api/types";

const steps = [
  { n: 1, label: "Client" },
  { n: 2, label: "Room & dates" },
  { n: 3, label: "PIN & send" },
  { n: 4, label: "Done" },
];

const emptyGuest = { firstname: "", lastname: "", phone: "", email: "" };
const emptyBooking = { room_id: "", check_in: "", check_out: "" };

export default function BookingPage() {
  const qc = useQueryClient();
  const { data: guests = [] } = useQuery({ queryKey: ["guests"], queryFn: getGuests });
  const { data: rooms = [] } = useQuery({ queryKey: ["rooms"], queryFn: getRooms });

  const [searchParams] = useSearchParams();
  const [step, setStep] = useState(1);
  const [guestMode, setGuestMode] = useState<"new" | "existing">("new");
  const [newGuest, setNewGuest] = useState(emptyGuest);
  const [existingGuestId, setExistingGuestId] = useState("");
  const [guest, setGuest] = useState<Guest | null>(null);
  // Pre-filled when arriving from the calendar (?room_id=&check_in=&check_out=)
  const [booking, setBooking] = useState(() => ({
    room_id: searchParams.get("room_id") ?? "",
    check_in: searchParams.get("check_in") ?? "",
    check_out: searchParams.get("check_out") ?? "",
  }));
  const [assignment, setAssignment] = useState<Assignment | null>(null);
  const [channels, setChannels] = useState<Channel[]>(["whatsapp", "sms"]);
  const [sendResults, setSendResults] = useState<MessageLog[] | null>(null);

  const toggleChannel = (c: Channel) =>
    setChannels((cur) =>
      cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c]
    );

  const reset = () => {
    setStep(1);
    setGuestMode("new");
    setNewGuest(emptyGuest);
    setExistingGuestId("");
    setGuest(null);
    setBooking(emptyBooking);
    setAssignment(null);
    setChannels(["whatsapp", "sms"]);
    setSendResults(null);
  };

  const createGuestMutation = useMutation({
    mutationFn: () =>
      createGuest({
        firstname: newGuest.firstname,
        lastname: newGuest.lastname,
        phone: newGuest.phone || null,
        email: newGuest.email || null,
        address: null,
        notes: null,
      }),
    onSuccess: (g) => {
      qc.invalidateQueries({ queryKey: ["guests"] });
      setGuest(g);
      setStep(2);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const createAssignmentMutation = useMutation({
    mutationFn: () =>
      createAssignment({
        guest_id: guest!.id,
        room_id: Number(booking.room_id),
        check_in: toIsoOrNull(booking.check_in),
        check_out: toIsoOrNull(booking.check_out),
      }),
    onSuccess: (a) => {
      invalidateBookingViews(qc);
      setAssignment(a);
      setStep(3);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const sendMutation = useMutation({
    mutationFn: () => sendPin(assignment!.id, channels),
    onSuccess: (res) => {
      const failed = res.results.filter((r) => r.status === "failed");
      const mocked = res.results.filter((r) => r.status === "mocked");
      if (failed.length) {
        toast.error(`Delivery issue: ${failed.map((f) => f.channel).join(", ")}`);
      } else if (mocked.length) {
        toast(`Not delivered: ${mocked.map((m) => m.channel).join(", ")} is not configured on the server`, { icon: "⚠️" });
      } else {
        toast.success("PIN sent to guest");
      }
      setSendResults(res.results);
      setStep(4);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const onClientNext = () => {
    if (guestMode === "new") {
      createGuestMutation.mutate();
    } else {
      const g = guests.find((x) => x.id === Number(existingGuestId));
      if (!g) return;
      setGuest(g);
      setStep(2);
    }
  };

  const clientReady =
    guestMode === "new"
      ? newGuest.firstname.trim() && newGuest.lastname.trim()
      : !!existingGuestId;

  const room = rooms.find((r) => r.id === Number(booking.room_id));

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">New Booking</h1>
        <p className="text-sm text-gray-500 mt-1">
          Register a client, assign a room, and send their access PIN
        </p>
      </div>

      {/* Stepper */}
      <div className="flex items-center gap-3 mb-8 max-w-3xl">
        {steps.map((s, i) => (
          <Fragment key={s.n}>
            <div className="flex items-center gap-2">
              <div
                className={clsx(
                  "w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-colors",
                  step >= s.n ? "bg-brand-600 text-white" : "bg-gray-200 text-gray-500"
                )}
              >
                {step > s.n ? <Check size={16} /> : s.n}
              </div>
              <span
                className={clsx(
                  "text-sm font-medium hidden sm:block",
                  step >= s.n ? "text-gray-900" : "text-gray-400"
                )}
              >
                {s.label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div
                className={clsx(
                  "flex-1 h-px",
                  step > s.n ? "bg-brand-600" : "bg-gray-200"
                )}
              />
            )}
          </Fragment>
        ))}
      </div>

      <div className="card p-6 max-w-3xl">
        {/* Step 1 — Client */}
        {step === 1 && (
          <div className="space-y-5">
            <div className="flex items-center gap-2 text-gray-900">
              <UserPlus size={18} className="text-brand-600" />
              <h2 className="font-semibold">Who is the client?</h2>
            </div>

            <div className="flex gap-2">
              {(["new", "existing"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setGuestMode(m)}
                  className={clsx(
                    "px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors",
                    guestMode === m
                      ? "border-brand-500 bg-brand-50 text-brand-700"
                      : "border-gray-200 text-gray-600 hover:bg-gray-50"
                  )}
                >
                  {m === "new" ? "New guest" : "Existing guest"}
                </button>
              ))}
            </div>

            {guestMode === "new" ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="label">First name *</label>
                    <input
                      className="input"
                      value={newGuest.firstname}
                      onChange={(e) =>
                        setNewGuest((g) => ({ ...g, firstname: e.target.value }))
                      }
                    />
                  </div>
                  <div>
                    <label className="label">Last name *</label>
                    <input
                      className="input"
                      value={newGuest.lastname}
                      onChange={(e) =>
                        setNewGuest((g) => ({ ...g, lastname: e.target.value }))
                      }
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="label">Phone</label>
                    <input
                      className="input"
                      placeholder="0743… or +40743…"
                      value={newGuest.phone}
                      onChange={(e) =>
                        setNewGuest((g) => ({ ...g, phone: e.target.value }))
                      }
                    />
                  </div>
                  <div>
                    <label className="label">Email</label>
                    <input
                      className="input"
                      type="email"
                      value={newGuest.email}
                      onChange={(e) =>
                        setNewGuest((g) => ({ ...g, email: e.target.value }))
                      }
                    />
                  </div>
                </div>
                <p className="text-xs text-gray-400">
                  A phone number is needed to send the PIN by SMS or WhatsApp.
                </p>
              </div>
            ) : (
              <div>
                <label className="label">Select a guest</label>
                <select
                  className="input"
                  value={existingGuestId}
                  onChange={(e) => setExistingGuestId(e.target.value)}
                >
                  <option value="">Select a guest…</option>
                  {guests.map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.firstname} {g.lastname}
                      {g.phone ? ` · ${g.phone}` : ""}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <button
                className="btn-primary"
                onClick={onClientNext}
                disabled={!clientReady || createGuestMutation.isPending}
              >
                {createGuestMutation.isPending ? "Saving…" : "Continue"}
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        )}

        {/* Step 2 — Room & dates */}
        {step === 2 && (
          <div className="space-y-5">
            <div className="flex items-center gap-2 text-gray-900">
              <BedDouble size={18} className="text-brand-600" />
              <h2 className="font-semibold">
                Book a room for {guest?.firstname} {guest?.lastname}
              </h2>
            </div>

            <div>
              <label className="label">Room *</label>
              <select
                className="input"
                value={booking.room_id}
                onChange={(e) =>
                  setBooking((b) => ({ ...b, room_id: e.target.value }))
                }
              >
                <option value="">Select a room…</option>
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
                  value={booking.check_in}
                  onChange={(e) =>
                    setBooking((b) => ({ ...b, check_in: e.target.value }))
                  }
                />
              </div>
              <div>
                <label className="label">Check-out</label>
                <input
                  type="datetime-local"
                  className="input"
                  value={booking.check_out}
                  onChange={(e) =>
                    setBooking((b) => ({ ...b, check_out: e.target.value }))
                  }
                />
              </div>
            </div>
            <p className="text-xs text-gray-400">
              A secure 6-digit PIN is generated automatically for this booking.
            </p>

            <div className="flex justify-between pt-2">
              <button className="btn-secondary" onClick={() => setStep(1)}>
                <ArrowLeft size={16} /> Back
              </button>
              <button
                className="btn-primary"
                onClick={() => createAssignmentMutation.mutate()}
                disabled={!booking.room_id || createAssignmentMutation.isPending}
              >
                {createAssignmentMutation.isPending ? "Creating…" : "Generate PIN"}
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        )}

        {/* Step 3 — PIN & send */}
        {step === 3 && assignment && (
          <div className="space-y-5">
            <div className="flex items-center gap-2 text-gray-900">
              <KeyRound size={18} className="text-brand-600" />
              <h2 className="font-semibold">Booking ready — send the PIN</h2>
            </div>

            <div className="flex flex-col sm:flex-row gap-6">
              <div className="flex-1 space-y-3">
                <div>
                  <div className="label">Access PIN</div>
                  <div className="font-mono text-3xl tracking-widest text-gray-900">
                    {assignment.pin}
                  </div>
                </div>
                <div className="text-sm text-gray-600 space-y-1">
                  <div>
                    <span className="text-gray-400">Guest: </span>
                    {guest?.firstname} {guest?.lastname}
                  </div>
                  <div>
                    <span className="text-gray-400">Room: </span>
                    {room?.name ?? `#${assignment.room_id}`}
                  </div>
                  <div>
                    <span className="text-gray-400">Phone: </span>
                    {guest?.phone || (
                      <span className="text-red-500">none on file</span>
                    )}
                  </div>
                </div>
              </div>
              <div className="text-center">
                <img
                  src={getRoomQrUrl(assignment.room_id)}
                  alt="Room door QR"
                  className="w-40 h-40 rounded-xl border border-gray-100 mx-auto"
                />
                <p className="text-xs text-gray-400 mt-1">Door QR (sent on WhatsApp)</p>
              </div>
            </div>

            <div className="space-y-2">
              <label className="label">Send via</label>
              {(
                [
                  { key: "whatsapp", label: "WhatsApp (PIN + QR)", icon: MessageCircle },
                  { key: "sms", label: "SMS (text only)", icon: Smartphone },
                ] as const
              ).map(({ key, label, icon: Icon }) => (
                <label
                  key={key}
                  className={clsx(
                    "flex items-center gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-colors",
                    channels.includes(key)
                      ? "border-brand-500 bg-brand-50"
                      : "border-gray-200 hover:bg-gray-50"
                  )}
                >
                  <input
                    type="checkbox"
                    className="accent-brand-600"
                    checked={channels.includes(key)}
                    onChange={() => toggleChannel(key)}
                  />
                  <Icon size={16} className="text-gray-500" />
                  <span className="text-sm text-gray-700">{label}</span>
                </label>
              ))}
            </div>

            <div className="flex justify-between pt-2">
              <button className="btn-secondary" onClick={() => setStep(4)}>
                Skip for now
              </button>
              <button
                className="btn-primary"
                onClick={() => sendMutation.mutate()}
                disabled={
                  channels.length === 0 || !guest?.phone || sendMutation.isPending
                }
              >
                {sendMutation.isPending ? "Sending…" : "Send PIN"}
                <Send size={16} />
              </button>
            </div>
          </div>
        )}

        {/* Step 4 — Done */}
        {step === 4 && assignment && (
          <div className="space-y-5 text-center">
            <PartyPopper size={40} className="mx-auto text-brand-600" />
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Booking complete</h2>
              <p className="text-sm text-gray-500 mt-1">
                {guest?.firstname} {guest?.lastname} · {room?.name} · PIN{" "}
                <span className="font-mono">{assignment.pin}</span>
              </p>
            </div>

            {(assignment.check_in || assignment.check_out) && (
              <p className="text-sm text-gray-500">
                {assignment.check_in
                  ? format(new Date(assignment.check_in), "dd MMM yyyy HH:mm")
                  : "—"}{" "}
                →{" "}
                {assignment.check_out
                  ? format(new Date(assignment.check_out), "dd MMM yyyy HH:mm")
                  : "—"}
              </p>
            )}

            {sendResults && (
              <div className="inline-flex flex-col gap-1 text-sm">
                {sendResults.map((r) => (
                  <div key={r.id} className="flex items-center gap-2 justify-center">
                    <CheckCircle2
                      size={15}
                      className={
                        r.status === "sent"
                          ? "text-green-500"
                          : r.status === "mocked"
                            ? "text-amber-500"
                            : "text-red-400"
                      }
                    />
                    <span className="text-gray-600">
                      {r.channel} — {r.status === "mocked" ? "not configured" : r.status}
                    </span>
                  </div>
                ))}
              </div>
            )}

            <div className="flex justify-center pt-2">
              <button className="btn-primary" onClick={reset}>
                Start new booking
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
