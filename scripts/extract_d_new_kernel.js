#!/usr/bin/env node
"use strict";
/**
 * Invoke B[624] D-cipher with authentic bootstrap args (K=79520, g=9) from callback.
 * Hooks F() during kernel init, captures parent frame, then decrypts f5 ck module.
 *
 * Writes /tmp/d_cipher_new.json
 */
const fs = require("fs");
const zlib = require("zlib");
const { JSDOM } = require("jsdom");
const canvas = require("canvas");

const INIT_PATH = process.env.SW_INIT_JSON || "/tmp/init.json";
const OUT_PATH = "/tmp/d_cipher_new.json";
const D_STATIC = 624;
const D_RUNTIME = 135;
const TIMEOUT_MS = 15000;

const PREFIX = Buffer.from("X-dUblrIiu-", "utf8");
const TARGET_KS = "51859262afb3edb6b357";

function shiftSeed(seed) {
  const key = Buffer.from(seed);
  for (let i = 0; i < Math.min(PREFIX.length, key.length); i += 1) {
    key[i] ^= PREFIX[i];
  }
  return key;
}

function patchKernel(kernel, ck) {
  const ckJson = JSON.stringify(ck || {});
  let patched = kernel.replace(
    /createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",\[\],(\[\d+(?:,\d+){7}\])/,
    `createEvent("CustomEvent"),["$1","$2",${ckJson},$3`,
  );

  const hookF = `
function F(b,K,g,W){
  "use strict";
  var u=B[b];
  if(!window.__cap) window.__cap={calls:[],fcc:[],states:[]};
  if(b===${D_STATIC}||b===${D_RUNTIME}){
    window.__cap.calls.push({b,K,g,WType:typeof W});
    window.__cap.lastParent=W;
    window.__cap.lastArgs={b,K,g};
  }
  var fn=d(K,g,W,u.H,u.X,u.p,u.G,u.S);
  if(b===${D_STATIC}){
    window.__cap.decryptFn=fn;
    window.__cap.decryptFnType=typeof fn;
  }
  return fn;
}`;

  patched = patched.replace(
    /function F\(b,K,g,W\)\{"use strict";var u=B\[b\];return d\(K,g,W,u\.H,u\.X,u\.p,u\.G,u\.S\)\}/,
    hookF,
  );

  const ksPrefix = TARGET_KS.slice(0, 10);
  const hooks = `
window.__cap={calls:[],fcc:[],states:[],active:false,pendingDecrypt:null};
(function(){
  const o=String.fromCharCode;
  String.fromCharCode=function(...codes){
    if(window.__cap.active&&codes.length>=4){
      const hex=codes.slice(0,16).map(c=>(c&255).toString(16).padStart(2,"0")).join("");
      window.__cap.fcc.push({len:codes.length,hex});
      if(hex.startsWith("${ksPrefix}")) window.__cap.matched=true;
    }
    return o(...codes);
  };
})();
`;

  return hooks + patched;
}

function nativeFn(name, impl = () => null) {
  Object.defineProperty(impl, "name", { value: name });
  return impl;
}

function main() {
  const init = JSON.parse(fs.readFileSync(INIT_PATH, "utf8"));
  const mod = init.ck?.f5;
  if (!mod) throw new Error("f5 module missing");

  const body = zlib.inflateSync(Buffer.from(mod.c, "base64"));
  const ciphertext = body.subarray(4);
  const keyShifted = shiftSeed(Buffer.from(mod.d, "hex"));

  const argSets = [
    [ciphertext, keyShifted],
    [new Uint8Array(ciphertext), new Uint8Array(keyShifted)],
    [body, keyShifted],
    [Buffer.from(body), keyShifted],
    [mod.c, mod.d],
  ];

  let decryptFn = null;
  const patched = patchKernel(init.kernel, init.ck);

  const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
    url: "https://mobile.southwest.com/",
    runScripts: "dangerously",
    pretendToBeVisual: true,
    beforeParse(w) {
      w.global = {
        nativeAgent: { ios: {}, invoke: nativeFn("invoke", () => null) },
        ck: init.ck,
        sk: init.sk,
        kernelId: init.kernelId,
      };
      w.webkit = {
        messageHandlers: {
          send: { postMessage: nativeFn("postMessage", () => "[]") },
          pushMinPayload: { postMessage: nativeFn("postMessage", () => {}) },
          pushMaxPayload: { postMessage: nativeFn("postMessage", () => {}) },
        },
      };
    },
  });

  const { window } = dom;
  Object.defineProperty(window.navigator, "userAgent", {
    get: () => "Southwest/13.20.2 CFNetwork/3860.700.2 Darwin/25.6.0",
  });
  window.HTMLCanvasElement.prototype.getContext = function () {
    return canvas.createCanvas(1, 1).getContext("2d");
  };

  const script = window.document.createElement("script");
  script.textContent = patched;
  window.document.body.appendChild(script);

  // Bootstrap creates authentic F(624, K, g, parent) — hook stores decrypt closure.
  if (typeof window.__callback === "function") {
    window.__callback("POST", "https://mobile.southwest.com/api/security/v4/security/token");
  }

  decryptFn = window.__cap?.decryptFn;

  const cap = window.__cap || {};
  const attempts = [];

  if (typeof decryptFn === "function") {
    window.__cap.active = true;
    for (let ai = 0; ai < argSets.length; ai += 1) {
      try {
        const result = decryptFn(...argSets[ai]);
        let head = null;
        if (typeof result === "string") {
          head = Buffer.from(result.slice(0, 8), "latin1").toString("hex");
        } else if (result instanceof Uint8Array || Buffer.isBuffer(result)) {
          head = Buffer.from(result.subarray(0, 8)).toString("hex");
        }
        attempts.push({
          ai,
          type: typeof result,
          head,
          luaJit: head?.startsWith("1b4c4a") || false,
        });
      } catch (err) {
        attempts.push({ ai, error: err.message });
      }
    }
    window.__cap.active = false;
  }

  // Also try re-calling F with captured bootstrap args if we have vm refs from a second patch
  const staticCall = cap.calls?.find((c) => c.b === D_STATIC);

  const findings = {
    generatedAt: new Date().toISOString(),
    initPath: INIT_PATH,
    kernelId: init.kernelId,
    format: "B/bA/bC",
    bootstrapCalls: cap.calls || [],
    staticCall,
    f5: {
      ciphertextHead: ciphertext.subarray(0, 8).toString("hex"),
      keyShiftedHex: keyShifted.toString("hex"),
      targetKeystreamPrefix: TARGET_KS,
    },
    runtime: {
      decryptFnCaptured: typeof decryptFn === "function",
      decryptFnType: cap.decryptFnType || typeof cap.decryptFn,
      fromCharCodeEvents: cap.fcc || [],
      matchedKeystream: Boolean(cap.matched),
      attempts,
      decrypted: attempts.some((a) => a.luaJit),
    },
  };

  fs.writeFileSync(OUT_PATH, JSON.stringify(findings, null, 2));
  console.log(JSON.stringify(findings, null, 2));
  return findings;
}

let finished = false;
const timer = setTimeout(() => {
  if (!finished) {
    finished = true;
    fs.writeFileSync(OUT_PATH, JSON.stringify({ timeout: true }, null, 2));
    process.exit(0);
  }
}, TIMEOUT_MS);

try {
  main();
  if (!finished) {
    finished = true;
    clearTimeout(timer);
    process.exit(0);
  }
} catch (err) {
  if (!finished) {
    finished = true;
    clearTimeout(timer);
    fs.writeFileSync(OUT_PATH, JSON.stringify({ error: err.message, stack: err.stack }, null, 2));
    console.error(err.stack);
    process.exit(1);
  }
}
