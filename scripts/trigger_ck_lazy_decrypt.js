#!/usr/bin/env node
"use strict";
/**
 * Trigger APIGuard ck lazy-decrypt by running full kernel bootstrap + token callback,
 * hooking fromCharCode for LuaJIT headers and logging decrypt artifacts.
 */
const fs = require("fs");
const zlib = require("zlib");
const { JSDOM } = require("jsdom");
const canvas = require("canvas");
const { createProbeHandler, parseInitArgs } = require("../southwest_checker/apiguard/probe_handler");

const init = JSON.parse(fs.readFileSync("/tmp/init.json", "utf8"));
const ckJson = JSON.stringify(init.ck || {});
let kernel = init.kernel.replace(
  /createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",\[\],(\[\d+(?:,\d+){7}\])/,
  `createEvent("CustomEvent"),["$1","$2",${ckJson},$3`,
);

const HOOK = `
window.__decLog={lj:[],fcc:[],events:[]};
(function(){
  const o=String.fromCharCode;
  String.fromCharCode=function(...codes){
    const bytes=codes.map(c=>c&255);
    if(bytes.length>=3 && bytes[0]===0x1b && bytes[1]===0x4c && bytes[2]===0x4a){
      window.__decLog.lj.push({len:bytes.length, head:bytes.slice(0,16)});
    } else if(bytes.length>=8){
      window.__decLog.fcc.push({len:bytes.length, head:bytes.slice(0,16)});
    }
    return o(...codes);
  };
  const od=EventTarget.prototype.dispatchEvent;
  EventTarget.prototype.dispatchEvent=function(ev){
    if(ev&&ev.type) window.__decLog.events.push(ev.type);
    return od.call(this,ev);
  };
})();
`;
kernel = HOOK + kernel;

function nativeFn(name, impl = () => null) {
  Object.defineProperty(impl, "name", { value: name });
  return impl;
}

const initArgs = parseInitArgs(kernel);
const computeProbe = createProbeHandler(init.sk, "native-sess-all", init, initArgs);
const nativeCalls = [];

const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
  url: "https://mobile.southwest.com/",
  runScripts: "dangerously",
  pretendToBeVisual: true,
  beforeParse(w) {
    w.global = {
      nativeAgent: {
        ios: {},
        invoke: nativeFn("invoke", (...args) => {
          nativeCalls.push(args.map((x) => String(x).slice(0, 120)));
          return null;
        }),
      },
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
window.HTMLCanvasElement.prototype.getContext = function () {
  return canvas.createCanvas(1, 1).getContext("2d");
};

window.document.body.appendChild(
  Object.assign(window.document.createElement("script"), { textContent: kernel }),
);

const start = Date.now();
while (Date.now() - start < 2000) {}

if (typeof window.__callback === "function") {
  window.__callback("POST", "https://mobile.southwest.com/api/security/v4/security/token");
}

const log = window.__decLog || {};
const out = {
  ljHits: log.lj?.length || 0,
  ljSample: log.lj?.slice(0, 5) || [],
  fccCount: log.fcc?.length || 0,
  events: log.events || [],
  nativeCalls: nativeCalls.length,
  nativeSample: nativeCalls.slice(0, 5),
};
fs.writeFileSync("/tmp/ck_lazy_decrypt.json", JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
