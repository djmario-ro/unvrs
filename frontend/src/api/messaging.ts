import api from "./client";
import type {
  Channel,
  MessageLog,
  SendPinResult,
  WhatsAppQr,
  WhatsAppStatus,
} from "./types";

export const sendPin = (assignmentId: number, channels: Channel[]) =>
  api
    .post<SendPinResult>(`/assignments/${assignmentId}/send-pin`, { channels })
    .then((r) => r.data);

export const getWhatsappStatus = () =>
  api.get<WhatsAppStatus>("/messaging/whatsapp/status").then((r) => r.data);

export const getWhatsappQr = () =>
  api.get<WhatsAppQr>("/messaging/whatsapp/qr").then((r) => r.data);

export const getMessageLogs = () =>
  api.get<MessageLog[]>("/messaging/logs").then((r) => r.data);
