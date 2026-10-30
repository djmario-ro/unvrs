import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { clsx } from "clsx";

/**
 * A door PIN, masked until explicitly revealed — a reception screen is often
 * left open in a room guests walk through.
 */
export default function PinReveal({ pin, className }: { pin: string; className?: string }) {
  const [shown, setShown] = useState(false);
  return (
    <span className={clsx("inline-flex items-center gap-1.5", className)}>
      <span
        className={clsx(
          "font-mono tracking-widest",
          shown ? "text-gray-900" : "text-gray-400 select-none"
        )}
      >
        {shown ? pin : "••••••"}
      </span>
      <button
        type="button"
        className="p-0.5 text-gray-400 hover:text-gray-600 transition-colors"
        onClick={() => setShown((s) => !s)}
        aria-label={shown ? "Hide PIN" : "Reveal PIN"}
        title={shown ? "Hide PIN" : "Reveal PIN"}
      >
        {shown ? <EyeOff size={13} /> : <Eye size={13} />}
      </button>
    </span>
  );
}
