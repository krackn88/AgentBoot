#!/usr/bin/env node
"use strict";
const fs = require("fs");
const zlib = require("zlib");
const { JSDOM } = require("jsdom");
const canvas = require("canvas");

const init = JSON.parse(fs.readFileSync("/tmp/init.json", "utf8"));
const PREFIX = Buffer.from("X-dUblrIiu-", "utf8");

function shiftSeed(s) {
  const k = Buffer.from(s);
  for (let i = 0; i < Math.min(PREFIX.length, k.length); i += 1) k[i] ^= PREFIX[i];
  return k;
}

const mod = init.ck.f5;
const body = zlib.inflateSync(Buffer.from(mod.c, "base64"));
const enc = body.subarray(4);
const key = shiftSeed(Buffer.from(mod.d, "hex"));

let kernel = init.kernel.replace(
  /createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",\[\],(\[\d+(?:,\d+){7}\])/,
  `createEvent("CustomEvent"),["$1","$2",${JSON.stringify(init.ck)},$3`,
);
kernel = kernel.replace(
  'function r(G,a,I,p){"use strict";var X=GI[G];return M(a,I,p,X.L,X.V,X.H,X.J,X.g)}',
  'function r(G,a,I,p){"use strict";var X=GI[G];if(!globalThis.__vmRef)globalThis.__vmRef={Gv,GY,GI,A,Gl,Gt,GC,Q,b,z,M,GU,C,r};return M(a,I,p,X.L,X.V,X.H,X.J,X.g)}',
);

function nativeFn(n, f) {
  Object.defineProperty(f, "name", { value: n });
  return f;
}

const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
  url: "https://mobile.southwest.com/",
  runScripts: "dangerously",
  beforeParse(w) {
    w.global = { nativeAgent: { ios: {}, invoke: nativeFn("invoke", () => null) } };
    w.webkit = { messageHandlers: { send: { postMessage: nativeFn("postMessage", () => "[]") } } };
  },
});
const { window } = dom;
Object.defineProperty(window.navigator, "userAgent", {
  get: () => "Southwest/13.20.2 CFNetwork/3860.700.2 Darwin/25.6.0",
});
window.HTMLCanvasElement.prototype.getContext = () => canvas.createCanvas(1, 1).getContext("2d");
window.document.body.appendChild(
  Object.assign(window.document.createElement("script"), { textContent: kernel }),
);

const vm = window.__vmRef;
const gi = 135;
const Q = vm.Q;
const sites = [];
for (let i = 0; i < Q.length - 1; i += 1) {
  if ((Q[i] | (Q[i + 1] << 8)) === gi) sites.push(i);
}

function makeParent() {
  const p = new vm.Gl();
  for (let i = 0; i < 512; i += 1) {
    p.N(i);
    p.Nf(i, undefined);
  }
  return p;
}

const parent = makeParent();
for (let i = 0; i < 256; i += 1) {
  parent.Nf(i, enc);
  parent.Nf(i + 256, key);
}

function toBuf(x) {
  if (Buffer.isBuffer(x)) return x;
  if (x instanceof Uint8Array) return Buffer.from(x);
  if (typeof x === "string") return Buffer.from(x, "latin1");
  if (Array.isArray(x)) return Buffer.from(x);
  return null;
}

function score(r) {
  const b = toBuf(r);
  if (!b || b.length < 3) return 0;
  if (b[0] === 0x1b && b[1] === 0x4c && b[2] === 0x4a) return 100;
  return 0;
}

const argSets = [
  [enc, key],
  [body, key],
  [Buffer.from(mod.c, "utf8"), Buffer.from(mod.d, "utf8")],
  [enc, key, body],
  [key, enc],
  [Array.from(enc), Array.from(key)],
  [new Uint8Array(enc), new Uint8Array(key)],
];

const hits = [];
const tried = new Set();

for (const pos of sites) {
  for (const z of [pos - 2, pos - 4, pos - 6, pos - 8]) {
    if (z < 0 || z + 3 >= Q.length) continue;
    if ((Q[z + 2] | (Q[z + 3] << 8)) !== gi) continue;
    const a = Q[z + 1];
    const I = Q[z];
    const tk = `${a},${I}`;
    if (tried.has(tk)) continue;
    tried.add(tk);
    try {
      const fn = vm.r(gi, a, I, parent);
      for (const args of argSets) {
        let r;
        try {
          r = fn(...args);
        } catch {
          continue;
        }
        if (score(r) >= 100) {
          hits.push({ pos, a, I, head: toBuf(r).slice(0, 16).toString("hex") });
        }
      }
    } catch {
      /* ignore */
    }
  }
}

console.log(JSON.stringify({ sites: sites.length, tried: tried.size, hits }, null, 2));
