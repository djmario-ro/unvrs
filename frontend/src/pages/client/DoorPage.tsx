import { useState, useRef, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { DoorOpen, Delete, CheckCircle, XCircle, Hotel } from "lucide-react";
import { clsx } from "clsx";
import { validatePin } from "../../api/door";
import type { DoorAccessResult } from "../../api/types";

const DIGITS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "⌫"];

export default function DoorPage() {
  const { roomHash } = useParams<{ roomHash: string }>();
  const [pin, setPin] = useState("");
  const [result, setResult] = useState<DoorAccessResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const resetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const resetState = () => {
    if (resetTimer.current) clearTimeout(resetTimer.current);
    setPin("");
    setResult(null);
    setErrorMsg(null);
  };

  // Auto-reset 10 s after success or error
  const scheduleReset = () => {
    if (resetTimer.current) clearTimeout(resetTimer.current);
    resetTimer.current = setTimeout(resetState, 10_000);
  };

  useEffect(() => () => {
    if (resetTimer.current) clearTimeout(resetTimer.current);
  }, []);

  const mutation = useMutation({
    // The PIN is passed in explicitly: reading `pin` from state here would see
    // the previous render's value, since mutate() runs before React commits
    // the setPin() from the same tap.
    mutationFn: (fullPin: string) => validatePin(roomHash ?? "", fullPin),
    onSuccess: (data) => {
      setResult(data);
      setErrorMsg(null);
      scheduleReset();
    },
    onError: (e: Error) => {
      setErrorMsg(e.message);
      setPin("");
      scheduleReset();
    },
  });

  const handleDigit = (digit: string) => {
    if (digit === "⌫") {
      setPin((p) => p.slice(0, -1));
      return;
    }
    if (pin.length >= 6) return;
    const next = pin + digit;
    setPin(next);
    if (next.length === 6) {
      mutation.mutate(next);
    }
  };

  if (result) {
    return (
      <DoorScreen>
        <div className="flex flex-col items-center gap-6 text-center">
          <CheckCircle size={72} className="text-green-400 drop-shadow-lg" />
          <div>
            <p className="text-3xl font-bold text-white">Door is open</p>
            <p className="text-green-200 mt-2 text-lg">
              Welcome, {result.guest}
            </p>
            <p className="text-green-300/70 text-sm mt-1">{result.room}</p>
          </div>
          <p className="text-xs text-green-300/40 mt-6">
            Screen resets in 10 seconds…
          </p>
        </div>
      </DoorScreen>
    );
  }

  if (errorMsg) {
    return (
      <DoorScreen>
        <div className="flex flex-col items-center gap-6 text-center">
          <XCircle size={72} className="text-red-400 drop-shadow-lg" />
          <div>
            <p className="text-2xl font-bold text-white">Access denied</p>
            <p className="text-red-300 mt-2">{errorMsg}</p>
          </div>
          <button
            className="mt-4 px-6 py-2 rounded-xl bg-white/10 text-white text-sm hover:bg-white/20 transition-colors"
            onClick={resetState}
          >
            Try again
          </button>
          <p className="text-xs text-red-300/40 mt-2">
            Screen resets automatically in 10 seconds…
          </p>
        </div>
      </DoorScreen>
    );
  }

  return (
    <DoorScreen>
      <div className="flex flex-col items-center gap-8 w-full max-w-xs">
        {/* Header */}
        <div className="flex flex-col items-center gap-2">
          <div className="w-16 h-16 rounded-2xl bg-white/10 flex items-center justify-center">
            <DoorOpen size={32} className="text-white" />
          </div>
          <p className="text-white text-xl font-semibold">Enter your PIN</p>
          <p className="text-brand-200/60 text-sm">Scan complete — enter your code</p>
        </div>

        {/* PIN dots */}
        <div className="flex gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className={clsx(
                "w-4 h-4 rounded-full transition-all duration-150",
                i < pin.length
                  ? "bg-white scale-110"
                  : "bg-white/20"
              )}
            />
          ))}
        </div>

        {/* Keypad */}
        <div className="grid grid-cols-3 gap-3 w-full">
          {DIGITS.map((d, i) => (
            <button
              key={i}
              disabled={d === "" || mutation.isPending}
              onClick={() => handleDigit(d)}
              className={clsx(
                "h-16 rounded-2xl text-xl font-semibold transition-all duration-100",
                d === ""
                  ? "invisible"
                  : d === "⌫"
                  ? "bg-white/10 text-white/60 hover:bg-white/20 active:scale-95"
                  : "bg-white/15 text-white hover:bg-white/25 active:scale-95 active:bg-white/30"
              )}
            >
              {d === "⌫" ? <Delete size={20} className="mx-auto" /> : d}
            </button>
          ))}
        </div>

        {mutation.isPending && (
          <p className="text-brand-200/60 text-sm animate-pulse">Verifying…</p>
        )}
      </div>
    </DoorScreen>
  );
}

function DoorScreen({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-900 via-brand-800 to-slate-900 flex flex-col items-center justify-center px-4">
      <div className="absolute top-6 left-1/2 -translate-x-1/2 flex items-center gap-2 opacity-40">
        <Hotel size={18} className="text-white" />
        <span className="text-white text-sm font-medium tracking-wider uppercase">
          Retreat 480
        </span>
      </div>
      {children}
    </div>
  );
}
