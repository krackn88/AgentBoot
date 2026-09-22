#!/usr/bin/env node
"use strict";
/** Capture r(135) during bootstrap; replay decrypt after with captured a/I and slot dump. */
const fs = require("fs");
const zlib = require("zlib");
const { JSDOM } = require("jsdom");
const canvas = require("canvas");
const { createProbeHandler, parseInitArgs } = require("../southwest_checker/apiguard/probe_handler");

const init = JSON.parse(fs.readFileSync("/tmp/init.json", "utf8"));
const ckJson = JSON.stringify(init.ck || {});
const mod = init.ck.f5;
const body = zlib.inflateSync(Buffer.from(mod.c, "base64"));
const enc = body.subarray(4);
const PREFIX = Buffer.from("X-dUblrIiu-", "utf8");

function shiftSeed(seed) {
  const k = Buffer.from(seed);
  for (let i = 0; i < Math.min(PREFIX.length, k.length); i += 1) k[i] ^= PREFIX[i];
  return k;
}
const keyS = shiftSeed(Buffer.from(mod.d, "hex"));

function toHex(x) {
  if (x == null) return null;
  if (Buffer.isBuffer(x)) return x.slice(0, 16).toString("hex");
  if (x instanceof Uint8Array) return Buffer.from(x).slice(0, 16).toString("hex");
  if (typeof x === "string") {
    return [...x.slice(0, 8)].map((c) => c.charCodeAt(0).toString(16).padStart(2, "0")).join("");
  }
  if (Array.isArray(x)) return Buffer.from(x.slice(0, 8)).toString("hex");
  return null;
}

function patchKernel(kernel) {
  let k = kernel.replace(
    /createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",\[\],(\[\d+(?:,\d+){7}\])/,
    `createEvent("CustomEvent"),["$1","$2",${ckJson},$3`,
  );

  k = `window.__cap={calls:[]};\n` + k;
  k = k.replace(
    'function r(G,a,I,p){"use strict";var X=GI[G];return M(a,I,p,X.L,X.V,X.H,X.J,X.g)}',
    `function r(G,a,I,p){"use strict";var X=GI[G];
if(!window.__vmRef)window.__vmRef={Gv,GY,GI,A,Gl,Gt,GC,Q,b,z,M,GU,C,r};
if(G===135){
  var slots={};
  for(var si=0;si<128;si++){ try{ var v=p.Nf(si); if(v!=null) slots[si]=v; }catch(e){} }
  window.__cap.calls.push({a:a,I:I,slots:slots});
}
return M(a,I,p,X.L,X.V,X.H,X.J,X.g);`,
  );
  return k;
}

function nativeFn(name, impl = () => null) {
  Object.defineProperty(impl, "name", { value: name });
  return impl;
}

const initArgs = parseInitArgs(init.kernel);
const computeProbe = createProbeHandler(init.sk, "native-sess-all", init, initArgs);

const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
  url: "https://mobile.southwest.com/",
  runScripts: "dangerously",
  pretendToBeVisual: true,
  beforeParse(w) {
    w.global = {
      nativeAgent: { ios: {}, invoke: nativeFn("invoke", () => null) },
      ck: init.ck,
      sk: init.sk,
    };
    w.webkit = {
      messageHandlers: new Proxy(
        {},
        {
          get(t, p) {
            const k = String(p);
            if (!t[k]) {
              t[k] = {
                postMessage: nativeFn("postMessage", (...args) => {
                  if (k === "send") return computeProbe(args[0]);
                  return undefined;
                }),
              };
            }
            return t[k];
          },
        },
      ),
    };
  },
});

const { window } = dom;
Object.defineProperty(window.navigator, "userAgent", {
  get: () => "Southwest/13.20.2 CFNetwork/3860.700.2 Darwin/25.6.0",
});
window.HTMLCanvasElement.prototype.getContext = () => canvas.createCanvas(1, 1).getContext("2d");
window.document.body.appendChild(
  Object.assign(window.document.createElement("script"), { textContent: patchKernel(init.kernel) }),
);

const vm = window.__vmRef;
const out = { captured: window.__cap?.calls || [], replays: [] };

function makeParentFromCapture(cap) {
  const p = new vm.Gl();
  for (let i = 0; i < 512; i += 1) {
    p.N(i);
    p.Nf(i, cap.slots[i] ?? undefined);
  }
  return p;
}

const argSets = [
  [enc, keyS],
  [body, keyS],
  [new Uint8Array(enc), new Uint8Array(keyS)],
  [Buffer.from(mod.c, "utf8"), Buffer.from(mod.d, "utf8")],
  [init.ck.f5, init.sk],
];

for (const cap of out.captured) {
  const parent = makeParentFromCapture(cap);
  try {
    const fn = vm.r(135, cap.a, cap.I, parent);
    for (let ai = 0; ai < argSets.length; ai += 1) {
      try {
        const r = fn(...argSets[ai]);
        const head = toHex(r);
        const lj = head && head.startsWith("1b4c4a");
        out.replays.push({ a: cap.a, I: cap.I, ai, type: typeof r, head, lj });
      } catch (e) {
        out.replays.push({ a: cap.a, I: cap.I, ai, err: e.message });
      }
    }
  } catch (e) {
    out.replays.push({ a: cap.a, I: cap.I, err: e.message });
  }
}

if (typeof window.__callback === "function") {
  window.__callback("POST", "https://mobile.southwest.com/api/security/v4/security/token");
}

// replay again after callback in case more captures
for (const cap of (window.__cap?.calls || []).slice(out.captured.length)) {
  const parent = makeParentFromCapture(cap);
  try {
    const fn = vm.r(135, cap.a, cap.I, parent);
    const r = fn(enc, keyS);
    out.replays.push({ phase: "post-callback", a: cap.a, I: cap.I, head: toHex(r) });
  } catch (e) {
    out.replays.push({ phase: "post-callback", err: e.message });
  }
}

out.totalCaptures = window.__cap?.calls?.length || 0;
fs.writeFileSync("/tmp/r135_replay.json", JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
