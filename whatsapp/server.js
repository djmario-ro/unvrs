const crypto = require("crypto");
const fs = require("fs/promises");
const express = require("express");
const QRCode = require("qrcode");
const pino = require("pino");
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} = require("@whiskeysockets/baileys");

const PORT = process.env.PORT || 3000;
const AUTH_DIR = process.env.AUTH_DIR || "/app/auth";

// Shared connection state, kept in memory and exposed over HTTP.
const state = {
  sock: null,
  connected: false,
  number: null,
  qr: null, // data URL of the current pairing QR, or null once linked
};

const logger = pino({ level: "silent" });

// Reconnect with exponential backoff so a transient failure doesn't become a
// tight loop, and so a rejected start() never surfaces as an unhandled
// rejection that would kill the process.
let reconnectDelay = 2000;
function scheduleRestart({ immediate = false } = {}) {
  const delay = immediate ? 500 : reconnectDelay;
  if (!immediate) reconnectDelay = Math.min(reconnectDelay * 2, 60_000);
  setTimeout(() => {
    start().catch((err) => {
      console.error("WhatsApp start failed:", err?.message || err);
      scheduleRestart();
    });
  }, delay);
}

// A logged-out session can never reconnect: drop the stale credentials so the
// next start() emits a fresh pairing QR instead of failing forever.
async function clearAuthState() {
  // AUTH_DIR is a volume mount point, so remove its contents, not the dir.
  await fs.mkdir(AUTH_DIR, { recursive: true });
  for (const entry of await fs.readdir(AUTH_DIR)) {
    await fs.rm(`${AUTH_DIR}/${entry}`, { recursive: true, force: true });
  }
  state.number = null;
  state.qr = null;
}

async function start() {
  if (state.sock) {
    try {
      state.sock.ev.removeAllListeners("connection.update");
      state.sock.end(undefined);
    } catch (_) {
      // best effort: the old socket may already be closed
    }
    state.sock = null;
  }
  const { state: authState, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    version,
    auth: authState,
    printQRInTerminal: false,
    logger,
  });
  state.sock = sock;

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      // A QR means we're actively pairing: reset the backoff so a failed scan
      // is followed by a fresh QR quickly, not after a long delay.
      state.qr = await QRCode.toDataURL(qr);
      state.connected = false;
      reconnectDelay = 2000;
    }

    if (connection === "open") {
      state.connected = true;
      state.qr = null;
      state.number = sock.user?.id?.split(":")[0] || null;
      reconnectDelay = 2000;
      console.log(`WhatsApp linked as ${state.number}`);
    }

    if (connection === "close") {
      state.connected = false;
      const code = lastDisconnect?.error?.output?.statusCode;
      const loggedOut = code === DisconnectReason.loggedOut;
      // restartRequired (515) is the normal step right after a QR scan: the
      // socket must be recreated at once to finish the handshake, so don't
      // let the backoff stall it.
      const restartRequired = code === DisconnectReason.restartRequired;
      console.log(`WhatsApp connection closed (code=${code} loggedOut=${loggedOut})`);
      if (loggedOut) {
        console.log("Session was logged out; clearing it so a new pairing QR can be issued");
        await clearAuthState();
      }
      scheduleRestart({ immediate: restartRequired });
    }
  });
}

process.on("unhandledRejection", (err) => {
  console.error("Unhandled rejection:", err?.message || err);
});

function toNumber(phone) {
  return String(phone).replace(/\D/g, "");
}

// The token guards /send (messages from the guesthouse's real number) and
// /qr (the pairing code, i.e. the account itself), so running without one is
// only allowed when asked for explicitly, for local experiments.
const API_TOKEN = process.env.API_TOKEN || "";
if (!API_TOKEN) {
  if (process.env.ALLOW_UNAUTHENTICATED !== "true") {
    console.error(
      "API_TOKEN is not set. Refusing to start: without it anyone on the network " +
        "could send messages or pair a device. Set API_TOKEN (and the same value " +
        "as WHATSAPP_API_TOKEN for the backend), or set ALLOW_UNAUTHENTICATED=true " +
        "for a local experiment."
    );
    process.exit(1);
  }
  console.warn("WARNING: API_TOKEN not set — sidecar endpoints are unauthenticated");
}

function tokenMatches(header) {
  const expected = Buffer.from(`Bearer ${API_TOKEN}`);
  const given = Buffer.from(String(header || ""));
  return given.length === expected.length && crypto.timingSafeEqual(given, expected);
}

const app = express();
app.disable("x-powered-by");

// Liveness probe for the container healthcheck: no secrets, so it sits before
// the auth middleware and reports whether WhatsApp is currently linked.
app.get("/health", (_req, res) => {
  res.json({ ok: true, connected: state.connected });
});

// Authenticate before parsing bodies, so unauthenticated callers can't make
// us buffer and parse multi-megabyte payloads.
app.use((req, res, next) => {
  if (!API_TOKEN) return next();
  if (tokenMatches(req.headers["authorization"])) return next();
  return res.status(401).json({ detail: "unauthorized" });
});
// The only image we ever receive is a small QR PNG from the backend.
app.use(express.json({ limit: "1mb" }));

app.get("/status", (_req, res) => {
  res.json({ connected: state.connected, number: state.number });
});

app.get("/qr", (_req, res) => {
  res.json({ qr: state.connected ? null : state.qr });
});

app.post("/send", async (req, res) => {
  const { phone, message, image } = req.body || {};
  if (!phone || !message) {
    return res.status(400).json({ detail: "phone and message are required" });
  }
  if (!state.connected || !state.sock) {
    return res.status(409).json({ detail: "WhatsApp is not linked" });
  }
  try {
    // Resolve the canonical WhatsApp address; a number that isn't registered
    // returns no result, so we fail fast instead of hanging on send.
    const [contact] = await state.sock.onWhatsApp(toNumber(phone));
    if (!contact?.exists) {
      return res.status(422).json({ detail: `${phone} is not on WhatsApp` });
    }
    // With an image (base64), send it as a photo captioned with the message.
    const content = image
      ? { image: Buffer.from(image, "base64"), caption: message }
      : { text: message };
    await state.sock.sendMessage(contact.jid, content);
    res.json({ status: "sent" });
  } catch (err) {
    res.status(502).json({ detail: `send failed: ${err.message}` });
  }
});

app.listen(PORT, () => console.log(`WhatsApp sidecar listening on :${PORT}`));
start().catch((err) => {
  console.error("Failed to start WhatsApp socket:", err?.message || err);
  scheduleRestart();
});
