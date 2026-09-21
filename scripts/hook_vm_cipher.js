#!/usr/bin/env node
"use strict";
/**
 * Invoke APIGuard kernel VM cipher (GI[127]) on ck module bytes and log output.
 * Patches Gv dispatch to capture fromCharCode outputs during crypto block execution.
 */
const fs = require("fs");
const zlib = require("zlib");
const { JSDOM } = require("jsdom");
const canvas = require("canvas");

const init = JSON.parse(fs.readFileSync("/tmp/init.json", "utf8"));
const mod = init.ck.f5;
const ct = zlib.inflateSync(Buffer.from(mod.c, "base64"));
const enc = ct.subarray(4);
const keyHex = mod.d;

let kernel = init.kernel;
const inject = `
globalThis.__cipherLog=[];
(function(){
  const _fcc=String.fromCharCode;
  let depth=0;
  String.fromCharCode=function(...codes){
    const r=_fcc(...codes);
    if(depth>0 && codes.length>=4){
      globalThis.__cipherLog.push({n:codes.length, head:[...codes.slice(0,8)]});
    }
    return r;
  };
  const _Gv=(${kernel.match(/function Gv\(G\)\{[^}]+\}[^}]+\}/)?.[0] || "null"});
})();
`;
// simpler: patch Gv loop to count opcodes
kernel = kernel.replace(
  "function Gv(G){var X,I;for(;;){",
  'function Gv(G){var X,I;globalThis.__opCount=(globalThis.__opCount||0)+1;for(;;){',
);

function nativeFn(name, impl = () => null) {
  Object.defineProperty(impl, "name", { value: name });
  return impl;
}

const ckJson = JSON.stringify(init.ck);
kernel = kernel.replace(
  /createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",\[\],(\[\d+(?:,\d+){7}\])/,
  `createEvent("CustomEvent"),["$1","$2",${ckJson},$3`,
);

const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
  url: "https://mobile.southwest.com/",
  runScripts: "dangerously",
  beforeParse(w) {
    w.global = {
      nativeAgent: { ios: {}, invoke: nativeFn("invoke", () => null) },
      ck: init.ck,
      sk: init.sk,
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
script.textContent = kernel;
window.document.body.appendChild(script);

console.log(
  JSON.stringify(
    {
      opCount: window.__opCount || 0,
      encHead: [...enc.slice(0, 8)],
      keyHex,
    },
    null,
    2,
  ),
);
