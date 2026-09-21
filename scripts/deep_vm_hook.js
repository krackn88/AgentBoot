#!/usr/bin/env node
"use strict";
/** Deep-hook GI[135]: log NP tails during cipher execution and brute-force op63 sites. */
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

let kernel = init.kernel.replace(
  /createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",\[\],(\[\d+(?:,\d+){7}\])/,
  `createEvent("CustomEvent"),["$1","$2",${ckJson},$3`,
);

const HOOK = `
window.__deep={np:[],fcc:[],in135:false,tried:[]};
(function(){
  const o=String.fromCharCode;
  String.fromCharCode=function(...codes){
    if(window.__deep.in135&&codes.length>=4){
      const hex=codes.slice(0,16).map(c=>(c&255).toString(16).padStart(2,'0')).join('');
      window.__deep.fcc.push({len:codes.length,hex});
    }
    return o(...codes);
  };
})();
`;

kernel = HOOK + kernel;
kernel = kernel.replace(
  'function r(G,a,I,p){"use strict";var X=GI[G];return M(a,I,p,X.L,X.V,X.H,X.J,X.g)}',
  'function r(G,a,I,p){"use strict";var X=GI[G];if(!window.__vmRef)window.__vmRef={Gv,GY,GI,A,Gl,Gt,GC,Q,b,z,M,GU,C,r};return M(a,I,p,X.L,X.V,X.H,X.J,X.g)}',
);
kernel = kernel.replace(
  "function Gv(G){var X,I;for(;;){",
  "function Gv(G){var X,I;if(window.__deep.in135&&G.NP&&G.NP.length>=16){var tail=G.NP.slice(-16);if(tail.every(function(v){return typeof v==='number'&&(v>>>0)===v;})){window.__deep.np.push({pc:G.Z,op:G.l,words:tail.map(function(v){return v>>>0;})});}}for(;;){",
);

const driver = `
;(function(){
  var vm=window.__vmRef; if(!vm) return;
  var gi=135, block=vm.GI[gi];
  var enc=new Uint8Array(${JSON.stringify([...enc])});
  var keyS=new Uint8Array(${JSON.stringify([...keyS])});
  var bodyBuf=new Uint8Array(${JSON.stringify([...body])});
  var p=new vm.Gl();
  for(var i=0;i<512;i++){p.N(i);p.Nf(i,undefined);}
  for(var si=0;si<256;si++){p.Nf(si,enc);p.Nf(si+256,keyS);}
  var Q=vm.Q, sites=[];
  for(var i=0;i<Q.length-1;i++) if((Q[i]|(Q[i+1]<<8))===135) sites.push(i);
  window.__deep.sites=sites.length;
  var argSets=[[enc,keyS],[bodyBuf,keyS],[enc,keyS,bodyBuf],[mod.c,mod.d]];
  for(var si=0;si<sites.length;si++){
    var pos=sites[si];
    for(var zi=0;zi<4;zi++){
      var z=[pos-2,pos-4,pos-6,pos-8][zi];
      if(z<0||z+3>=Q.length) continue;
      if((Q[z+2]|(Q[z+3]<<8))!==135) continue;
      var a=Q[z+1], I=Q[z];
      try{
        window.__deep.in135=true;
        var fn=vm.r(gi,a,I,p);
        for(var ai=0;ai<argSets.length;ai++){
          try{
            var r=fn.apply(null,argSets[ai]);
            if(r!=null){
              var head='';
              if(typeof r==='string') head=[].map.call(r.slice(0,8),function(c){return c.charCodeAt(0).toString(16).padStart(2,'0');}).join('');
              window.__deep.tried.push({pos:pos,a:a,I:I,ai:ai,type:typeof r,head:head});
            }
          }catch(e){ window.__deep.tried.push({pos:pos,a:a,I:I,ai:ai,err:e.message}); }
        }
      }catch(e){ window.__deep.tried.push({pos:pos,err:e.message}); }
      finally{ window.__deep.in135=false; }
    }
  }
})();
`.replace("mod.c", JSON.stringify(mod.c)).replace("mod.d", JSON.stringify(mod.d));

kernel += driver;

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
    w.webkit = { messageHandlers: { send: { postMessage: nativeFn("postMessage", () => "[]") } } };
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

const out = {
  npCaptures: window.__deep?.np?.length || 0,
  fccCaptures: window.__deep?.fcc?.length || 0,
  npSample: (window.__deep?.np || []).slice(0, 8),
  fccSample: (window.__deep?.fcc || []).slice(0, 8),
  triedCount: window.__deep?.tried?.length || 0,
  triedSample: (window.__deep?.tried || []).slice(0, 15),
  sites: window.__deep?.sites || 0,
};
fs.writeFileSync("/tmp/deep_vm_hook.json", JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
