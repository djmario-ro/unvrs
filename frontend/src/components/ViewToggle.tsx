import { LayoutGrid, List } from "lucide-react";
import { clsx } from "clsx";

export type ViewMode = "cards" | "list";

export default function ViewToggle({
  value,
  onChange,
}: {
  value: ViewMode;
  onChange: (v: ViewMode) => void;
}) {
  const options = [
    { mode: "cards" as const, icon: LayoutGrid, label: "Card view" },
    { mode: "list" as const, icon: List, label: "List view" },
  ];
  return (
    <div className="inline-flex rounded-lg border border-gray-200 bg-white p-0.5">
      {options.map(({ mode, icon: Icon, label }) => (
        <button
          key={mode}
          onClick={() => onChange(mode)}
          className={clsx(
            "p-1.5 rounded-md transition-colors",
            value === mode
              ? "bg-brand-50 text-brand-600"
              : "text-gray-400 hover:text-gray-600"
          )}
          title={label}
          aria-label={label}
          aria-pressed={value === mode}
        >
          <Icon size={16} />
        </button>
      ))}
    </div>
  );
}
