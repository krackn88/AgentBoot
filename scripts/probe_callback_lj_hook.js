#!/usr/bin/env node
"use strict";
/** Full bootstrap + probe callback with fromCharCode hook for LuaJIT decrypt events. */
const fs = require("fs");
const { JSDOM } = require("jsdom");
const canvas = require("canvas");
const { createProbeHandler, parseInitArgs } = require("../southwest_checker/apiguard/probe_handler");

const init = JSON.parse(fs.readFileSync("/tmp/init.json", "utf8"));
const ckJson = JSON.stringify(init.ck || {});

const preamble = `window.__lj={events:[],r135:0};
(function(){
  var o=String.fromCharCode;
  String.fromCharCode=function(){
    var codes=[].map.call(arguments,function(c){return c&255;});
    if(codes.length>=3&&codes[0]===0x1b&&codes[1]===0x4c&&codes[2]===0x4a){
      window.__lj.events.push({kind:'lj',len:codes.length,head:codes.slice(0,16)});
    }
    return o.apply(String,arguments);
  };
})();
`;

let k =
  preamble +
  init.kernel.replace(
    /createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",\[\],(\[\d+(?:,\d+){7}\])/,
    `createEvent("CustomEvent"),["$1","$2",${ckJson},$3`,
  );

k = k.replace(
  'function r(G,a,I,p){"use strict";var X=GI[G];return M(a,I,p,X.L,X.V,X.H,X.J,X.g)}',
  'function r(G,a,I,p){"use strict";var X=GI[G];if(G===135)window.__lj.r135++;return M(a,I,p,X.L,X.V,X.H,X.J,X.g)}',
);

function nativeFn(name, impl) {
  Object.defineProperty(impl, "name", { value: name });
  return impl;
}

const initArgs = parseInitArgs(init.kernel);
const computeProbe = createProbeHandler(init.sk, "native-sess-all", init, initArgs);

const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
  url: "https://mobile.southwest.com/",
  runScripts: "dangerously",
  pretendToBeVisual: true,
  beforeParse(w) {
    w.global = {
      nativeAgent: { ios: {}, invoke: nativeFn("invoke", function () { return null; }) },
      ck: init.ck,
      sk: init.sk,
    };
    w.webkit = {
      messageHandlers: new Proxy(
        {},
        {
          get(t, p) {
            const key = String(p);
            if (!t[key]) {
              t[key] = {
                postMessage: nativeFn("postMessage", function (...args) {
                  if (key === "send") return computeProbe(args[0]);
                  return undefined;
                }),
              };
            }
            return t[key];
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
window.document.body.appendChild(Object.assign(window.document.createElement("script"), { textContent: k }));

if (typeof window.__callback === "function") {
  window.__callback("POST", "https://mobile.southwest.com/api/security/v4/security/token");
}

const out = {
  r135Calls: window.__lj?.r135 || 0,
  ljEvents: window.__lj?.events?.length || 0,
  ljSample: window.__lj?.events?.slice(0, 5) || [],
};
fs.writeFileSync("/tmp/probe_lj_hook.json", JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
