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
const enc = [...body.subarray(4)];
const PREFIX = Buffer.from("X-dUblrIiu-", "utf8");

function shiftSeed(seed) {
  const k = Buffer.from(seed);
  for (let i = 0; i < Math.min(PREFIX.length, k.length); i += 1) k[i] ^= PREFIX[i];
  return k;
}
const keyS = [...shiftSeed(Buffer.from(mod.d, "hex"))];

const preamble = `window.__dec={n:0,hits:[],enc:${JSON.stringify(enc)},keyS:${JSON.stringify(keyS)},body:${JSON.stringify([...body])},modC:${JSON.stringify(mod.c)},modD:${JSON.stringify(mod.d)}};
function __describe(v){
  if(v==null)return {type:'null'};
  var t=typeof v;
  if(t==='string')return {type:t,len:v.length,head:[].map.call(v.slice(0,8),function(c){return c.charCodeAt(0).toString(16).padStart(2,'0');}).join('')};
  if(v&&v.length!=null&&typeof v!=='function'){
    var a=[].slice.call(v,0,8).map(function(b){return (b&255).toString(16).padStart(2,'0');}).join('');
    return {type:'bytes',len:v.length,head:a,lj:a.indexOf('1b4c4a')===0};
  }
  if(t==='object'){
    var o={type:'object',keys:Object.keys(v).slice(0,12)};
    if(v.c&&typeof v.c==='string') o.cHead=v.c.slice(0,16);
    if(v.d&&typeof v.d==='string') o.dHead=v.d.slice(0,16);
    if(v.c&&v.d){ o.note='ck-entry'; }
    return o;
  }
  return {type:t};
}
`;

let k =
  preamble +
  init.kernel.replace(
    /createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",\[\],(\[\d+(?:,\d+){7}\])/,
    `createEvent("CustomEvent"),["$1","$2",${ckJson},$3`,
  );

k = k.replace(
  'function r(G,a,I,p){"use strict";var X=GI[G];return M(a,I,p,X.L,X.V,X.H,X.J,X.g)}',
  `function r(G,a,I,p){"use strict";var X=GI[G];
if(G===135){
  window.__dec.n++;
  var fn=M(a,I,p,X.L,X.V,X.H,X.J,X.g);
  if(typeof fn==='function'){
    var encU8=new Uint8Array(window.__dec.enc);
    var keyU8=new Uint8Array(window.__dec.keyS);
    var bodyU8=new Uint8Array(window.__dec.body);
    var sets=[
      ['enc+keyU8',[encU8,keyU8]]
    ];
    for(var si=0;si<sets.length;si++){
      try{
        var rv=fn.apply(null,sets[si][1]);
        window.__dec.hits.push({name:sets[si][0],out:__describe(rv)});
      }catch(e){window.__dec.hits.push({name:sets[si][0],err:e.message});}
    }
  }
  return fn;
}
return M(a,I,p,X.L,X.V,X.H,X.J,X.g)}`,
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

const out = {
  n: window.__dec?.n,
  hits: window.__dec?.hits,
  success: (window.__dec?.hits || []).some((h) => h.out?.lj),
};
fs.writeFileSync("/tmp/r135_inline_decrypt.json", JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
