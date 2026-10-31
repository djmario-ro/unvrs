import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { CheckCircle, Delete, DoorOpen, Hotel, LockKeyhole } from "lucide-react";
import { clsx } from "clsx";
import { forgetDoorSession, getDoorSession, unlockDoor, validatePin } from "../../api/door";
import type { GuestDoorSession } from "../../api/door";

const DIGITS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "⌫"];

export default function DoorPage() {
  const { roomHash = "" } = useParams<{ roomHash: string }>();
  const [session, setSession] = useState<GuestDoorSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const pending = useRef(false);
  const resetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setSession(null);
    setPin("");
    setError("");
    setSuccess(false);
    getDoorSession(roomHash).then((value) => { if (alive) setSession(value); })
      .catch(() => { /* A missing/revoked session returns to PIN activation. */ })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; if (resetTimer.current) clearTimeout(resetTimer.current); };
  }, [roomHash]);

  const digit = async (value: string) => {
    if (pending.current) return;
    setError("");
    if (value === "⌫") { setPin((p) => p.slice(0, -1)); return; }
    if (!value || pin.length >= 6) return;
    const next = pin + value;
    setPin(next);
    if (next.length !== 6) return;
    pending.current = true;
    setBusy(true);
    try {
      const activated = await validatePin(roomHash, next);
      setSession(activated);
      setPin("");
    } catch (e) {
      setError((e as Error).message);
      setPin("");
    } finally { pending.current = false; setBusy(false); }
  };

  const open = async () => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    setSuccess(false);
    try {
      await unlockDoor(roomHash);
      setSuccess(true);
      resetTimer.current = setTimeout(() => setSuccess(false), 6000);
    } catch (e) {
      setError((e as Error).message);
      // Expiry/revocation is rechecked by the server, including mid-stay changes.
      try { setSession(await getDoorSession(roomHash)); } catch { setSession(null); }
    } finally { pending.current = false; setBusy(false); }
  };

  const forget = async () => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    try { await forgetDoorSession(roomHash); setSession(null); setPin(""); setSuccess(false); setError(""); }
    catch (e) { setError((e as Error).message); }
    finally { pending.current = false; setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white flex flex-col items-center justify-center px-6 py-12">
      <div className="flex items-center gap-2 text-slate-400 text-sm tracking-widest uppercase mb-12">
        <Hotel size={18} /> Retreat 480
      </div>
      <main className="w-full max-w-sm flex flex-col items-center gap-7 text-center">
        {loading ? <p role="status" className="text-slate-300">Checking your guest key…</p> : session ? (
          <>
            {success ? <CheckCircle size={64} className="text-emerald-400" /> : <DoorOpen size={64} className="text-emerald-300" />}
            <div>
              <p className="text-slate-400 text-sm mb-2">Your guest key</p>
              <h1 className="text-3xl font-semibold">Room {session.room}</h1>
              <p className="text-slate-300 mt-3">Welcome, {session.guest}</p>
            </div>
            <p role="status" aria-live="polite" className="text-emerald-300 min-h-6">
              {busy ? "Opening door…" : success ? "Door unlock triggered" : "Slide when you are ready to enter"}
            </p>
            <UnlockSlider disabled={busy || success} onUnlock={open} />
            <p className="text-xs text-slate-400">This phone remembers your key for your stay.</p>
            <button className="text-sm text-slate-400 underline underline-offset-4 disabled:opacity-40" onClick={forget} disabled={busy}>
              Forget this device
            </button>
          </>
        ) : (
          <>
            <LockKeyhole size={56} className="text-emerald-300" />
            <div><h1 className="text-2xl font-semibold">Activate your guest key</h1>
              <p className="text-slate-400 mt-3">Enter your stay PIN once on this phone.<br />Then slide to unlock during your stay.</p></div>
            <div className="flex gap-4" aria-label={`${pin.length} of 6 PIN digits entered`}>
              {Array.from({ length: 6 }, (_, i) => <span key={i} className={clsx("w-3 h-3 rounded-full", i < pin.length ? "bg-emerald-300" : "bg-slate-700")} />)}
            </div>
            <div className="grid grid-cols-3 gap-3 w-full max-w-xs">
              {DIGITS.map((d, i) => <button key={i} aria-label={d === "⌫" ? "Delete digit" : d || "Spacer"}
                disabled={!d || busy} onClick={() => void digit(d)}
                className={clsx("h-16 rounded-2xl text-xl bg-slate-800 hover:bg-slate-700 active:scale-95 disabled:opacity-40", !d && "invisible")}>
                {d === "⌫" ? <Delete size={22} className="mx-auto" /> : d}
              </button>)}
            </div>
            {busy && <p role="status" className="text-slate-300">Activating this device…</p>}
          </>
        )}
        {error && <p role="alert" className="text-red-300 text-sm">{error}</p>}
      </main>
    </div>
  );
}

function UnlockSlider({ disabled, onUnlock }: { disabled: boolean; onUnlock: () => Promise<void> }) {
  const [position, setPosition] = useState(0);
  const dragging = useRef<{ start: number; travel: number } | null>(null);
  const submitting = useRef(false);
  const finish = async (value: number) => {
    setPosition(0);
    if (value < 95 || disabled || submitting.current) return;
    submitting.current = true;
    try { await onUnlock(); } finally { submitting.current = false; }
  };
  return <div className="relative w-full rounded-full bg-slate-800 h-16 flex items-center justify-center">
    <span aria-hidden="true" className="pointer-events-none text-sm text-slate-300 pl-8">Slide to unlock →</span>
    <input type="range" min="0" max="100" step="1" value={position} disabled={disabled}
      aria-label="Slide to unlock door" className="door-slider absolute inset-0 w-full"
      onChange={(e) => setPosition(Number(e.target.value))}
      onPointerDown={(e) => {
        // Only grabbing the handle starts a gesture; tapping the track cannot open a door.
        if (disabled || e.clientX > e.currentTarget.getBoundingClientRect().left + 60) { e.preventDefault(); return; }
        e.preventDefault();
        dragging.current = { start: e.clientX, travel: Math.max(1, e.currentTarget.getBoundingClientRect().width - 64) };
        e.currentTarget.setPointerCapture(e.pointerId);
      }}
      onPointerMove={(e) => {
        if (dragging.current) setPosition(Math.max(0, Math.min(100, (e.clientX - dragging.current.start) / dragging.current.travel * 100)));
      }}
      onPointerUp={(e) => {
        const gesture = dragging.current;
        dragging.current = null;
        if (gesture) void finish((e.clientX - gesture.start) / gesture.travel * 100);
        else setPosition(0);
      }}
      onPointerCancel={() => { dragging.current = null; setPosition(0); }}
      onBlur={() => { dragging.current = null; setPosition(0); }}
      onKeyUp={(e) => { if (["ArrowRight", "End"].includes(e.key) && Number(e.currentTarget.value) >= 95) void finish(Number(e.currentTarget.value)); }}
    />
  </div>;
}
