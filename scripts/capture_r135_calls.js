#!/usr/bin/env node
"use strict";
/**
 * Capture authentic r(135, a, I, parent) calls during APIGuard bootstrap + token callback.
 * Logs parent-frame slot values at each GI[135] invocation for later replay.
 */
const fs = require("fs");
const zlib = require("zlib");
const { JSDOM } = require("jsdom");
const canvas = require("canvas");
const { createProbeHandler, parseInitArgs } = require("../southwest_checker/apiguard/probe_handler");

const INIT_PATH = process.env.SW_INIT_JSON || "/tmp/init.json";
const OUT_PATH = process.env.R135_OUT || "/tmp/r135_calls.json";

const init = JSON.parse(fs.readFileSync(INIT_PATH, "utf8"));
const ckJson = JSON.stringify(init.ck || {});

function nativeFn(name, impl = () => null) {
  Object.defineProperty(impl, "name", { value: name });
  return impl;
}

function patchKernel(kernel) {
  let k = kernel.replace(
    /createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",\[\],(\[\d+(?:,\d+){7}\])/,
    `createEvent("CustomEvent"),["$1","$2",${ckJson},$3`,
  );

  const hook = `
window.__r135Log={calls:[],gvSteps:0,gi135Steps:0};
window.__vmRef=null;
function __parentSlots(p, slots){
  const out={};
  if(!p||typeof p.Nf!=='function') return out;
  for(const s of slots){
    try{ out[s]=p.Nf(s); }catch(e){ out[s]=String(e.message); }
  }
  return out;
}
`;

  k = hook + k;

  k = k.replace(
    'function r(G,a,I,p){"use strict";var X=GI[G];return M(a,I,p,X.L,X.V,X.H,X.J,X.g)}',
    `function r(G,a,I,p){"use strict";var X=GI[G];
if(G===135){
  var entry={gi:G,a:a,I:I,stack:(new Error()).stack.split('\\n').slice(1,4)};
  try{
    entry.slots=__parentSlots(p,[a,I,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]);
    entry.slotTypes={};
    for(var sk in entry.slots){
      var v=entry.slots[sk];
      entry.slotTypes[sk]=v==null?'null':(Array.isArray(v)?'array':(v instanceof Uint8Array?'u8':typeof v));
    }
  }catch(e){ entry.slotErr=e.message; }
  window.__r135Log.calls.push(entry);
}
if(!window.__vmRef)window.__vmRef={Gv,GY,GI,A,Gl,Gt,GC,Q,b,z,M,GU,C,r};
return M(a,I,p,X.L,X.V,X.H,X.J,X.g)}`,
  );

  k = k.replace(
    "function Gv(G){var X,I;for(;;){",
    `function Gv(G){var X,I;
if(G.l===135)window.__r135Log.gi135Steps+=1;
window.__r135Log.gvSteps+=1;
for(;;){`,
  );

  return k;
}

const initArgs = parseInitArgs(init.kernel);
const computeProbe = createProbeHandler(init.sk, "native-sess-all", init, initArgs);

const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
  url: "https://mobile.southwest.com/",
  runScripts: "dangerously",
  pretendToBeVisual: true,
  beforeParse(w) {
    w.global = {
      nativeAgent: {
        ios: {},
        invoke: nativeFn("invoke", () => null),
      },
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
  Object.assign(window.document.createElement("script"), {
    textContent: patchKernel(init.kernel),
  }),
);

const bootstrapCalls = window.__r135Log?.calls?.length || 0;

if (typeof window.__callback === "function") {
  window.__callback("POST", "https://mobile.southwest.com/api/security/v4/security/token");
}

// Try invoking ck module names on global if exposed
const postCk = {};
if (window.global?.ck) {
  for (const name of Object.keys(window.global.ck).slice(0, 4)) {
    postCk[name] = typeof window.global.ck[name];
  }
}

const out = {
  bootstrapCalls,
  totalCalls: window.__r135Log?.calls?.length || 0,
  gvSteps: window.__r135Log?.gvSteps || 0,
  gi135Steps: window.__r135Log?.gi135Steps || 0,
  calls: (window.__r135Log?.calls || []).slice(0, 30),
  globalCkTypes: postCk,
  hasCallback: typeof window.__callback === "function",
};

fs.writeFileSync(OUT_PATH, JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
