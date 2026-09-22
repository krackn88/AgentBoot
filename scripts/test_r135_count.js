#!/usr/bin/env node
"use strict";
const fs = require("fs");
const { JSDOM } = require("jsdom");
const canvas = require("canvas");
const init = JSON.parse(fs.readFileSync("/tmp/init.json", "utf8"));
const ckJson = JSON.stringify(init.ck || {});
let k = `window.__cap={n:0};\n` + init.kernel.replace(
  /createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",\[\],(\[\d+(?:,\d+){7}\])/,
  `createEvent("CustomEvent"),["$1","$2",${ckJson},$3`,
);
k = k.replace(
  'function r(G,a,I,p){"use strict";var X=GI[G];return M(a,I,p,X.L,X.V,X.H,X.J,X.g)}',
  'function r(G,a,I,p){"use strict";var X=GI[G];if(G===135)window.__cap.n++;return M(a,I,p,X.L,X.V,X.H,X.J,X.g)}',
);
const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
  url: "https://mobile.southwest.com/",
  runScripts: "dangerously",
  beforeParse(w) {
    w.global = { nativeAgent: { ios: {}, invoke: () => null }, ck: init.ck, sk: init.sk };
    w.webkit = { messageHandlers: { send: { postMessage: () => "[]" } } };
  },
});
const { window } = dom;
window.HTMLCanvasElement.prototype.getContext = () => canvas.createCanvas(1, 1).getContext("2d");
window.document.body.appendChild(Object.assign(window.document.createElement("script"), { textContent: k }));
console.log("count", window.__cap.n);
