import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Trash2,
  RefreshCw,
  CalendarCheck,
  Eye,
  EyeOff,
  Send,
  MessageCircle,
  Smartphone,
  Search,
} from "lucide-react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import { format } from "date-fns";
import { clsx } from "clsx";

import {
  getAssignments,
  createAssignment,
  deleteAssignment,
  regeneratePin,
  getGuestDevices,
  revokeGuestDevice,
  revokeGuestAccess,
} from "../../api/assignments";
import { sendPin } from "../../api/messaging";
import { getGuests } from "../../api/guests";
import { getRooms } from "../../api/rooms";
import { toIsoOrNull } from "../../lib/datetime";
import type { Assignment, Channel } from "../../api/types";
import Modal from "../../components/Modal";
import ConfirmDialog from "../../components/ConfirmDialog";
import ErrorState from "../../components/ErrorState";
import { invalidateBookingViews } from "../../lib/queries";
import Spinner from "../../components/Spinner";
import ViewToggle from "../../components/ViewToggle";
import { useViewMode } from "../../hooks/useViewMode";

export default function AssignmentsPage() {
  const qc = useQueryClient();
  const { data: assignments = [], isLoading, isError, error, refetch } = useQuery({
    queryKey: ["assignments"],
    queryFn: getAssignments,
  });
  const { data: guests = [] } = useQuery({ queryKey: ["guests"], queryFn: getGuests });
  const { data: rooms = [] } = useQuery({ queryKey: ["rooms"], queryFn: getRooms });

  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState({
    guest_id: "",
    room_id: "",
    check_in: "",
    check_out: "",
  });
  const [deleteTarget, setDeleteTarget] = useState<Assignment | null>(null);
  const [regenTarget, setRegenTarget] = useState<Assignment | null>(null);
  const [visiblePins, setVisiblePins] = useState<Set<number>>(new Set());
  const [deviceTarget, setDeviceTarget] = useState<Assignment | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<Assignment | null>(null);
  const devicesQuery = useQuery({
    queryKey: ["guestDevices", deviceTarget?.id],
    queryFn: () => getGuestDevices(deviceTarget!.id),
    enabled: !!deviceTarget,
  });
  const revokeDeviceMutation = useMutation({
    mutationFn: (device: number) => revokeGuestDevice(deviceTarget!.id, device),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["guestDevices"] }); toast.success("Device revoked"); },
    onError: (e: Error) => toast.error(e.message),
  });
  const revokeAccessMutation = useMutation({
    mutationFn: () => revokeGuestAccess(revokeTarget!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["guestDevices"] });
      invalidateBookingViews(qc); setRevokeTarget(null); setDeviceTarget(null);
      toast.success("Guest access disabled for this stay");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const [sendTarget, setSendTarget] = useState<Assignment | null>(null);
  const [channels, setChannels] = useState<Channel[]>(["sms", "whatsapp"]);
  const [view, setView] = useViewMode("bookings");
  const [search, setSearch] = useState("");

  const toggleChannel = (c: Channel) =>
    setChannels((cur) =>
      cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c]
    );

  const togglePin = (id: number) =>
    setVisiblePins((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const createMutation = useMutation({
    mutationFn: () =>
      createAssignment({
        guest_id: Number(form.guest_id),
        room_id: Number(form.room_id),
        check_in: toIsoOrNull(form.check_in),
        check_out: toIsoOrNull(form.check_out),
      }),
    onSuccess: () => {
      invalidateBookingViews(qc);
      toast.success("Booking created — PIN generated automatically");
      setModalOpen(false);
      setForm({ guest_id: "", room_id: "", check_in: "", check_out: "" });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteAssignment(deleteTarget!.id),
    onSuccess: () => {
      invalidateBookingViews(qc);
      toast.success("Booking removed");
      setDeleteTarget(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const regenMutation = useMutation({
    mutationFn: (id: number) => regeneratePin(id),
    onSuccess: () => {
      setRegenTarget(null);
      invalidateBookingViews(qc);
      qc.invalidateQueries({ queryKey: ["guestDevices"] });
      toast.success("New PIN created — previous devices revoked");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const sendMutation = useMutation({
    mutationFn: () => sendPin(sendTarget!.id, channels),
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
      setSendTarget(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const guestName = (a: Assignment) =>
    a.guest ? `${a.guest.firstname} ${a.guest.lastname}` : `Guest #${a.guest_id}`;
  const roomName = (a: Assignment) => a.room?.name ?? `Room #${a.room_id}`;

  const q = search.trim().toLowerCase();
  const filtered = assignments.filter(
    (a) =>
      !q ||
      guestName(a).toLowerCase().includes(q) ||
      roomName(a).toLowerCase().includes(q)
  );

  const pinCell = (a: Assignment) => (
    <div className="flex items-center gap-2">
      <span
        className={clsx(
          "font-mono text-sm tracking-widest",
          visiblePins.has(a.id) ? "text-gray-900" : "text-gray-300 select-none"
        )}
      >
        {visiblePins.has(a.id) ? a.pin : "••••••"}
      </span>
      <button
        className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
        onClick={() => togglePin(a.id)}
        title={visiblePins.has(a.id) ? "Hide PIN" : "Reveal PIN"}
      >
        {visiblePins.has(a.id) ? <EyeOff size={14} /> : <Eye size={14} />}
      </button>
      <button
        className="p-1 text-gray-400 hover:text-brand-600 transition-colors"
        onClick={() => setRegenTarget(a)}
        title="Regenerate PIN"
        disabled={regenMutation.isPending}
      >
        <RefreshCw size={14} />
      </button>
    </div>
  );

  const rowActions = (a: Assignment) => (
    <div className="flex items-center justify-end gap-1">
      <button className="p-1.5 rounded-lg text-gray-400 hover:text-brand-600 hover:bg-brand-50"
        onClick={() => setDeviceTarget(a)} title="Guest devices and access">
        <Smartphone size={15} />
      </button>
      {a.access_revoked_at && <span className="text-xs text-red-600 mr-2">Access disabled</span>}
      <button
        className="p-1.5 rounded-lg text-gray-400 hover:text-brand-600 hover:bg-brand-50 transition-colors"
        onClick={() => {
          setChannels(["sms", "whatsapp"]);
          setSendTarget(a);
        }}
        title="Send PIN to guest"
      >
        <Send size={15} />
      </button>
      <button
        className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
        onClick={() => setDeleteTarget(a)}
        title="Remove booking"
      >
        <Trash2 size={15} />
      </button>
    </div>
  );

  const dateRange = (a: Assignment) =>
    `${a.check_in ? format(new Date(a.check_in), "dd MMM yyyy") : "—"} → ${
      a.check_out ? format(new Date(a.check_out), "dd MMM yyyy") : "—"
    }`;

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Bookings</h1>
          <p className="text-sm text-gray-500 mt-1">
            {filtered.length} of {assignments.length} · guest ↔ room with door PIN
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search
              size={15}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400"
            />
            <input
              className="input pl-8 py-1.5 w-48"
              placeholder="Search guest or room…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <ViewToggle value={view} onChange={setView} />
          <button className="btn-primary" onClick={() => setModalOpen(true)}>
            <Plus size={16} /> New booking
          </button>
        </div>
      </div>

      {isError ? (
        <ErrorState what="bookings" error={error} onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="flex justify-center py-20">
          <Spinner size={32} />
        </div>
      ) : assignments.length === 0 ? (
        <div className="card p-12 text-center text-gray-400">
          <CalendarCheck size={40} className="mx-auto mb-3 opacity-40" />
          <p>No bookings yet.</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="card p-12 text-center text-gray-400">
          <Search size={40} className="mx-auto mb-3 opacity-40" />
          <p>No bookings match your search.</p>
        </div>
      ) : view === "list" ? (
        <div className="card overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-100">
            <thead className="bg-gray-50">
              <tr>
                {["Guest", "Room", "PIN", "Check-in", "Check-out", ""].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((a) => (
                <tr key={a.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {guestName(a)}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/app/rooms/${a.room_id}`}
                      className="text-brand-600 hover:underline"
                    >
                      {roomName(a)}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{pinCell(a)}</td>
                  <td className="px-4 py-3 text-gray-500 text-sm">
                    {a.check_in ? format(new Date(a.check_in), "dd MMM yyyy") : "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-sm">
                    {a.check_out ? format(new Date(a.check_out), "dd MMM yyyy") : "—"}
                  </td>
                  <td className="px-4 py-3 text-right">{rowActions(a)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((a) => (
            <div key={a.id} className="card p-4 flex flex-col gap-2">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="font-semibold text-gray-900 truncate">
                    {guestName(a)}
                  </h3>
                  <p className="text-sm text-gray-500 truncate">{roomName(a)}</p>
                </div>
                {rowActions(a)}
              </div>
              <div className="pt-1">{pinCell(a)}</div>
              <p className="text-xs text-gray-400 mt-auto pt-1">{dateRange(a)}</p>
            </div>
          ))}
        </div>
      )}

      {/* Create assignment modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="New booking"
        size="sm"
      >
        <div className="space-y-4">
          <div>
            <label className="label">Guest *</label>
            <select
              className="input"
              value={form.guest_id}
              onChange={(e) => setForm((f) => ({ ...f, guest_id: e.target.value }))}
            >
              <option value="">Select a guest…</option>
              {guests.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.firstname} {g.lastname}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Room *</label>
            <select
              className="input"
              value={form.room_id}
              onChange={(e) => setForm((f) => ({ ...f, room_id: e.target.value }))}
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
                value={form.check_in}
                onChange={(e) => setForm((f) => ({ ...f, check_in: e.target.value }))}
              />
            </div>
            <div>
              <label className="label">Check-out</label>
              <input
                type="datetime-local"
                className="input"
                value={form.check_out}
                onChange={(e) => setForm((f) => ({ ...f, check_out: e.target.value }))}
              />
            </div>
          </div>
          <p className="text-xs text-gray-400">
            A secure 6-digit PIN will be generated automatically.
          </p>
          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary" onClick={() => setModalOpen(false)}>
              Cancel
            </button>
            <button
              className="btn-primary"
              onClick={() => createMutation.mutate()}
              disabled={!form.guest_id || !form.room_id || createMutation.isPending}
            >
              {createMutation.isPending ? "Assigning…" : "Assign"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Send PIN modal */}
      <Modal
        open={!!sendTarget}
        onClose={() => setSendTarget(null)}
        title="Send PIN to guest"
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            Send the door PIN to{" "}
            <span className="font-medium text-gray-900">
              {sendTarget?.guest
                ? `${sendTarget.guest.firstname} ${sendTarget.guest.lastname}`
                : "the guest"}
            </span>
            {sendTarget?.guest?.phone ? (
              <>
                {" "}
                at{" "}
                <span className="font-mono text-gray-700">
                  {sendTarget.guest.phone}
                </span>
                .
              </>
            ) : (
              <span className="text-red-500"> — no phone number on file.</span>
            )}
          </p>

          <div className="space-y-2">
            <label className="label">Channels</label>
            {(
              [
                { key: "sms", label: "SMS", icon: Smartphone },
                { key: "whatsapp", label: "WhatsApp", icon: MessageCircle },
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

          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary" onClick={() => setSendTarget(null)}>
              Cancel
            </button>
            <button
              className="btn-primary"
              onClick={() => sendMutation.mutate()}
              disabled={
                channels.length === 0 ||
                !sendTarget?.guest?.phone ||
                sendMutation.isPending
              }
            >
              {sendMutation.isPending ? "Sending…" : "Send PIN"}
            </button>
          </div>
        </div>
      </Modal>

      <Modal open={!!deviceTarget} onClose={() => setDeviceTarget(null)} title={`Guest devices — ${deviceTarget?.room?.name ?? "room"}`}>
        <div className="space-y-4 max-h-[65vh] overflow-y-auto pr-1">
          <p className="text-sm text-gray-500">Each phone has its own guest key. Revoking a device removes its key; someone who still knows the stay PIN can activate again. Replace the PIN to block that too.</p>
          {devicesQuery.isLoading ? <Spinner /> : devicesQuery.isError ? <ErrorState what="guest devices" error={devicesQuery.error} onRetry={() => devicesQuery.refetch()} /> : devicesQuery.data?.length ? (
            <ul className="divide-y divide-gray-100">
              {devicesQuery.data.map((device) => <li key={device.id} className="py-3 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium break-words">{device.device_name}</p>
                  <p className="text-xs text-gray-500 mt-1">{device.active ? "Active" : "Expired or revoked"} · Activated {format(new Date(device.created_at), "dd MMM HH:mm")}</p>
                  <p className="text-xs text-gray-400">Last unlock: {device.last_used_at ? format(new Date(device.last_used_at), "dd MMM HH:mm") : "Not yet used"}</p>
                </div>
                {device.active && <button className="btn-secondary text-xs" disabled={revokeDeviceMutation.isPending}
                  onClick={() => revokeDeviceMutation.mutate(device.id)}>Revoke device</button>}
              </li>)}
            </ul>
          ) : <p className="text-sm text-gray-400">No phones have activated this stay PIN yet.</p>}
          <div className="flex flex-wrap gap-2 pt-3 border-t border-gray-100">
            <button className="btn-secondary" onClick={() => { setRegenTarget(deviceTarget); setDeviceTarget(null); }}>Replace PIN and revoke devices</button>
            <button className="btn-secondary text-red-600" onClick={() => setRevokeTarget(deviceTarget)}>Disable guest access</button>
          </div>
        </div>
      </Modal>
      <ConfirmDialog open={!!revokeTarget} onClose={() => setRevokeTarget(null)} onConfirm={() => revokeAccessMutation.mutate()}
        title="Disable guest access?" message="All device keys and the current PIN will stop working for this stay. Create a replacement PIN to re-enable access."
        loading={revokeAccessMutation.isPending} confirmLabel="Disable access" />
      <ConfirmDialog
        open={!!regenTarget}
        onClose={() => setRegenTarget(null)}
        onConfirm={() => regenTarget && regenMutation.mutate(regenTarget.id)}
        title="Regenerate PIN?"
        message="The current PIN and all activated devices stop working immediately. A new PIN re-enables guest access for the stay. Send the new PIN to the guests so each phone can activate again."
        confirmLabel="Regenerate"
        loadingLabel="Regenerating…"
        loading={regenMutation.isPending}
      />
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteMutation.mutate()}
        loading={deleteMutation.isPending}
        title="Remove booking"
        message={`Remove the booking for ${
          deleteTarget?.guest
            ? `${deleteTarget.guest.firstname} ${deleteTarget.guest.lastname}`
            : "this guest"
        } in ${deleteTarget?.room?.name ?? "this room"}? The PIN will be invalidated.`}
      />
    </div>
  );
}
