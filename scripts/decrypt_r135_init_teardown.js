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

const preamble = `window.__dec={n:0,hits:[],enc:${JSON.stringify(enc)},keyS:${JSON.stringify(keyS)}};
function __hex(v){if(!v||v.length==null)return null;var a=[].slice.call(v,0,8).map(function(b){return (b&255).toString(16).padStart(2,'0');}).join('');return a;}
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
    try{
      var obj=fn(encU8,keyU8);
      if(obj&&typeof obj.init==='function'){
        obj.init();
        window.__dec.hits.push({step:'afterInit',ckF5:global.ck&&global.ck.f5});
      }
      if(obj&&typeof obj.teardown==='function'){
        var td=obj.teardown(encU8,keyU8);
        window.__dec.hits.push({step:'teardown',head:__hex(td),type:typeof td});
      }
    }catch(e){window.__dec.hits.push({err:e.message});}
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

console.log(JSON.stringify({ n: window.__dec?.n, hits: window.__dec?.hits, ckF5: window.global?.ck?.f5 }, null, 2));
