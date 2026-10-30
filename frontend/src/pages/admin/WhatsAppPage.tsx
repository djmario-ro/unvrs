import { useQuery } from "@tanstack/react-query";
import { MessageCircle, CheckCircle2, Loader2 } from "lucide-react";

import { getWhatsappStatus, getWhatsappQr } from "../../api/messaging";
import Spinner from "../../components/Spinner";
import ErrorState from "../../components/ErrorState";

export default function WhatsAppPage() {
  const { data: status, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["whatsapp", "status"],
    queryFn: getWhatsappStatus,
    // Poll hard only while pairing; once linked, a slow heartbeat is enough.
    refetchInterval: (q) => (q.state.data?.connected ? 30_000 : 3000),
  });

  const connected = status?.connected ?? false;

  const { data: qrData } = useQuery({
    queryKey: ["whatsapp", "qr"],
    queryFn: getWhatsappQr,
    refetchInterval: 3000,
    enabled: !connected,
  });

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">WhatsApp</h1>
        <p className="text-sm text-gray-500 mt-1">
          Link the guesthouse number to send PINs over WhatsApp
        </p>
      </div>

      {isError ? (
        <div className="max-w-md">
          <ErrorState what="the WhatsApp service" error={error} onRetry={() => refetch()} />
        </div>
      ) : isLoading ? (
        <div className="flex justify-center py-20">
          <Spinner size={32} />
        </div>
      ) : connected ? (
        <div className="card p-8 flex items-center gap-4 max-w-md">
          <CheckCircle2 className="text-green-500 flex-shrink-0" size={40} />
          <div>
            <p className="font-semibold text-gray-900">Connected</p>
            <p className="text-sm text-gray-500">
              Linked as{" "}
              <span className="font-mono">{status?.number ?? "unknown"}</span>
            </p>
          </div>
        </div>
      ) : (
        <div className="card p-8 max-w-md text-center">
          <MessageCircle className="mx-auto mb-3 text-brand-600" size={32} />
          <p className="text-sm text-gray-600 mb-6">
            Open WhatsApp on the guesthouse phone →{" "}
            <span className="font-medium">Linked devices</span> →{" "}
            <span className="font-medium">Link a device</span>, then scan this
            code.
          </p>
          {qrData?.qr ? (
            <img
              src={qrData.qr}
              alt="WhatsApp pairing QR"
              className="mx-auto w-64 h-64 rounded-xl border border-gray-100"
            />
          ) : (
            <div className="flex flex-col items-center gap-3 py-10 text-gray-400">
              <Loader2 className="animate-spin" size={28} />
              <p className="text-sm">Waiting for a pairing code…</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
