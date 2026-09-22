#!/usr/bin/env node
"use strict";
/** Observe r(135) during bootstrap: capture return fn, parent slots before/after, try decrypt. */
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

function slotTypes(p, max = 64) {
  const d = {};
  for (let i = 0; i < max; i += 1) {
    try {
      const v = p.Nf(i);
      if (v == null) continue;
      d[i] = typeof v === "function" ? "fn" : typeof v;
    } catch {
      /* ignore */
    }
  }
  return d;
}

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

let kernel = init.kernel.replace(
  /createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",\[\],(\[\d+(?:,\d+){7}\])/,
  `createEvent("CustomEvent"),["$1","$2",${ckJson},$3`,
);

const encArr = JSON.stringify([...enc]);
const keyArr = JSON.stringify([...keyS]);
const bodyArr = JSON.stringify([...body]);

kernel = `window.__obs=[];\n` + kernel;
kernel = kernel.replace(
  'function r(G,a,I,p){"use strict";var X=GI[G];return M(a,I,p,X.L,X.V,X.H,X.J,X.g)}',
  `function r(G,a,I,p){"use strict";var X=GI[G];
if(!window.__vmRef)window.__vmRef={Gv,GY,GI,A,Gl,Gt,GC,Q,b,z,M,GU,C,r};
if(G===135){
  var before=__slotTypes(p);
  var fn=M(a,I,p,X.L,X.V,X.H,X.J,X.g);
  var after=__slotTypes(p);
  var entry={a:a,I:I,before:before,after:after,fnType:typeof fn};
  if(typeof fn==='function'){
    var tries=[];
    var enc=new Uint8Array(${encArr});
    var keyS=new Uint8Array(${keyArr});
    var bodyBuf=new Uint8Array(${bodyArr});
    [[enc,keyS],[bodyBuf,keyS]].forEach(function(args,idx){
      try{ var rv=fn.apply(null,args); tries.push({idx:idx,type:typeof rv,head:__toHex(rv)}); }catch(e){ tries.push({idx:idx,err:e.message}); }
    });
    entry.tries=tries;
  }
  window.__obs.push(entry);
  return fn;
}
return M(a,I,p,X.L,X.V,X.H,X.J,X.g);`,
);

kernel = kernel.replace(
  "window.__obs=[];",
  `window.__obs=[];
function __slotTypes(p,max){
  max=max||64; var d={};
  for(var i=0;i<max;i++){ try{ var v=p.Nf(i); if(v!=null) d[i]=typeof v==='function'?'fn':typeof v; }catch(e){} }
  return d;
}
function __toHex(x){
  if(x==null)return null;
  if(typeof x==='string') return [].map.call(x.slice(0,8),function(c){return c.charCodeAt(0).toString(16).padStart(2,'0');}).join('');
  if(x.length!=null) return [].slice.call(x,0,8).map(function(b){return (b&255).toString(16).padStart(2,'0');}).join('');
  return null;
}`,
);

function nativeFn(name, impl = () => null) {
  Object.defineProperty(impl, "name", { value: name });
  return impl;
}

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
      messageHandlers: { send: { postMessage: nativeFn("postMessage", () => "[]") } },
    };
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

const out = { observations: window.__obs || [] };
fs.writeFileSync("/tmp/r135_observe.json", JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
