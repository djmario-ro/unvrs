import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, RefreshCw, Link2, Eye, EyeOff } from "lucide-react";
import toast from "react-hot-toast";
import { format } from "date-fns";
import { clsx } from "clsx";

import {
  getAssignments,
  createAssignment,
  deleteAssignment,
  regeneratePin,
} from "../../api/assignments";
import { getGuests } from "../../api/guests";
import { getRooms } from "../../api/rooms";
import type { Assignment } from "../../api/types";
import Modal from "../../components/Modal";
import ConfirmDialog from "../../components/ConfirmDialog";
import Spinner from "../../components/Spinner";

export default function AssignmentsPage() {
  const qc = useQueryClient();
  const { data: assignments = [], isLoading } = useQuery({
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
  const [visiblePins, setVisiblePins] = useState<Set<number>>(new Set());

  const togglePin = (id: number) =>
    setVisiblePins((s) => {
      const next = new Set(s);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const createMutation = useMutation({
    mutationFn: () =>
      createAssignment({
        guest_id: Number(form.guest_id),
        room_id: Number(form.room_id),
        check_in: form.check_in || null,
        check_out: form.check_out || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assignments"] });
      toast.success("Assignment created — PIN generated automatically");
      setModalOpen(false);
      setForm({ guest_id: "", room_id: "", check_in: "", check_out: "" });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteAssignment(deleteTarget!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assignments"] });
      toast.success("Assignment removed");
      setDeleteTarget(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const regenMutation = useMutation({
    mutationFn: (id: number) => regeneratePin(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assignments"] });
      toast.success("PIN regenerated");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Assignments</h1>
          <p className="text-sm text-gray-500 mt-1">
            Guest ↔ Room links with door PINs
          </p>
        </div>
        <button className="btn-primary" onClick={() => setModalOpen(true)}>
          <Plus size={16} /> Assign guest
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20">
          <Spinner size={32} />
        </div>
      ) : assignments.length === 0 ? (
        <div className="card p-12 text-center text-gray-400">
          <Link2 size={40} className="mx-auto mb-3 opacity-40" />
          <p>No assignments yet.</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
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
              {assignments.map((a) => (
                <tr key={a.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {a.guest
                      ? `${a.guest.firstname} ${a.guest.lastname}`
                      : `Guest #${a.guest_id}`}
                  </td>
                  <td className="px-4 py-3 text-gray-700">
                    {a.room?.name ?? `Room #${a.room_id}`}
                  </td>
                  <td className="px-4 py-3">
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
                        onClick={() => regenMutation.mutate(a.id)}
                        title="Regenerate PIN"
                        disabled={regenMutation.isPending}
                      >
                        <RefreshCw size={14} />
                      </button>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-sm">
                    {a.check_in ? format(new Date(a.check_in), "dd MMM yyyy") : "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-sm">
                    {a.check_out ? format(new Date(a.check_out), "dd MMM yyyy") : "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                      onClick={() => setDeleteTarget(a)}
                    >
                      <Trash2 size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create assignment modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Assign guest to room"
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

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteMutation.mutate()}
        loading={deleteMutation.isPending}
        title="Remove assignment"
        message={`Remove the assignment for ${
          deleteTarget?.guest
            ? `${deleteTarget.guest.firstname} ${deleteTarget.guest.lastname}`
            : "this guest"
        } in ${deleteTarget?.room?.name ?? "this room"}? The PIN will be invalidated.`}
      />
    </div>
  );
}
