import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, ShieldCheck } from "lucide-react";
import toast from "react-hot-toast";
import { format } from "date-fns";
import { clsx } from "clsx";

import { getUsers, createUser, updateUser, deleteUser } from "../api/users";
import type { Role, User } from "../api/types";
import { useMe } from "../hooks/useMe";
import Modal from "../components/Modal";
import ConfirmDialog from "../components/ConfirmDialog";
import Spinner from "../components/Spinner";

const empty = { username: "", password: "", role: "frontdesk" as Role };

export default function UsersPage() {
  const qc = useQueryClient();
  const { data: me } = useMe();
  const { data: users = [], isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: getUsers,
  });

  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);
  const [editTarget, setEditTarget] = useState<User | null>(null);
  const [editForm, setEditForm] = useState<{ password: string; role: Role }>({
    password: "",
    role: "frontdesk",
  });

  const createMutation = useMutation({
    mutationFn: () => createUser(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      toast.success("User created");
      setModalOpen(false);
      setForm(empty);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const editMutation = useMutation({
    mutationFn: () =>
      updateUser(editTarget!.id, {
        role: editForm.role,
        ...(editForm.password ? { password: editForm.password } : {}),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      toast.success("User updated");
      setEditTarget(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const openEdit = (u: User) => {
    setEditForm({ password: "", role: (u.role as Role) ?? "frontdesk" });
    setEditTarget(u);
  };

  const deleteMutation = useMutation({
    mutationFn: () => deleteUser(deleteTarget!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      toast.success("User deleted");
      setDeleteTarget(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Users</h1>
          <p className="text-sm text-gray-500 mt-1">
            Staff accounts for property management and front desk
          </p>
        </div>
        <button className="btn-primary" onClick={() => setModalOpen(true)}>
          <Plus size={16} /> Add user
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20">
          <Spinner size={32} />
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-100">
            <thead className="bg-gray-50">
              <tr>
                {["User", "Role", "Created", ""].map((h) => (
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
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {u.username}
                    {u.id === me?.id && (
                      <span className="ml-2 text-xs text-gray-400">(you)</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={clsx(
                        "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium capitalize",
                        u.role === "admin"
                          ? "bg-brand-50 text-brand-700"
                          : "bg-gray-100 text-gray-600"
                      )}
                    >
                      {u.role === "admin" && <ShieldCheck size={12} />}
                      {u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {format(new Date(u.created_at), "dd MMM yyyy")}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        className="p-1.5 rounded-lg text-gray-400 hover:text-brand-600 hover:bg-brand-50 transition-colors"
                        onClick={() => openEdit(u)}
                        title="Edit role / reset password"
                      >
                        <Pencil size={15} />
                      </button>
                      <button
                        className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
                        onClick={() => setDeleteTarget(u)}
                        disabled={u.id === me?.id}
                        title={u.id === me?.id ? "You can't delete yourself" : "Delete user"}
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

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Add user"
        size="sm"
      >
        <div className="space-y-4">
          <div>
            <label className="label">Username *</label>
            <input
              className="input"
              value={form.username}
              onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
            />
          </div>
          <div>
            <label className="label">Password *</label>
            <input
              type="password"
              className="input"
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
            />
          </div>
          <div>
            <label className="label">Role</label>
            <select
              className="input"
              value={form.role}
              onChange={(e) =>
                setForm((f) => ({ ...f, role: e.target.value as Role }))
              }
            >
              <option value="frontdesk">Front desk</option>
              <option value="admin">Admin (property)</option>
            </select>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary" onClick={() => setModalOpen(false)}>
              Cancel
            </button>
            <button
              className="btn-primary"
              onClick={() => createMutation.mutate()}
              disabled={!form.username || !form.password || createMutation.isPending}
            >
              {createMutation.isPending ? "Creating…" : "Create user"}
            </button>
          </div>
        </div>
      </Modal>

      <Modal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={`Edit ${editTarget?.username ?? "user"}`}
        size="sm"
      >
        <div className="space-y-4">
          <div>
            <label className="label">Role</label>
            <select
              className="input"
              value={editForm.role}
              onChange={(e) =>
                setEditForm((f) => ({ ...f, role: e.target.value as Role }))
              }
            >
              <option value="frontdesk">Front desk</option>
              <option value="admin">Admin (property)</option>
            </select>
          </div>
          <div>
            <label className="label">New password</label>
            <input
              type="password"
              className="input"
              placeholder="Leave blank to keep current"
              value={editForm.password}
              onChange={(e) =>
                setEditForm((f) => ({ ...f, password: e.target.value }))
              }
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary" onClick={() => setEditTarget(null)}>
              Cancel
            </button>
            <button
              className="btn-primary"
              onClick={() => editMutation.mutate()}
              disabled={editMutation.isPending}
            >
              {editMutation.isPending ? "Saving…" : "Save changes"}
            </button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteMutation.mutate()}
        loading={deleteMutation.isPending}
        title="Delete user"
        message={`Remove user "${deleteTarget?.username}"? They will lose access immediately.`}
      />
    </div>
  );
}
