#!/usr/bin/env node
"use strict";
/**
 * Invoke GI[135] using authentic call-site args captured from bootstrap (a=91131, I=5).
 */
const fs = require("fs");
const zlib = require("zlib");
const { JSDOM } = require("jsdom");
const canvas = require("canvas");
const { createProbeHandler, parseInitArgs } = require("../southwest_checker/apiguard/probe_handler");

const INIT_PATH = process.env.SW_INIT_JSON || "/tmp/init.json";
const OUT_PATH = "/tmp/r135_authentic_invoke.json";

const PREFIX = Buffer.from("X-dUblrIiu-", "utf8");
const LJ = Buffer.from("1b4c4a02000000000000", "hex");
const TARGET = "51859262afb3edb6b357";

function shiftSeed(seed) {
  const k = Buffer.from(seed);
  for (let i = 0; i < Math.min(PREFIX.length, k.length); i += 1) k[i] ^= PREFIX[i];
  return k;
}

const init = JSON.parse(fs.readFileSync(INIT_PATH, "utf8"));
const ckJson = JSON.stringify(init.ck || {});
const mod = init.ck.f5;
const body = zlib.inflateSync(Buffer.from(mod.c, "base64"));
const enc = body.subarray(4);
const key = shiftSeed(Buffer.from(mod.d, "hex"));

function patchKernel(kernel) {
  let k = kernel.replace(
    /createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",\[\],(\[\d+(?:,\d+){7}\])/,
    `createEvent("CustomEvent"),["$1","$2",${ckJson},$3`,
  );
  k = k.replace(
    'function r(G,a,I,p){"use strict";var X=GI[G];return M(a,I,p,X.L,X.V,X.H,X.J,X.g)}',
    'function r(G,a,I,p){"use strict";var X=GI[G];if(!globalThis.__vmRef)globalThis.__vmRef={Gv,GY,GI,A,Gl,Gt,GC,Q,b,z,M,GU,C,r};return M(a,I,p,X.L,X.V,X.H,X.J,X.g)}',
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
const gi = 135;
const block = vm.GI[gi];

function makeParent(seedValues = {}) {
  const p = new vm.Gl();
  for (const slot of block.L || []) {
    p.N(slot);
    p.Nf(slot, seedValues[slot] ?? undefined);
  }
  for (let i = 0; i < 512; i += 1) {
    if (!(i in seedValues)) {
      p.N(i);
      p.Nf(i, undefined);
    }
  }
  return p;
}

function toBuf(x) {
  if (x == null) return null;
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
  for (let i = 0; i < 10; i += 1) {
    if (ks[i] === parseInt(TARGET.slice(i * 2, i * 2 + 2), 16)) s += 1;
  }
  return s;
}

// Authentic args from capture_r135_calls.js bootstrap
const AUTH_A = 91131;
const AUTH_I = 5;

const argSets = [
  [enc, key],
  [body, key],
  [Buffer.concat([body.subarray(0, 4), enc]), key],
  [mod.c, mod.d],
  [Buffer.from(mod.c, "utf8"), Buffer.from(mod.d, "utf8")],
  [new Uint8Array(enc), new Uint8Array(key)],
  [Array.from(enc), Array.from(key)],
  [enc, key, body],
  [key, enc],
  [init.ck, init.sk],
  [globalThis.ck?.f5?.c, globalThis.ck?.f5?.d],
];

const parentVariants = [
  { name: "empty", parent: makeParent() },
  { name: "enc_key_slots", parent: makeParent({ 0: enc, 1: key, 2: body, 3: mod.c, 4: mod.d }) },
  { name: "ck_f5", parent: makeParent({ 0: init.ck.f5, 1: enc, 2: key }) },
];

const results = [];
for (const { name, parent } of parentVariants) {
  for (const [a, I] of [
    [AUTH_A, AUTH_I],
    [104826, 4],
    [3586, 0],
    [33578, 2],
  ]) {
    try {
      const fn = vm.r(gi, a, I, parent);
      for (let ai = 0; ai < argSets.length; ai += 1) {
        const args = argSets[ai];
        let r;
        let err = null;
        try {
          r = fn(...args);
        } catch (e) {
          err = e.message;
          continue;
        }
        const score = scoreResult(r);
        const head = toBuf(r)?.slice(0, 16).toString("hex") ?? null;
        if (score > 0 || head) {
          results.push({ parent: name, a, I, argSet: ai, score, head, err, type: typeof r });
        }
        if (score >= 100) {
          results.sort((x, y) => y.score - x.score);
          const out = { success: true, hit: results[0], all: results.slice(0, 20) };
          fs.writeFileSync(OUT_PATH, JSON.stringify(out, null, 2));
          console.log(JSON.stringify(out, null, 2));
          process.exit(0);
        }
      }
    } catch (e) {
      results.push({ parent: name, a, I, error: e.message });
    }
  }
}

results.sort((a, b) => (b.score || 0) - (a.score || 0));
const out = { success: false, gi, authArgs: [AUTH_A, AUTH_I], results: results.slice(0, 30) };
fs.writeFileSync(OUT_PATH, JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
