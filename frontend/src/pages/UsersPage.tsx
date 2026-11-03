import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { getUsers, createUser, updateUser, deleteUser } from "../api/users";
import type { Role, User } from "../api/types";
import { useMe } from "../hooks/useMe";
import { useAuthConfig } from "../hooks/useAuthConfig";
import Modal from "../components/Modal";
import ConfirmDialog from "../components/ConfirmDialog";
import Spinner from "../components/Spinner";
const ALL_ROLES: Role[] = [
  "owner",
  "administrator",
  "frontdesk",
  "housekeeping",
  "maintenance",
];
const empty = {
  username: "",
  password: "",
  oidc_subject: "",
  roles: ["frontdesk"] as Role[],
};
export default function UsersPage() {
  const qc = useQueryClient();
  const { data: me } = useMe();
  const {
    data: auth,
    isLoading: authLoading,
    isError: authError,
  } = useAuthConfig();
  const isSSO = auth?.provider === "keycloak";
  const {
    data: users = [],
    isLoading,
    isError,
  } = useQuery({ queryKey: ["users"], queryFn: getUsers });
  const [form, setForm] = useState(empty),
    [open, setOpen] = useState(false),
    [editing, setEditing] = useState<User | null>(null),
    [removing, setRemoving] = useState<User | null>(null);
  const owner = me?.roles.includes("owner");
  const grantable = owner
    ? ALL_ROLES
    : ALL_ROLES.filter((r) => r !== "owner" && r !== "administrator");
  const save = useMutation({
    mutationFn: () =>
      editing
        ? updateUser(editing.id, {
            roles: form.roles,
            ...(isSSO && !editing.oidc_subject && form.oidc_subject
              ? { oidc_subject: form.oidc_subject }
              : {}),
            ...(!isSSO && form.password ? { password: form.password } : {}),
          })
        : createUser({
            username: form.username,
            roles: form.roles,
            ...(isSSO
              ? { oidc_subject: form.oidc_subject }
              : { password: form.password }),
          }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setOpen(false);
      toast.success("Property access saved");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const remove = useMutation({
    mutationFn: () => deleteUser(removing!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setRemoving(null);
      toast.success("Property access removed");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const editable = (u: User) =>
    u.id !== me?.id &&
    (owner || !u.roles.some((r) => r === "owner" || r === "administrator"));
  return (
    <div className="p-4 sm:p-8">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">Staff access</h1>
          <p className="text-sm text-gray-500">
            Roles apply to the selected property. Sign-in accounts and passwords
            are managed in Keycloak.
          </p>
        </div>
        <button
          className="btn-primary"
          disabled={authLoading || authError}
          onClick={() => {
            setEditing(null);
            setForm(empty);
            setOpen(true);
          }}
        >
          Add access
        </button>
      </div>
      {isLoading ? (
        <Spinner />
      ) : isError ? (
        <p role="alert">Could not load staff access.</p>
      ) : (
        <div className="card overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left">
                <th className="p-4">User</th>
                <th>Roles</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t">
                  <td className="p-4">
                    {u.username}
                    {u.id === me?.id ? " (you)" : ""}
                  </td>
                  <td className="capitalize">{u.roles.join(", ")}</td>
                  <td className="space-x-3">
                    <button
                      disabled={!editable(u) || authLoading || authError}
                      className="text-brand-600 disabled:opacity-30"
                      onClick={() => {
                        setEditing(u);
                        setForm({
                          username: u.username,
                          password: "",
                          oidc_subject: u.oidc_subject ?? "",
                          roles: u.roles,
                        });
                        setOpen(true);
                      }}
                    >
                      Edit
                    </button>
                    <button
                      disabled={!editable(u)}
                      className="text-red-600 disabled:opacity-30"
                      onClick={() => setRemoving(u)}
                    >
                      Remove access
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={
          editing ? `Access for ${editing.username}` : "Grant property access"
        }
        size="sm"
      >
        <div className="space-y-4">
          {!editing && (
            <>
              <label className="label">
                Username
                <input
                  className="input"
                  value={form.username}
                  onChange={(e) =>
                    setForm({ ...form, username: e.target.value })
                  }
                />
              </label>
              <label className="label">
                {isSSO ? "Keycloak user ID" : "Password"}
                <input
                  className="input"
                  type={isSSO ? "text" : "password"}
                  value={isSSO ? form.oidc_subject : form.password}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      ...(isSSO
                        ? { oidc_subject: e.target.value }
                        : { password: e.target.value }),
                    })
                  }
                />
              </label>
              {isSSO && (
                <p className="text-xs text-gray-500">
                  Copy the immutable user ID from Keycloak. An identity already
                  in UNVRS can be added to this property.
                </p>
              )}
            </>
          )}
          {editing && isSSO && !editing.oidc_subject && (
            <label className="label">
              Link Keycloak user ID
              <input
                className="input"
                value={form.oidc_subject}
                onChange={(e) =>
                  setForm({ ...form, oidc_subject: e.target.value })
                }
              />
            </label>
          )}
          {editing && isSSO && editing.oidc_subject && (
            <p className="text-xs text-gray-500">
              Keycloak user ID: {editing.oidc_subject}. Remove and invite the
              correct identity to change the person.
            </p>
          )}
          {editing && !isSSO && (
            <label className="label">
              New password (optional)
              <input
                type="password"
                className="input"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </label>
          )}
          <fieldset>
            <legend className="label">Roles</legend>
            {grantable.map((role) => (
              <label
                key={role}
                className="flex items-center gap-2 py-1 capitalize"
              >
                <input
                  type="checkbox"
                  checked={form.roles.includes(role)}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      roles: e.target.checked
                        ? [...form.roles, role]
                        : form.roles.filter((r) => r !== role),
                    })
                  }
                />
                {role}
              </label>
            ))}
          </fieldset>
          <div className="flex justify-end gap-3">
            <button className="btn-secondary" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button
              className="btn-primary"
              disabled={
                save.isPending ||
                !form.roles.length ||
                (!editing &&
                  (!form.username ||
                    !(isSSO ? form.oidc_subject : form.password)))
              }
              onClick={() => save.mutate()}
            >
              Save access
            </button>
          </div>
        </div>
      </Modal>
      <ConfirmDialog
        open={!!removing}
        onClose={() => setRemoving(null)}
        onConfirm={() => remove.mutate()}
        loading={remove.isPending}
        title="Remove property access"
        message={`Remove ${removing?.username}'s access to this property? Their Keycloak account and other property memberships remain.`}
      />
    </div>
  );
}
