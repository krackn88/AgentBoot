#!/usr/bin/env node
/**
 * Execute APIGuard kernel JS and capture session headers via webkit bridge mock.
 *
 * The iOS kernel expects:
 *   window.global.nativeAgent
 *   window.webkit.messageHandlers.{send,pushMinPayload,pushMaxPayload}
 *
 * Output JSON: { kernelId, sk, headers, errors }
 */
"use strict";

const crypto = require("crypto");
const { fetch: undiciFetch, ProxyAgent } = require("undici");
const { JSDOM } = require("jsdom");
const canvas = require("canvas");

const INIT_URL =
  process.env.SW_INIT_URL ||
  "https://mobile.southwest.com/sw_check/ios/init?cid=ios_config";
const API_KEY = process.env.SW_API_KEY || "l7xx3386def1284d487ca8cb3aa80729d766";
const UA =
  process.env.SW_UA ||
  "Southwest/13.20.2 CFNetwork/3860.700.2 Darwin/25.6.0";
const REQUEST_URL =
  process.env.SW_REQUEST_URL ||
  "https://mobile.southwest.com/api/security/v4/security/token";

function normalizeProxy(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (raw.includes("://")) return raw;
  const parts = raw.split(":");
  if (parts.length < 4) return raw;
  const host = parts[0];
  const port = parts[1];
  const user = encodeURIComponent(parts[2]);
  const pass = encodeURIComponent(parts.slice(3).join(":"));
  return `http://${user}:${pass}@${host}:${port}`;
}

async function fetchInit() {
  const proxy = normalizeProxy(process.env.SW_PROXY);
  const opts = {
    headers: {
      "User-Agent": UA,
      "X-Channel-ID": "IOS",
      "X-API-Key": API_KEY,
      Accept: "*/*",
    },
  };
  if (proxy) {
    opts.dispatcher = new ProxyAgent(proxy);
  }
  const res = await undiciFetch(INIT_URL, opts);
  if (!res.ok) {
    throw new Error(`init HTTP ${res.status}`);
  }
  return res.json();
}

function nativeFn(name, impl = () => null) {
  const fn = impl;
  Object.defineProperty(fn, "name", { value: name });
  Object.defineProperty(fn, "toString", {
    value: () => `function ${name}() { [native code] }`,
  });
  return fn;
}

/** Parse comma-joined header payload: name,value,name,value,... */
function parseHeaderPayload(raw) {
  const headers = {};
  if (!raw || typeof raw !== "string") return headers;
  const re = /(X-dUblrIiu-[a-z])[,=](.*?)(?=,X-dUblrIiu-[a-z]|$)/gi;
  let match;
  while ((match = re.exec(raw)) !== null) {
    headers[match[1].toLowerCase()] = match[2];
  }
  return headers;
}

function mergeHeaders(target, source) {
  for (const [k, v] of Object.entries(source)) {
    if (v) target[k] = v;
  }
}

function makeHandler(name, fn) {
  return { postMessage: nativeFn("postMessage", fn) };
}

function buildBridge(onHeaders) {
  const pendingSend = [];

  const sendHandler = makeHandler("send", (...args) => {
    try {
      const req = JSON.parse(args[0]);
      const resp = req.map(() => crypto.randomBytes(16).toString("base64url"));
      pendingSend.push({ reqLen: req.length });
      return JSON.stringify(resp);
    } catch {
      return "[]";
    }
  });

  const pushHandler = (kind) =>
    makeHandler(kind, (...args) => {
      mergeHeaders(onHeaders, parseHeaderPayload(String(args[0] || "")));
    });

  const messageHandlers = new Proxy(
    {},
    {
      get(target, prop) {
        const key = String(prop);
        if (!target[key]) {
          if (key === "pushMinPayload") target[key] = pushHandler(key);
          else if (key === "pushMaxPayload") target[key] = pushHandler(key);
          else target[key] = sendHandler;
        }
        return target[key];
      },
    }
  );

  return { messageHandlers, pendingSend };
}

function runKernel(initData, requestUrl) {
  const headers = {};
  const errors = [];
  const { messageHandlers } = buildBridge(headers);

  const agent = {
    ios: {},
    invoke: nativeFn("invoke", () => null),
  };

  const dom = new JSDOM(
    '<!DOCTYPE html><html><head></head><body><script nonce="apiguard"></script></body></html>',
    {
      url: "https://mobile.southwest.com/",
      runScripts: "dangerously",
      pretendToBeVisual: true,
      beforeParse(window) {
        window.global = { nativeAgent: agent };
        window.webkit = { messageHandlers };
      },
    }
  );

  const { window } = dom;
  Object.defineProperty(window.navigator, "userAgent", { get: () => UA });
  Object.defineProperty(window.navigator, "platform", { get: () => "iPhone" });

  window.HTMLCanvasElement.prototype.getContext = function (type) {
    const c = canvas.createCanvas(this.width || 300, this.height || 150);
    return c.getContext(type === "webgl" || type === "experimental-webgl" ? "webgl" : "2d");
  };

  window.addEventListener("error", (e) => errors.push(e.message || String(e.error)));

  const script = window.document.createElement("script");
  script.textContent = initData.kernel;
  window.document.body.appendChild(script);

  // Allow bootstrap probes to finish (bounded)
  const start = Date.now();
  while (Date.now() - start < 2500) {
    // spin briefly; kernel runs synchronously on appendChild
  }

  if (typeof window.__callback === "function") {
    try {
      window.__callback("POST", requestUrl);
    } catch (e) {
      errors.push(`callback: ${e.message}`);
    }
  }

  return { headers, errors, hasCallback: typeof window.__callback === "function" };
}

async function main() {
  const initData = await fetchInit();
  const { headers, errors, hasCallback } = runKernel(initData, REQUEST_URL);

  const out = {
    kernelId: initData.kernelId,
    sk: initData.sk,
    headers,
    headerKeys: Object.keys(headers).sort(),
    hasCallback,
    errors,
  };

  console.log(JSON.stringify(out, null, 2));
  process.exit(errors.length && !Object.keys(headers).length ? 1 : 0);
}

main().catch((e) => {
  console.error(JSON.stringify({ error: e.message, stack: e.stack }));
  process.exit(1);
});
