import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import api from "../api/client";
import Spinner from "../components/Spinner";
interface Room {
  id: number;
  name: string;
  floor: number | null;
  status: string;
  cleaned_at: string | null;
}
interface Ticket {
  id: number;
  room_id: number;
  title: string;
  description: string;
  status: "open" | "in_progress" | "resolved";
}
export default function OperationsPage({
  mode,
}: {
  mode: "housekeeping" | "maintenance";
}) {
  const qc = useQueryClient();
  const housekeeping = mode === "housekeeping";
  const {
    data: rooms = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["operations", mode, "rooms"],
    queryFn: () =>
      api
        .get<Room[]>(
          housekeeping
            ? "/operations/housekeeping"
            : "/operations/maintenance/rooms",
        )
        .then((r) => r.data),
  });
  const { data: tickets = [], isError: ticketError } = useQuery({
    queryKey: ["maintenance"],
    queryFn: () =>
      api.get<Ticket[]>("/operations/maintenance").then((r) => r.data),
    enabled: !housekeeping,
  });
  const [room, setRoom] = useState(""),
    [title, setTitle] = useState(""),
    [description, setDescription] = useState("");
  const cleaned = useMutation({
    mutationFn: (id: number) =>
      api.post(`/operations/housekeeping/${id}/cleaned`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["operations"] });
      toast.success("Room marked clean");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const create = useMutation({
    mutationFn: () =>
      api.post("/operations/maintenance", {
        room_id: Number(room),
        title,
        description,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["maintenance"] });
      setTitle("");
      setDescription("");
      toast.success("Issue reported");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const update = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      api.patch(`/operations/maintenance/${id}`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["maintenance"] }),
    onError: (e: Error) => toast.error(e.message),
  });
  return (
    <div className="p-4 sm:p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold capitalize">{mode}</h1>
        <p className="text-sm text-gray-500">
          {housekeeping
            ? "Room status and cleaning confirmations"
            : "Report issues and track repairs"}
        </p>
      </div>
      {isLoading ? (
        <Spinner />
      ) : isError ? (
        <p role="alert">Could not load rooms.</p>
      ) : (
        <div className="card overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left">
                <th className="p-4">Room</th>
                <th>Floor</th>
                <th>Status</th>
                {housekeeping && <th>Cleaning</th>}
              </tr>
            </thead>
            <tbody>
              {rooms.map((r) => (
                <tr key={r.id} className="border-t">
                  <td className="p-4 font-medium">{r.name}</td>
                  <td>{r.floor ?? "—"}</td>
                  <td className="capitalize">{r.status.replace(/_/g, " ")}</td>
                  {housekeeping && (
                    <td>
                      <button
                        className="btn-secondary my-2"
                        disabled={cleaned.isPending}
                        onClick={() => {
                          if (
                            window.confirm(
                              `Confirm room ${r.name} has been cleaned?`,
                            )
                          )
                            cleaned.mutate(r.id);
                        }}
                      >
                        Mark clean
                      </button>
                      {r.cleaned_at && (
                        <p className="text-xs text-gray-500 mb-2">
                          Last confirmed:{" "}
                          {new Date(r.cleaned_at).toLocaleString()}
                        </p>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <form
        className="card p-5 space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <h2 className="font-semibold">Report a maintenance issue</h2>
        <label className="label">
          Room
          <select
            className="input"
            required
            value={room}
            onChange={(e) => setRoom(e.target.value)}
          >
            <option value="">Choose a room</option>
            {rooms.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
        </label>
        <label className="label">
          Issue
          <input
            className="input"
            required
            maxLength={160}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label className="label">
          Details
          <textarea
            className="input"
            maxLength={4000}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <button
          className="btn-primary"
          disabled={create.isPending || !room || !title}
        >
          Report issue
        </button>
      </form>
      {!housekeeping && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Maintenance tickets</h2>
          {ticketError ? (
            <p role="alert">Could not load tickets.</p>
          ) : !tickets.length ? (
            <p className="text-sm text-gray-500">No issues reported.</p>
          ) : (
            tickets.map((t) => (
              <article className="card p-5" key={t.id}>
                <div className="flex justify-between items-center gap-4">
                  <div>
                    <h3 className="font-semibold">
                      {rooms.find((r) => r.id === t.room_id)?.name ?? "Room"}:{" "}
                      {t.title}
                    </h3>
                    <p className="text-sm whitespace-pre-wrap mt-2">
                      {t.description}
                    </p>
                  </div>
                  <label className="text-sm">
                    Status
                    <select
                      aria-label={`Status for ${t.title}`}
                      className="input"
                      value={t.status}
                      disabled={update.isPending}
                      onChange={(e) =>
                        update.mutate({ id: t.id, status: e.target.value })
                      }
                    >
                      <option value="open">Open</option>
                      <option value="in_progress">In progress</option>
                      <option value="resolved">Resolved</option>
                    </select>
                  </label>
                </div>
              </article>
            ))
          )}
        </div>
      )}
    </div>
  );
}
