import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, BedDouble, QrCode } from "lucide-react";
import toast from "react-hot-toast";
import { format } from "date-fns";

import { getRooms, createRoom, updateRoom, deleteRoom, getRoomQrUrl } from "../../api/rooms";
import type { Room } from "../../api/types";
import Modal from "../../components/Modal";
import ConfirmDialog from "../../components/ConfirmDialog";
import Spinner from "../../components/Spinner";

type FormData = { name: string; description: string };
const empty: FormData = { name: "", description: "" };

export default function RoomsPage() {
  const qc = useQueryClient();
  const { data: rooms = [], isLoading } = useQuery({
    queryKey: ["rooms"],
    queryFn: getRooms,
  });

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Room | null>(null);
  const [form, setForm] = useState<FormData>(empty);
  const [deleteTarget, setDeleteTarget] = useState<Room | null>(null);
  const [qrRoom, setQrRoom] = useState<Room | null>(null);

  const openCreate = () => {
    setEditing(null);
    setForm(empty);
    setModalOpen(true);
  };

  const openEdit = (r: Room) => {
    setEditing(r);
    setForm({ name: r.name, description: r.description ?? "" });
    setModalOpen(true);
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = { ...form, description: form.description || null };
      if (editing) return updateRoom(editing.id, payload);
      return createRoom(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rooms"] });
      toast.success(editing ? "Room updated" : "Room created");
      setModalOpen(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteRoom(deleteTarget!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rooms"] });
      toast.success("Room deleted");
      setDeleteTarget(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const set = (field: keyof FormData) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Rooms</h1>
          <p className="text-sm text-gray-500 mt-1">{rooms.length} total</p>
        </div>
        <button className="btn-primary" onClick={openCreate}>
          <Plus size={16} /> Add room
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20">
          <Spinner size={32} />
        </div>
      ) : rooms.length === 0 ? (
        <div className="card p-12 text-center text-gray-400">
          <BedDouble size={40} className="mx-auto mb-3 opacity-40" />
          <p>No rooms yet.</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {rooms.map((r) => (
            <div key={r.id} className="card p-5 flex flex-col gap-3">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900">{r.name}</h3>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Created {format(new Date(r.created_at), "dd MMM yyyy")}
                  </p>
                </div>
                <div className="flex gap-1">
                  <button
                    className="p-1.5 rounded-lg text-gray-400 hover:text-brand-600 hover:bg-brand-50 transition-colors"
                    onClick={() => setQrRoom(r)}
                    title="View QR code"
                  >
                    <QrCode size={15} />
                  </button>
                  <button
                    className="p-1.5 rounded-lg text-gray-400 hover:text-brand-600 hover:bg-brand-50 transition-colors"
                    onClick={() => openEdit(r)}
                  >
                    <Pencil size={15} />
                  </button>
                  <button
                    className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                    onClick={() => setDeleteTarget(r)}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
              {r.description && (
                <p className="text-sm text-gray-500 line-clamp-2">{r.description}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Create / Edit modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? "Edit room" : "Add room"}
        size="sm"
      >
        <div className="space-y-4">
          <div>
            <label className="label">Room name *</label>
            <input className="input" value={form.name} onChange={set("name")} placeholder="e.g. Suite 101" />
          </div>
          <div>
            <label className="label">Description</label>
            <textarea
              className="input resize-none"
              rows={3}
              value={form.description}
              onChange={set("description")}
              placeholder="Optional description…"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary" onClick={() => setModalOpen(false)}>
              Cancel
            </button>
            <button
              className="btn-primary"
              onClick={() => saveMutation.mutate()}
              disabled={!form.name || saveMutation.isPending}
            >
              {saveMutation.isPending ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      </Modal>

      {/* QR code modal */}
      <Modal
        open={!!qrRoom}
        onClose={() => setQrRoom(null)}
        title={`QR Code — ${qrRoom?.name}`}
        size="sm"
      >
        {qrRoom && (
          <div className="flex flex-col items-center gap-4">
            <img
              src={getRoomQrUrl(qrRoom.id)}
              alt={`QR code for ${qrRoom.name}`}
              className="w-56 h-56 rounded-lg border border-gray-100"
            />
            <p className="text-xs text-gray-400 text-center">
              Guests scan this QR to access the door entry page for{" "}
              <strong>{qrRoom.name}</strong>.
            </p>
            <a
              href={getRoomQrUrl(qrRoom.id)}
              download={`qr-${qrRoom.name}.png`}
              className="btn-secondary text-xs"
            >
              Download PNG
            </a>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteMutation.mutate()}
        loading={deleteMutation.isPending}
        title="Delete room"
        message={`Remove room "${deleteTarget?.name}"? All assignments for this room will also be deleted.`}
      />
    </div>
  );
}
