#!/usr/bin/env node
"use strict";
/** Lightweight kernel ck decrypt tracer — hooks byte conversions only. */
const fs = require("fs");
const { JSDOM } = require("jsdom");
const canvas = require("canvas");

const init = JSON.parse(fs.readFileSync("/tmp/init.json", "utf8"));
const ckJson = JSON.stringify(init.ck || {});
let kernel = (init.kernel || "").replace(
  /createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",\[\],(\[\d+(?:,\d+){7}\])/,
  `createEvent("CustomEvent"),["$1","$2",${ckJson},$3`,
);

const hook = `
globalThis.__ckLog=[];
(function(){
  const orig=String.fromCharCode;
  String.fromCharCode=function(...codes){
    if(codes.length>=8 && codes.length<=64 && codes.every(c=>c>=0&&c<=255)){
      const head=codes.slice(0,16);
      if(head[0]===0x1b && head[1]===0x4c && head[2]===0x4a){
        globalThis.__ckLog.push({kind:'lj',head});
      } else if(head[0]===0x10 && head[1]===0x53 && head[2]===0x50){
        globalThis.__ckLog.push({kind:'sp',head});
      } else if(codes.length>=16){
        globalThis.__ckLog.push({kind:'bytes',head, len:codes.length});
      }
    }
    return orig.apply(String,codes);
  };
})();
`;

function nativeFn(name, impl = () => null) {
  Object.defineProperty(impl, "name", { value: name });
  return impl;
}

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
      messageHandlers: new Proxy(
        {},
        {
          get(t, p) {
            const k = String(p);
            if (!t[k]) {
              t[k] = {
                postMessage: nativeFn("postMessage", (...args) => {
                  if (k === "send") {
                    try {
                      return JSON.stringify(JSON.parse(args[0]).map(() => "AA=="));
                    } catch {
                      return "[]";
                    }
                  }
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
window.HTMLCanvasElement.prototype.getContext = function (type) {
  const c = canvas.createCanvas(300, 150);
  return c.getContext("2d");
};

const script = window.document.createElement("script");
script.textContent = hook + kernel;
window.document.body.appendChild(script);

setTimeout(() => {
  const log = window.__ckLog || [];
  console.log(JSON.stringify({ events: log.length, sample: log.slice(0, 20) }, null, 2));
  process.exit(0);
}, 2000);
