#!/usr/bin/env node
"use strict";
/**
 * Invoke APIGuard VM D-cipher (GI[135]) with fully populated parent frame.
 */
const fs = require("fs");
const zlib = require("zlib");
const { JSDOM } = require("jsdom");
const canvas = require("canvas");

const init = JSON.parse(fs.readFileSync("/tmp/init.json", "utf8"));
const PREFIX = Buffer.from("X-dUblrIiu-", "utf8");
const LJ = Buffer.from("1b4c4a02000000000000", "hex");
const TARGET = "51859262afb3edb6b357";

function shiftSeed(seed) {
  const k = Buffer.from(seed);
  for (let i = 0; i < Math.min(PREFIX.length, k.length); i += 1) k[i] ^= PREFIX[i];
  return k;
}

const mod = init.ck.f5;
const body = zlib.inflateSync(Buffer.from(mod.c, "base64"));
const enc = body.subarray(4);
const key = shiftSeed(Buffer.from(mod.d, "hex"));

let kernel = init.kernel;
kernel = kernel.replace(
  /createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",\[\],(\[\d+(?:,\d+){7}\])/,
  `createEvent("CustomEvent"),["$1","$2",${JSON.stringify(init.ck)},$3`,
);
kernel = kernel.replace(
  'function r(G,a,I,p){"use strict";var X=GI[G];return M(a,I,p,X.L,X.V,X.H,X.J,X.g)};',
  'function r(G,a,I,p){"use strict";var X=GI[G];if(!globalThis.__vmRef)globalThis.__vmRef={Gv,GY,GI,A,Gl,Gt,GC,Q,b,z,M,GU,C,r};return M(a,I,p,X.L,X.V,X.H,X.J,X.g)};',
);

function nativeFn(name, impl = () => null) {
  Object.defineProperty(impl, "name", { value: name });
  return impl;
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
Object.defineProperty(window.navigator, "userAgent", { get: () => "Southwest/13.20.2 CFNetwork/3860.700.2 Darwin/25.6.0" });
window.HTMLCanvasElement.prototype.getContext = () => canvas.createCanvas(1, 1).getContext("2d");
window.document.body.appendChild(Object.assign(window.document.createElement("script"), { textContent: kernel }));

const vm = window.__vmRef;
const gi = vm.GI.findIndex((b) => b?.V?.includes(96) && b?.V?.includes(159));
const block = vm.GI[gi];

function makeParent() {
  const p = new vm.Gl();
  for (let i = 0; i < 512; i += 1) {
    p.N(i);
    p.Nf(i, undefined);
  }
  return p;
}

function toBuf(x) {
  if (Buffer.isBuffer(x)) return x;
  if (x instanceof Uint8Array) return Buffer.from(x);
  if (typeof x === "string") return Buffer.from(x, "latin1");
  if (Array.isArray(x)) return Buffer.from(x);
  return null;
}

function scoreResult(r) {
  const b = toBuf(r);
  if (!b || b.length < 3) return 0;
  if (b[0] === 0x1b && b[1] === 0x4c && b[2] === 0x4a) return 100;
  const ks = Buffer.alloc(10);
  for (let i = 0; i < 10; i += 1) ks[i] = enc[i] ^ b[i] ^ (i ? b[i - 1] : 0);
  let s = 0;
  for (let i = 0; i < 10; i += 1) if (ks[i] === parseInt(TARGET.slice(i * 2, i * 2 + 2), 16)) s += 1;
  return s;
}

const bytes = vm.Q;
const sites = [];
for (let i = 0; i < bytes.length - 1; i += 1) {
  if ((bytes[i] | (bytes[i + 1] << 8)) === gi) sites.push(i);
}

const results = [];
const parent = makeParent();
const argSets = [
  [enc, key],
  [Buffer.concat([body.subarray(0, 4), enc]), key],
  [mod.c, mod.d],
  [Buffer.from(mod.c, "utf8"), Buffer.from(mod.d, "utf8")],
];

for (const pos of sites.slice(0, 40)) {
  for (const z of [pos, pos - 2, pos - 4, pos + 2]) {
    if (z < 0 || z + 3 >= bytes.length) continue;
    const a = bytes[z] | (bytes[z + 1] << 8);
    const I = bytes[z + 2] | (bytes[z + 3] << 8);
    try {
      const fn = vm.r(gi, a, I, parent);
      for (const args of argSets) {
        let r;
        try {
          r = fn(...args);
        } catch {
          continue;
        }
        const score = scoreResult(r);
        if (score >= 4) {
          results.push({ pos, a, I, score, head: toBuf(r)?.slice(0, 16).toString("hex") });
        }
      }
    } catch {
      /* ignore */
    }
  }
}

const out = { gi, sites: sites.length, hits: results.sort((a, b) => b.score - a.score).slice(0, 20) };
fs.writeFileSync("/tmp/vm_cipher_invoke.json", JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
