import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { ClipboardList } from "lucide-react";
import { getAuditLog } from "../../api/audit";
import Spinner from "../../components/Spinner";
import { clsx } from "clsx";

const operationColor: Record<string, string> = {
  "guest.create": "bg-green-100 text-green-700",
  "guest.update": "bg-blue-100 text-blue-700",
  "guest.delete": "bg-red-100 text-red-700",
  "room.create": "bg-green-100 text-green-700",
  "room.update": "bg-blue-100 text-blue-700",
  "room.delete": "bg-red-100 text-red-700",
  "assignment.create": "bg-purple-100 text-purple-700",
  "assignment.delete": "bg-red-100 text-red-700",
  "assignment.pin_regenerated": "bg-yellow-100 text-yellow-700",
  "door.access": "bg-teal-100 text-teal-700",
};

export default function AuditPage() {
  const { data: entries = [], isLoading } = useQuery({
    queryKey: ["audit"],
    queryFn: getAuditLog,
    refetchInterval: 15_000,
  });

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Audit Log</h1>
        <p className="text-sm text-gray-500 mt-1">
          Last {entries.length} operations · auto-refreshes every 15 s
        </p>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20">
          <Spinner size={32} />
        </div>
      ) : entries.length === 0 ? (
        <div className="card p-12 text-center text-gray-400">
          <ClipboardList size={40} className="mx-auto mb-3 opacity-40" />
          <p>No audit entries yet.</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="min-w-full divide-y divide-gray-100">
            <thead className="bg-gray-50">
              <tr>
                {["Time", "Operation", "Message"].map((h) => (
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
              {entries.map((e) => (
                <tr key={e.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-gray-400 text-sm whitespace-nowrap">
                    {format(new Date(e.created_at), "dd MMM yyyy HH:mm:ss")}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={clsx(
                        "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
                        operationColor[e.operation] ?? "bg-gray-100 text-gray-700"
                      )}
                    >
                      {e.operation}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">{e.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
