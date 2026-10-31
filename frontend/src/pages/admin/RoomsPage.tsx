import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Pencil,
  Trash2,
  BedDouble,
  QrCode,
  ImagePlus,
  Star,
  X,
  Users,
  Ruler,
  Loader2,
  Copy,
  Search,
} from "lucide-react";
import toast from "react-hot-toast";
import { format } from "date-fns";
import { clsx } from "clsx";

import {
  getRooms,
  createRoom,
  updateRoom,
  deleteRoom,
  getRoomQrUrl,
  getRoomImageUrl,
  uploadRoomImage,
  deleteRoomImage,
  setCoverImage,
} from "../../api/rooms";
import type { Room, RoomImage, RoomInput } from "../../api/types";
import Modal from "../../components/Modal";
import ConfirmDialog from "../../components/ConfirmDialog";
import Spinner from "../../components/Spinner";
import ErrorState from "../../components/ErrorState";
import { invalidateRoomViews } from "../../lib/queries";
import ViewToggle from "../../components/ViewToggle";
import { useViewMode } from "../../hooks/useViewMode";

const ROOM_TYPES = [
  "Single",
  "Double",
  "Twin",
  "Triple",
  "Suite",
  "Studio",
  "Apartment",
  "Family",
];

const AMENITIES = [
  "WiFi",
  "Air conditioning",
  "Heating",
  "TV",
  "Private bathroom",
  "Balcony",
  "Minibar",
  "Kitchen",
  "Coffee machine",
  "Safe",
  "Hair dryer",
  "Desk",
  "Parking",
  "Breakfast",
];

type FormData = {
  name: string;
  homeassistant_entity_id: string;
  room_type: string;
  size_sqm: string;
  max_occupancy: string;
  price_per_night: string;
  floor: string;
  beds: string;
  view: string;
  amenities: string[];
  smoking: boolean;
  description: string;
};

const empty: FormData = {
  name: "",
  homeassistant_entity_id: "",
  room_type: "",
  size_sqm: "",
  max_occupancy: "",
  price_per_night: "",
  floor: "",
  beds: "",
  view: "",
  amenities: [],
  smoking: false,
  description: "",
};

const toForm = (r: Room): FormData => ({
  name: r.name,
  homeassistant_entity_id: r.homeassistant_entity_id ?? "",
  room_type: r.room_type ?? "",
  size_sqm: r.size_sqm?.toString() ?? "",
  max_occupancy: r.max_occupancy?.toString() ?? "",
  price_per_night: r.price_per_night?.toString() ?? "",
  floor: r.floor?.toString() ?? "",
  beds: r.beds ?? "",
  view: r.view ?? "",
  amenities: r.amenities ?? [],
  smoking: r.smoking,
  description: r.description ?? "",
});

const num = (s: string) => (s.trim() === "" ? null : Number(s));

export default function RoomsPage() {
  const qc = useQueryClient();
  const { data: rooms = [], isLoading, isError, error, refetch } = useQuery({
    queryKey: ["rooms"],
    queryFn: getRooms,
  });

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Room | null>(null);
  const [form, setForm] = useState<FormData>(empty);
  const [images, setImages] = useState<RoomImage[]>([]);
  const [uploading, setUploading] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Room | null>(null);
  const [qrRoom, setQrRoom] = useState<Room | null>(null);
  const [view, setView] = useViewMode("rooms");
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const openCreate = () => {
    setEditing(null);
    setForm(empty);
    setImages([]);
    setModalOpen(true);
  };

  const openEdit = (r: Room) => {
    setEditing(r);
    setForm(toForm(r));
    setImages(r.images ?? []);
    setModalOpen(true);
  };

  // Duplicate: prefill the create form from an existing room (new name, no photos).
  const openDuplicate = (r: Room) => {
    setEditing(null);
    setForm({ ...toForm(r), name: `${r.name} (copy)`, homeassistant_entity_id: "" });
    setImages([]);
    setModalOpen(true);
  };

  const presentTypes = Array.from(
    new Set(rooms.map((r) => r.room_type).filter(Boolean))
  ) as string[];

  const q = search.trim().toLowerCase();
  const filtered = rooms.filter((r) => {
    const matchesType = !typeFilter || r.room_type === typeFilter;
    const matchesSearch =
      !q ||
      r.name.toLowerCase().includes(q) ||
      (r.room_type ?? "").toLowerCase().includes(q) ||
      (r.view ?? "").toLowerCase().includes(q);
    return matchesType && matchesSearch;
  });

  const payload = (): RoomInput => ({
    name: form.name,
    homeassistant_entity_id: form.homeassistant_entity_id.trim() || null,
    description: form.description || null,
    room_type: form.room_type || null,
    size_sqm: num(form.size_sqm),
    max_occupancy: num(form.max_occupancy),
    price_per_night: num(form.price_per_night),
    floor: num(form.floor),
    beds: form.beds || null,
    view: form.view || null,
    amenities: form.amenities,
    smoking: form.smoking,
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      editing ? updateRoom(editing.id, payload()) : createRoom(payload()),
    onSuccess: (room) => {
      invalidateRoomViews(qc);
      if (editing) {
        toast.success("Room updated");
        setModalOpen(false);
      } else {
        // Keep the modal open in edit mode so photos can be added now.
        toast.success("Room created — add photos below");
        setEditing(room);
        setImages(room.images ?? []);
      }
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteRoom(deleteTarget!.id),
    onSuccess: () => {
      invalidateRoomViews(qc);
      toast.success("Room deleted");
      setDeleteTarget(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const onFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!editing) return;
    const files = Array.from(e.target.files ?? []);
    setUploading(true);
    for (const f of files) {
      try {
        const img = await uploadRoomImage(editing.id, f);
        setImages((prev) => [...prev, img]);
      } catch (err) {
        toast.error((err as Error).message);
      }
    }
    setUploading(false);
    invalidateRoomViews(qc);
    e.target.value = "";
  };

  const removeImage = async (imageId: number) => {
    if (!editing) return;
    try {
      await deleteRoomImage(editing.id, imageId);
      setImages((prev) => prev.filter((i) => i.id !== imageId));
      invalidateRoomViews(qc);
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const makeCover = async (imageId: number) => {
    if (!editing) return;
    try {
      await setCoverImage(editing.id, imageId);
      setImages((prev) => prev.map((i) => ({ ...i, is_cover: i.id === imageId })));
      invalidateRoomViews(qc);
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const toggleAmenity = (a: string) =>
    setForm((f) => ({
      ...f,
      amenities: f.amenities.includes(a)
        ? f.amenities.filter((x) => x !== a)
        : [...f.amenities, a],
    }));

  const coverOf = (r: Room) => r.images.find((i) => i.is_cover) ?? r.images[0];

  const roomActions = (r: Room) => (
    <div className="flex gap-1 flex-shrink-0">
      <button
        className="p-1.5 rounded-lg text-gray-400 hover:text-brand-600 hover:bg-brand-50 transition-colors"
        onClick={() => setQrRoom(r)}
        title="View QR code"
      >
        <QrCode size={15} />
      </button>
      <button
        className="p-1.5 rounded-lg text-gray-400 hover:text-brand-600 hover:bg-brand-50 transition-colors"
        onClick={() => openDuplicate(r)}
        title="Duplicate room"
      >
        <Copy size={15} />
      </button>
      <button
        className="p-1.5 rounded-lg text-gray-400 hover:text-brand-600 hover:bg-brand-50 transition-colors"
        onClick={() => openEdit(r)}
        title="Edit room"
      >
        <Pencil size={15} />
      </button>
      <button
        className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
        onClick={() => setDeleteTarget(r)}
        title="Delete room"
      >
        <Trash2 size={15} />
      </button>
    </div>
  );

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Rooms</h1>
          <p className="text-sm text-gray-500 mt-1">
            {filtered.length} of {rooms.length}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search
              size={15}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400"
            />
            <input
              className="input pl-8 py-1.5 w-44"
              placeholder="Search rooms…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select
            className="input py-1.5 w-36"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option value="">All types</option>
            {presentTypes.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <ViewToggle value={view} onChange={setView} />
          <button className="btn-primary" onClick={openCreate}>
            <Plus size={16} /> Add room
          </button>
        </div>
      </div>

      {isError ? (
        <ErrorState what="rooms" error={error} onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="flex justify-center py-20">
          <Spinner size={32} />
        </div>
      ) : rooms.length === 0 ? (
        <div className="card p-12 text-center text-gray-400">
          <BedDouble size={40} className="mx-auto mb-3 opacity-40" />
          <p>No rooms yet.</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="card p-12 text-center text-gray-400">
          <Search size={40} className="mx-auto mb-3 opacity-40" />
          <p>No rooms match your filters.</p>
        </div>
      ) : view === "cards" ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((r) => {
            const cover = coverOf(r);
            return (
              <div key={r.id} className="card overflow-hidden flex flex-col">
                <div className="relative h-40 bg-gray-100">
                  {cover ? (
                    <img
                      src={getRoomImageUrl(r.id, cover.id, 400)}
                      loading="lazy"
                      alt={r.name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-gray-300">
                      <BedDouble size={32} />
                    </div>
                  )}
                  {r.images.length > 1 && (
                    <span className="absolute bottom-2 right-2 text-xs bg-black/60 text-white px-1.5 py-0.5 rounded">
                      {r.images.length} photos
                    </span>
                  )}
                  {r.price_per_night != null && (
                    <span className="absolute top-2 left-2 text-xs font-semibold bg-white/90 text-gray-900 px-2 py-1 rounded-lg shadow-sm">
                      {r.price_per_night} RON / night
                    </span>
                  )}
                </div>

                <div className="p-4 flex flex-col gap-2 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="font-semibold text-gray-900">{r.name}</h3>
                      {r.room_type && (
                        <p className="text-xs text-brand-600">{r.room_type}</p>
                      )}
                    </div>
                    {roomActions(r)}
                  </div>

                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
                    {r.size_sqm != null && (
                      <span className="inline-flex items-center gap-1">
                        <Ruler size={13} /> {r.size_sqm} m²
                      </span>
                    )}
                    {r.max_occupancy != null && (
                      <span className="inline-flex items-center gap-1">
                        <Users size={13} /> {r.max_occupancy}
                      </span>
                    )}
                    {r.beds && <span>{r.beds}</span>}
                  </div>

                  {r.amenities.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {r.amenities.slice(0, 3).map((a) => (
                        <span
                          key={a}
                          className="text-[11px] bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded"
                        >
                          {a}
                        </span>
                      ))}
                      {r.amenities.length > 3 && (
                        <span className="text-[11px] text-gray-400">
                          +{r.amenities.length - 3}
                        </span>
                      )}
                    </div>
                  )}

                  {r.description && (
                    <p className="text-sm text-gray-500 line-clamp-2 mt-1">
                      {r.description}
                    </p>
                  )}

                  <p className="text-[11px] text-gray-300 mt-auto pt-1">
                    Created {format(new Date(r.created_at), "dd MMM yyyy")}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-100">
            <thead className="bg-gray-50">
              <tr>
                {["Room", "Type", "Size", "Guests", "Price", "Floor", ""].map((h) => (
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
              {filtered.map((r) => {
                const cover = coverOf(r);
                return (
                  <tr key={r.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-gray-100 overflow-hidden flex-shrink-0 flex items-center justify-center text-gray-300">
                          {cover ? (
                            <img
                              src={getRoomImageUrl(r.id, cover.id, 400)}
                              alt={r.name}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <BedDouble size={16} />
                          )}
                        </div>
                        <span className="font-medium text-gray-900">{r.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {r.room_type ?? "—"}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {r.size_sqm != null ? `${r.size_sqm} m²` : "—"}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {r.max_occupancy ?? "—"}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {r.price_per_night != null ? `${r.price_per_night} RON` : "—"}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {r.floor ?? "—"}
                    </td>
                    <td className="px-4 py-2 text-right">{roomActions(r)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Create / Edit modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? `Edit room — ${editing.name}` : "Add room"}
        size="lg"
      >
        <div>
          <div className="space-y-4 max-h-[65vh] overflow-y-auto pr-1">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Room name *</label>
                <input
                  className="input"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Suite 101"
                />
              </div>
              <div>
                <label className="label">Room type</label>
                <select
                  className="input"
                  value={form.room_type}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, room_type: e.target.value }))
                  }
                >
                  <option value="">Select type…</option>
                  {ROOM_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <label className="label">Size (m²)</label>
                <input
                  type="number"
                  step="1"
                  min="0"
                  className="input"
                  value={form.size_sqm}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, size_sqm: e.target.value }))
                  }
                />
              </div>
              <div>
                <label className="label">Max guests</label>
                <input
                  type="number"
                  step="1"
                  min="0"
                  className="input"
                  value={form.max_occupancy}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, max_occupancy: e.target.value }))
                  }
                />
              </div>
              <div>
                <label className="label">Price/night</label>
                <input
                  type="number"
                  step="1"
                  min="0"
                  className="input"
                  value={form.price_per_night}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, price_per_night: e.target.value }))
                  }
                  placeholder="RON"
                />
              </div>
              <div>
                <label className="label">Floor</label>
                <input
                  type="number"
                  step="1"
                  className="input"
                  value={form.floor}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, floor: e.target.value }))
                  }
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Beds</label>
                <input
                  className="input"
                  value={form.beds}
                  onChange={(e) => setForm((f) => ({ ...f, beds: e.target.value }))}
                  placeholder="e.g. 1 double bed"
                />
              </div>
              <div>
                <label className="label">View</label>
                <input
                  className="input"
                  value={form.view}
                  onChange={(e) => setForm((f) => ({ ...f, view: e.target.value }))}
                  placeholder="e.g. Sea view"
                />
              </div>
            </div>

            <div>
              <label className="label">Amenities</label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                {AMENITIES.map((a) => (
                  <label
                    key={a}
                    className={clsx(
                      "flex items-center gap-2 px-2.5 py-1.5 rounded-lg border cursor-pointer text-sm transition-colors",
                      form.amenities.includes(a)
                        ? "border-brand-500 bg-brand-50 text-brand-700"
                        : "border-gray-200 text-gray-600 hover:bg-gray-50"
                    )}
                  >
                    <input
                      type="checkbox"
                      className="accent-brand-600"
                      checked={form.amenities.includes(a)}
                      onChange={() => toggleAmenity(a)}
                    />
                    {a}
                  </label>
                ))}
              </div>
            </div>

            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                className="accent-brand-600"
                checked={form.smoking}
                onChange={(e) =>
                  setForm((f) => ({ ...f, smoking: e.target.checked }))
                }
              />
              Smoking allowed
            </label>

            <div className="sm:col-span-2">
              <label className="label" htmlFor="room-ha-entity">Home Assistant entity ID</label>
              <input id="room-ha-entity" className="input" value={form.homeassistant_entity_id}
                onChange={(e) => setForm((f) => ({ ...f, homeassistant_entity_id: e.target.value }))}
                placeholder="lock.room_101" autoCapitalize="none" spellCheck={false} />
              <p className="text-xs text-gray-400 mt-1">The lock for this room, for example lock.room_101. Existing door scripts such as script.open_door are also supported. Blank disables door control.</p>
            </div>
            <div>
              <label className="label">Description</label>
              <textarea
                className="input resize-none"
                rows={3}
                value={form.description}
                onChange={(e) =>
                  setForm((f) => ({ ...f, description: e.target.value }))
                }
                placeholder="Optional description…"
              />
            </div>

            {/* Photos */}
            <div>
              <label className="label">Photos</label>
              {editing ? (
                <>
                  <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 mb-2">
                    {images.map((img) => (
                      <div
                        key={img.id}
                        className="relative group aspect-square rounded-lg overflow-hidden border border-gray-100"
                      >
                        <img
                          src={getRoomImageUrl(editing.id, img.id, 200)}
                          loading="lazy"
                          alt=""
                          className="w-full h-full object-cover"
                        />
                        <button
                          onClick={() => makeCover(img.id)}
                          title={img.is_cover ? "Cover photo" : "Set as cover"}
                          className={clsx(
                            "absolute top-1 left-1 p-1 rounded-md transition-colors",
                            img.is_cover
                              ? "bg-brand-600 text-white"
                              : "bg-black/40 text-white opacity-0 group-hover:opacity-100 hover:bg-black/60"
                          )}
                        >
                          <Star
                            size={12}
                            fill={img.is_cover ? "currentColor" : "none"}
                          />
                        </button>
                        <button
                          onClick={() => removeImage(img.id)}
                          title="Remove photo"
                          className="absolute top-1 right-1 p-1 rounded-md bg-black/40 text-white opacity-0 group-hover:opacity-100 hover:bg-red-600 transition-colors"
                        >
                          <X size={12} />
                        </button>
                      </div>
                    ))}
                    <button
                      onClick={() => fileRef.current?.click()}
                      className="aspect-square rounded-lg border-2 border-dashed border-gray-200 text-gray-400 hover:border-brand-400 hover:text-brand-500 flex flex-col items-center justify-center gap-1 transition-colors"
                    >
                      {uploading ? (
                        <Loader2 size={18} className="animate-spin" />
                      ) : (
                        <ImagePlus size={18} />
                      )}
                      <span className="text-[11px]">Add</span>
                    </button>
                  </div>
                  <input
                    ref={fileRef}
                    type="file"
                    accept="image/*"
                    multiple
                    hidden
                    onChange={onFiles}
                  />
                  <p className="text-xs text-gray-400">
                    Click the star to set the cover photo.
                  </p>
                </>
              ) : (
                <p className="text-xs text-gray-400">
                  Save the room first, then you can upload photos.
                </p>
              )}
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 mt-4 border-t border-gray-100">
            <button className="btn-secondary" onClick={() => setModalOpen(false)}>
              {editing ? "Done" : "Cancel"}
            </button>
            <button
              className="btn-primary"
              onClick={() => saveMutation.mutate()}
              disabled={!form.name || saveMutation.isPending}
            >
              {saveMutation.isPending
                ? "Saving…"
                : editing
                ? "Save changes"
                : "Create room"}
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
