import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Users,
  Ruler,
  BedDouble,
  Layers,
  Eye,
  Cigarette,
  Ban,
  CalendarPlus,
  ImageOff,
} from "lucide-react";
import { format } from "date-fns";

import { getRoom, getRoomImageUrl, getRoomQrUrl } from "../api/rooms";
import { getAssignments } from "../api/assignments";
import type { Assignment } from "../api/types";
import { ROOM_STATUS } from "../lib/roomStatus";
import Spinner from "../components/Spinner";

const bookingStatus = (b: Assignment, now: Date) => {
  const ended = b.check_out ? new Date(b.check_out) < now : false;
  if (b.checked_in_at) return ended ? "checked_out" : "checked_in";
  return ended ? "expired" : "booked";
};

function Fact({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Users;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-9 h-9 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center flex-shrink-0">
        <Icon size={18} />
      </div>
      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-wide text-gray-400">{label}</p>
        <p className="text-sm font-medium text-gray-800">{value}</p>
      </div>
    </div>
  );
}

export default function RoomViewPage() {
  const { roomId } = useParams();
  const id = Number(roomId);
  const nav = useNavigate();
  const now = new Date();

  const { data: room, isLoading } = useQuery({
    queryKey: ["room", id],
    queryFn: () => getRoom(id),
    enabled: Number.isFinite(id),
  });
  const { data: bookings = [] } = useQuery({
    queryKey: ["assignments"],
    queryFn: getAssignments,
  });

  const [active, setActive] = useState(0);

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner size={32} />
      </div>
    );
  }
  if (!room) {
    return (
      <div className="p-8 text-center text-gray-400">
        <p>Room not found.</p>
        <button className="btn-secondary mt-4" onClick={() => nav(-1)}>
          Go back
        </button>
      </div>
    );
  }

  // Cover first, then the rest.
  const images = [...room.images].sort(
    (a, b) => Number(b.is_cover) - Number(a.is_cover)
  );
  const activeImg = images[Math.min(active, images.length - 1)];

  const roomBookings = bookings
    .filter((b) => b.room_id === id && b.check_in && b.check_out)
    .sort((a, b) => +new Date(a.check_in!) - +new Date(b.check_in!));

  const facts: { icon: typeof Users; label: string; value: string }[] = [];
  if (room.max_occupancy) facts.push({ icon: Users, label: "Sleeps", value: `${room.max_occupancy}` });
  if (room.beds) facts.push({ icon: BedDouble, label: "Beds", value: room.beds });
  if (room.size_sqm) facts.push({ icon: Ruler, label: "Size", value: `${room.size_sqm} m²` });
  if (room.floor != null)
    facts.push({ icon: Layers, label: "Floor", value: room.floor === 0 ? "Ground" : `${room.floor}` });
  if (room.view) facts.push({ icon: Eye, label: "View", value: room.view });
  facts.push({
    icon: room.smoking ? Cigarette : Ban,
    label: "Smoking",
    value: room.smoking ? "Allowed" : "Non-smoking",
  });

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-5xl">
      <button
        onClick={() => nav(-1)}
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 mb-4"
      >
        <ArrowLeft size={16} /> Back
      </button>

      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{room.name}</h1>
          <p className="text-sm text-gray-500 mt-1">
            {room.room_type || "Room"}
            {room.price_per_night != null && (
              <>
                {" · "}
                <span className="font-semibold text-gray-700">
                  {room.price_per_night} RON
                </span>{" "}
                / night
              </>
            )}
          </p>
        </div>
        <button
          className="btn-primary"
          onClick={() => nav(`/app/booking?room_id=${room.id}`)}
        >
          <CalendarPlus size={16} /> New booking
        </button>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Gallery */}
        <div className="lg:col-span-2">
          <div className="aspect-[16/10] rounded-xl overflow-hidden bg-gray-100 flex items-center justify-center">
            {activeImg ? (
              <img
                src={getRoomImageUrl(room.id, activeImg.id)}
                alt={room.name}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="text-gray-300 flex flex-col items-center">
                <ImageOff size={40} />
                <span className="text-sm mt-2">No photos</span>
              </div>
            )}
          </div>
          {images.length > 1 && (
            <div className="flex gap-2 mt-3 overflow-x-auto pb-1">
              {images.map((img, i) => (
                <button
                  key={img.id}
                  onClick={() => setActive(i)}
                  className={
                    "flex-shrink-0 w-24 h-16 rounded-lg overflow-hidden border-2 transition-colors " +
                    (i === active ? "border-brand-500" : "border-transparent opacity-70 hover:opacity-100")
                  }
                >
                  <img
                    src={getRoomImageUrl(room.id, img.id, 200)}
                    loading="lazy"
                    alt=""
                    className="w-full h-full object-cover"
                  />
                </button>
              ))}
            </div>
          )}

          {room.description && (
            <div className="mt-6">
              <h2 className="text-sm font-semibold text-gray-900 mb-2">About this room</h2>
              <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-line">
                {room.description}
              </p>
            </div>
          )}
        </div>

        {/* Details */}
        <div className="space-y-6">
          <div className="card p-5 grid grid-cols-2 gap-4">
            {facts.map((f) => (
              <Fact key={f.label} icon={f.icon} label={f.label} value={f.value} />
            ))}
          </div>

          {room.amenities.length > 0 && (
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-gray-900 mb-3">Amenities</h2>
              <div className="flex flex-wrap gap-2">
                {room.amenities.map((a) => (
                  <span
                    key={a}
                    className="px-2.5 py-1 rounded-full bg-gray-100 text-gray-700 text-xs"
                  >
                    {a}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Door QR</h2>
            <div className="flex items-center gap-4">
              <img
                src={getRoomQrUrl(room.id)}
                alt="Door QR"
                className="w-24 h-24 rounded-lg border border-gray-100"
              />
              <p className="text-xs text-gray-500">
                This room's <span className="font-medium text-gray-700">permanent</span> door
                code — print it and fix it to the door. Guests scan it and enter their own{" "}
                <span className="font-medium text-gray-700">booking PIN</span> (issued per stay,
                expires at checkout).
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Bookings for this room */}
      <div className="mt-8">
        <h2 className="text-sm font-semibold text-gray-900 mb-3">Bookings</h2>
        {roomBookings.length === 0 ? (
          <p className="text-sm text-gray-400">No dated bookings for this room.</p>
        ) : (
          <div className="card divide-y divide-gray-100">
            {roomBookings.map((b) => {
              const s = bookingStatus(b, now);
              const color = s === "expired" ? "#94a3b8" : ROOM_STATUS[s].hex;
              const label =
                s === "expired" ? "No-show" : ROOM_STATUS[s as keyof typeof ROOM_STATUS].full;
              return (
                <Link
                  key={b.id}
                  to="/app/calendar"
                  className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition-colors"
                >
                  <span
                    className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: color }}
                  />
                  <span className="text-sm font-medium text-gray-800">
                    {b.guest ? `${b.guest.firstname} ${b.guest.lastname}` : `Guest #${b.guest_id}`}
                  </span>
                  <span className="text-sm text-gray-400">
                    {format(new Date(b.check_in!), "dd MMM")} → {format(new Date(b.check_out!), "dd MMM")}
                  </span>
                  <span className="ml-auto text-xs font-medium" style={{ color }}>
                    {label}
                  </span>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
