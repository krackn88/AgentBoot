#!/usr/bin/env node
"use strict";
/**
 * Trace APIGuard kernel ck/sk decryption by hooking ChaCha-like byte loops.
 * Logs candidate 16-word state arrays and keystream prefixes when ck modules load.
 */
const fs = require("fs");
const { JSDOM } = require("jsdom");
const canvas = require("canvas");

const init = JSON.parse(fs.readFileSync(process.env.SW_INIT_JSON || "/tmp/init.json", "utf8"));
const ckJson = JSON.stringify(init.ck || {});
let kernel = init.kernel || "";
kernel = kernel.replace(
  /createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",\[\],(\[\d+(?:,\d+){7}\])/,
  `createEvent("CustomEvent"),["$1","$2",${ckJson},$3`,
);

const traces = [];
const byteOps = [];

function nativeFn(name, impl = () => null) {
  const fn = impl;
  Object.defineProperty(fn, "name", { value: name });
  return fn;
}

function hookKernelSource(src) {
  const marker = "function Ge(v,I){";
  if (!src.includes(marker)) {
    return src;
  }
  const inject = `
globalThis.__ckTrace={traces:[],byteOps:[]};
(function(){
  const _fromCC=String.fromCharCode.bind(String);
  const _ccAt=String.prototype.charCodeAt;
  let inCipher=false, buf=[], stateLog=[];
  String.fromCharCode=function(...codes){
    if(inCipher && codes.length>=4 && codes.length<=64){
      globalThis.__ckTrace.traces.push({kind:'fromCharCode',codes:codes.slice(0,16),len:codes.length});
    }
    return _fromCC(...codes);
  };
  const origPush=[].push;
  [].push=function(...args){
    if(args.length===1 && typeof args[0]==='number' && args[0]>=0 && args[0]<=255){
      buf.push(args[0]&255);
      if(buf.length===16){
        globalThis.__ckTrace.byteOps.push({head:buf.slice(0,16),len:globalThis.__ckTrace.byteOps.length});
        buf=[];
      }
    }
    return origPush.apply(this,args);
  };
})();
`;
  return inject + src;
}

const dom = new JSDOM("<!DOCTYPE html><html><body><script nonce='apiguard'></script></body></html>", {
  url: "https://mobile.southwest.com/",
  runScripts: "dangerously",
  pretendToBeVisual: true,
  beforeParse(window) {
    window.global = { nativeAgent: { ios: {}, invoke: nativeFn("invoke", () => null) } };
    window.webkit = {
      messageHandlers: new Proxy(
        {},
        {
          get(target, prop) {
            const key = String(prop);
            if (!target[key]) {
              target[key] = {
                postMessage: nativeFn("postMessage", (...args) => {
                  if (key === "send") {
                    try {
                      const req = JSON.parse(args[0]);
                      return JSON.stringify(req.map(() => Buffer.alloc(16).toString("base64url")));
                    } catch {
                      return "[]";
                    }
                  }
                  return undefined;
                }),
              };
            }
            return target[key];
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
  const c = canvas.createCanvas(this.width || 300, this.height || 150);
  return c.getContext(type === "webgl" || type === "experimental-webgl" ? "webgl" : "2d");
};

const script = window.document.createElement("script");
script.textContent = hookKernelSource(kernel);
window.document.body.appendChild(script);

const start = Date.now();
while (Date.now() - start < 3000) {}

const trace = window.__ckTrace || { traces: [], byteOps: [] };
console.log(
  JSON.stringify(
    {
      fromCharCodeEvents: trace.traces.length,
      byteOpChunks: trace.byteOps.length,
      sampleFromCC: trace.traces.slice(0, 5),
      sampleByteOps: trace.byteOps.slice(0, 10),
    },
    null,
    2,
  ),
);
