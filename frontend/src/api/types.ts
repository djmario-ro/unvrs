export interface Guest {
  id: number;
  firstname: string;
  lastname: string;
  email: string | null;
  phone: string | null;
  address: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface RoomImage {
  id: number;
  is_cover: boolean;
  content_type: string;
  created_at: string;
}

export interface Room {
  id: number;
  public_id: string;
  homeassistant_entity_id: string | null;
  name: string;
  description: string | null;
  room_type: string | null;
  size_sqm: number | null;
  max_occupancy: number | null;
  beds: string | null;
  price_per_night: number | null;
  floor: number | null;
  view: string | null;
  amenities: string[];
  smoking: boolean;
  created_at: string;
  images: RoomImage[];
}

export type RoomInput = Omit<
  Room,
  "id" | "public_id" | "created_at" | "images"
>;

export interface Assignment {
  id: number;
  guest_id: number;
  room_id: number;
  pin: string;
  check_in: string | null;
  check_out: string | null;
  checked_in_at: string | null;
  access_revoked_at: string | null;
  created_at: string;
  guest: Guest | null;
  room: Room | null;
}

export interface AuditEntry {
  id: number;
  operation: string;
  message: string;
  /** Staff username; null for door/system events. */
  actor: string | null;
  ip: string | null;
  created_at: string;
}

export interface DoorAccessResult {
  message: string;
  guest: string;
  room: string;
}

export type Role = "admin" | "frontdesk";

export interface User {
  id: number;
  username: string;
  role: string;
  created_at: string;
}

export type RoomStatus = "available" | "booked" | "checked_in" | "checked_out";

export interface FloorRoom {
  id: number;
  name: string;
  room_type: string | null;
  status: RoomStatus;
  occupied: boolean;
  guest: string | null;
}

export interface Floor {
  floor: number;
  total: number;
  available: number;
  rooms: FloorRoom[];
}

export interface DashboardFloors {
  floors: Floor[];
  totals: {
    total: number;
    available: number;
    booked: number;
    occupied: number;
    cleaning: number;
  };
}

export type Channel = "sms" | "whatsapp";

export interface MessageLog {
  id: number;
  assignment_id: number;
  channel: string;
  recipient: string;
  status: string;
  error: string | null;
  created_at: string;
}

export interface SendPinResult {
  results: MessageLog[];
}

export interface WhatsAppStatus {
  connected: boolean;
  number: string | null;
}

export interface WhatsAppQr {
  qr: string | null;
}
