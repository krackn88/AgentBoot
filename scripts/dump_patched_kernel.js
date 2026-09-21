#!/usr/bin/env node
const fs = require("fs");
const init = JSON.parse(fs.readFileSync("/tmp/init.json", "utf8"));
const ckJson = JSON.stringify(init.ck || {});
const mod = init.ck.f5;
const preamble = `window.__dec={n:0,hits:[],modC:${JSON.stringify(mod.c)},modD:${JSON.stringify(mod.d)}};
function __toHex(x){if(x==null)return null;if(typeof x==='string')return [].map.call(x.slice(0,8),function(c){return c.charCodeAt(0).toString(16).padStart(2,'0');}).join('');return null;}
`;
let k = preamble + init.kernel.replace(
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
    try{ var rv=fn(window.__dec.modC,window.__dec.modD); window.__dec.hits.push({head:__toHex(rv)}); }catch(e){window.__dec.hits.push({err:e.message});}
  }
  return fn;
}
return M(a,I,p,X.L,X.V,X.H,X.J,X.g)}`,
);
fs.writeFileSync("/tmp/patched_kernel.js", k);
console.log("wrote", k.length, "bytes");
