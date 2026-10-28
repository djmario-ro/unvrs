import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, User } from "lucide-react";
import toast from "react-hot-toast";
import { format } from "date-fns";

import { getGuests, createGuest, updateGuest, deleteGuest } from "../../api/guests";
import type { Guest } from "../../api/types";
import Modal from "../../components/Modal";
import ConfirmDialog from "../../components/ConfirmDialog";
import Spinner from "../../components/Spinner";
import ErrorState from "../../components/ErrorState";
import { invalidateGuestViews } from "../../lib/queries";

type FormData = {
  firstname: string;
  lastname: string;
  email: string;
  phone: string;
  address: string;
  notes: string;
};

const empty: FormData = {
  firstname: "",
  lastname: "",
  email: "",
  phone: "",
  address: "",
  notes: "",
};

export default function GuestsPage() {
  const qc = useQueryClient();
  const { data: guests = [], isLoading, isError, error, refetch } = useQuery({
    queryKey: ["guests"],
    queryFn: getGuests,
  });

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Guest | null>(null);
  const [form, setForm] = useState<FormData>(empty);
  const [deleteTarget, setDeleteTarget] = useState<Guest | null>(null);

  const openCreate = () => {
    setEditing(null);
    setForm(empty);
    setModalOpen(true);
  };

  const openEdit = (g: Guest) => {
    setEditing(g);
    setForm({
      firstname: g.firstname,
      lastname: g.lastname,
      email: g.email ?? "",
      phone: g.phone ?? "",
      address: g.address ?? "",
      notes: g.notes ?? "",
    });
    setModalOpen(true);
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        ...form,
        email: form.email || null,
        phone: form.phone || null,
        address: form.address || null,
        notes: form.notes || null,
      };
      if (editing) return updateGuest(editing.id, payload);
      return createGuest(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["guests"] });
      toast.success(editing ? "Guest updated" : "Guest created");
      setModalOpen(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteGuest(deleteTarget!.id),
    onSuccess: () => {
      invalidateGuestViews(qc);
      toast.success("Guest deleted");
      setDeleteTarget(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const set = (field: keyof FormData) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Guests</h1>
          <p className="text-sm text-gray-500 mt-1">{guests.length} total</p>
        </div>
        <button className="btn-primary" onClick={openCreate}>
          <Plus size={16} /> Add guest
        </button>
      </div>

      {isError ? (
        <ErrorState what="guests" error={error} onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="flex justify-center py-20">
          <Spinner size={32} />
        </div>
      ) : guests.length === 0 ? (
        <div className="card p-12 text-center text-gray-400">
          <User size={40} className="mx-auto mb-3 opacity-40" />
          <p>No guests yet. Add one to get started.</p>
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-100">
            <thead className="bg-gray-50">
              <tr>
                {["Name", "Email", "Phone", "Added"].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide"
                  >
                    {h}
                  </th>
                ))}
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {guests.map((g) => (
                <tr key={g.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {g.firstname} {g.lastname}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-sm">{g.email ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-500 text-sm">{g.phone ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-400 text-sm">
                    {format(new Date(g.created_at), "dd MMM yyyy")}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        className="p-1.5 rounded-lg text-gray-400 hover:text-brand-600 hover:bg-brand-50 transition-colors"
                        onClick={() => openEdit(g)}
                      >
                        <Pencil size={15} />
                      </button>
                      <button
                        className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                        onClick={() => setDeleteTarget(g)}
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create / Edit modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? "Edit guest" : "Add guest"}
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">First name *</label>
              <input className="input" value={form.firstname} onChange={set("firstname")} />
            </div>
            <div>
              <label className="label">Last name *</label>
              <input className="input" value={form.lastname} onChange={set("lastname")} />
            </div>
          </div>
          <div>
            <label className="label">Email</label>
            <input className="input" type="email" value={form.email} onChange={set("email")} />
          </div>
          <div>
            <label className="label">Phone</label>
            <input className="input" value={form.phone} onChange={set("phone")} />
          </div>
          <div>
            <label className="label">Address</label>
            <input className="input" value={form.address} onChange={set("address")} />
          </div>
          <div>
            <label className="label">Notes</label>
            <textarea
              className="input resize-none"
              rows={3}
              value={form.notes}
              onChange={set("notes")}
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary" onClick={() => setModalOpen(false)}>
              Cancel
            </button>
            <button
              className="btn-primary"
              onClick={() => saveMutation.mutate()}
              disabled={!form.firstname || !form.lastname || saveMutation.isPending}
            >
              {saveMutation.isPending ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteMutation.mutate()}
        loading={deleteMutation.isPending}
        title="Delete guest"
        message={`Remove ${deleteTarget?.firstname} ${deleteTarget?.lastname}? This will also remove all their room assignments.`}
      />
    </div>
  );
}
