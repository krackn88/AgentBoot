"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const PREFIX = Buffer.from("X-dUblrIiu-", "utf8");
const REPLAY_PATH =
  process.env.SW_PROBE_REPLAY ||
  path.join(__dirname, "..", "..", "data", "probe_replay.json");

function b64url(buf) {
  return Buffer.from(buf).toString("base64url");
}

function b64urlDecode(text) {
  let t = String(text || "").replace(/-/g, "+").replace(/_/g, "/");
  const pad = (-t.length) % 4;
  if (pad) t += "=".repeat(pad);
  return Buffer.from(t, "base64");
}

/** Normalize webkit send payload to [t0,t1,t2,platform]. */
function decodeSendRequest(raw) {
  let req = raw;
  if (typeof raw === "string") {
    try {
      req = JSON.parse(raw);
    } catch {
      return [];
    }
  }
  if (Array.isArray(req?.[0]) && typeof req[0][0] === "string") {
    req = req[0];
  }
  return Array.isArray(req) ? req : [];
}

function requestKey(tokens) {
  return JSON.stringify(tokens.slice(0, 4));
}

function loadReplayTable() {
  try {
    if (!fs.existsSync(REPLAY_PATH)) {
      return new Map();
    }
    const payload = JSON.parse(fs.readFileSync(REPLAY_PATH, "utf8"));
    const pairs = payload.pairs || payload;
    const table = new Map();
    for (const entry of pairs) {
      const req = entry.request || entry.req;
      const resp = entry.response || entry.resp;
      if (Array.isArray(req) && Array.isArray(resp)) {
        table.set(requestKey(req), resp);
      }
    }
    return table;
  } catch {
    return new Map();
  }
}

function parseSkToken(sk) {
  const parts = String(sk || "").split(";");
  if (parts.length < 3) {
    return { ct: null, key32: null, ident: "" };
  }
  try {
    return {
      ct: b64urlDecode(parts[0]),
      key32: b64urlDecode(parts[1]),
      ident: parts[2] || "",
    };
  } catch {
    return { ct: null, key32: null, ident: parts[2] || "" };
  }
}

function xorPrefixKey(key32) {
  const out = Buffer.from(key32);
  for (let i = 0; i < Math.min(PREFIX.length, out.length); i += 1) {
    out[i] ^= PREFIX[i];
  }
  return out;
}

function deriveProbeKey(sk, mode = "sk-key") {
  const parsed = parseSkToken(sk);
  if (mode === "sk-key" && parsed.key32) {
    return parsed.key32;
  }
  if (mode === "sk-xor" && parsed.key32) {
    return xorPrefixKey(parsed.key32);
  }
  if (mode === "sk-raw") {
    return Buffer.from(String(sk || ""), "utf8");
  }
  return Buffer.from(String(sk || ""), "utf8");
}

function responseForToken(token, key, index, tokens, mode) {
  const t0 = tokens[0] || "";
  const t1 = tokens[1] || "";
  const t2 = tokens[2] || "";
  const src = token || "";

  if (mode === "echo") {
    return src;
  }
  if (mode === "random") {
    return crypto.randomBytes(16).toString("base64url");
  }
  if (mode === "sha256-token") {
    return b64url(crypto.createHash("sha256").update(key).update(src).digest()).slice(0, 43);
  }
  if (mode === "hmac-token") {
    return b64url(crypto.createHmac("sha256", key).update(src).digest()).slice(0, 43);
  }
  if (mode === "hmac-all") {
    return b64url(
      crypto
        .createHmac("sha256", key)
        .update(`${t0}|${t1}|${t2}|${index}`)
        .digest()
    ).slice(0, 43);
  }
  if (mode === "hmac-chain") {
    const h = crypto.createHmac("sha256", key);
    h.update(t0);
    h.update(t1);
    h.update(t2);
    h.update(String(index));
    h.update(src);
    return b64url(h.digest()).slice(0, 43);
  }
  if (mode === "ct-offset") {
    const parsed = parseSkToken(String(key.__sk || ""));
    const ct = parsed.ct || Buffer.alloc(0);
    if (!ct.length) {
      return crypto.randomBytes(16).toString("base64url");
    }
    const h = crypto.createHash("sha256").update(`${t0}|${t1}|${t2}|${index}`).digest();
    const off = h.readUInt32BE(0) % Math.max(1, ct.length - 32);
    return b64url(ct.slice(off, off + 32)).slice(0, 43);
  }
  return crypto.randomBytes(16).toString("base64url");
}

function createProbeHandler(sk, mode = "hmac-chain") {
  const replayTable = mode === "replay" ? loadReplayTable() : null;
  const keyMode = process.env.SW_PROBE_KEY || "sk-key";
  const key = deriveProbeKey(sk, keyMode);
  key.__sk = sk;

  return function probeHandler(raw) {
    const tokens = decodeSendRequest(raw);
    if (!tokens.length) {
      return "[]";
    }

    if (replayTable) {
      const replay = replayTable.get(requestKey(tokens));
      if (replay) {
        return JSON.stringify(replay);
      }
    }

    const resp = tokens.map((token, index) => {
      if (index >= 3) {
        return token;
      }
      return responseForToken(token, key, index, tokens, mode);
    });
    return JSON.stringify(resp);
  };
}

module.exports = {
  REPLAY_PATH,
  b64url,
  b64urlDecode,
  decodeSendRequest,
  parseSkToken,
  loadReplayTable,
  createProbeHandler,
};
