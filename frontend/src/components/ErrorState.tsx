import { AlertTriangle, RefreshCw } from "lucide-react";

interface Props {
  /** What failed to load, e.g. "guests". */
  what: string;
  error: unknown;
  onRetry?: () => void;
}

/** Inline failure card for a query, so an error never masquerades as an empty list. */
export default function ErrorState({ what, error, onRetry }: Props) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="card p-12 text-center text-gray-500" role="alert">
      <AlertTriangle size={40} className="mx-auto mb-3 text-red-400" />
      <p className="font-medium text-gray-700">Couldn’t load {what}</p>
      <p className="text-sm mt-1 text-gray-500">{message}</p>
      {onRetry && (
        <button className="btn-secondary mt-5 inline-flex items-center gap-2" onClick={onRetry}>
          <RefreshCw size={14} /> Try again
        </button>
      )}
    </div>
  );
}
