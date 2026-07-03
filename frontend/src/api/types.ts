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

export interface Room {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
}

export interface Assignment {
  id: number;
  guest_id: number;
  room_id: number;
  pin: string;
  check_in: string | null;
  check_out: string | null;
  created_at: string;
  guest: Guest | null;
  room: Room | null;
}

export interface AuditEntry {
  id: number;
  operation: string;
  message: string;
  created_at: string;
}

export interface DoorAccessResult {
  message: string;
  guest: string;
  room: string;
  valid_until: string;
}
