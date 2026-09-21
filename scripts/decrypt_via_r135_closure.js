#!/usr/bin/env node
"use strict";
const fs = require("fs");
const zlib = require("zlib");
const { JSDOM } = require("jsdom");
const canvas = require("canvas");

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
  if (typeof x === "string") {
    return [...x.slice(0, 8)].map((c) => c.charCodeAt(0).toString(16).padStart(2, "0")).join("");
  }
  if (x.length != null) {
    return [...x.slice(0, 8)].map((b) => (b & 255).toString(16).padStart(2, "0")).join("");
  }
  return null;
}

let k = `window.__cap={fn:null,a:0,I:0};\n${init.kernel.replace(
  /createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",\[\],(\[\d+(?:,\d+){7}\])/,
  `createEvent("CustomEvent"),["$1","$2",${ckJson},$3`,
)}`;
k = k.replace(
  'function r(G,a,I,p){"use strict";var X=GI[G];return M(a,I,p,X.L,X.V,X.H,X.J,X.g)}',
  'function r(G,a,I,p){"use strict";var X=GI[G];if(G===135){var fn=M(a,I,p,X.L,X.V,X.H,X.J,X.g);window.__cap.fn=fn;window.__cap.a=a;window.__cap.I=I;return fn;}return M(a,I,p,X.L,X.V,X.H,X.J,X.g);}',
);

const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
  url: "https://mobile.southwest.com/",
  runScripts: "dangerously",
  beforeParse(w) {
    w.global = { nativeAgent: { ios: {}, invoke: function () { return null; } }, ck: init.ck, sk: init.sk };
    w.webkit = { messageHandlers: { send: { postMessage: function () { return "[]"; } } } };
  },
});

const { window } = dom;
window.HTMLCanvasElement.prototype.getContext = function () {
  return canvas.createCanvas(1, 1).getContext("2d");
};
window.document.body.appendChild(Object.assign(window.document.createElement("script"), { textContent: k }));

const fn = window.__cap.fn;
const attempts = [];
const sets = [
  ["enc+key_u8", [new Uint8Array(enc), new Uint8Array(keyS)]],
  ["body+key_u8", [new Uint8Array(body), new Uint8Array(keyS)]],
  ["mod_c+d", [mod.c, mod.d]],
  ["f5+keyS", [init.ck.f5, keyS]],
];

if (typeof fn === "function") {
  for (const [name, args] of sets) {
    try {
      const r = fn(...args);
      attempts.push({ name, type: typeof r, head: toHex(r), lj: toHex(r)?.startsWith("1b4c4a") });
    } catch (e) {
      attempts.push({ name, err: e.message });
    }
  }
}

const out = {
  captured: { a: window.__cap.a, I: window.__cap.I, hasFn: typeof fn === "function" },
  attempts,
};
fs.writeFileSync("/tmp/r135_closure_decrypt.json", JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
