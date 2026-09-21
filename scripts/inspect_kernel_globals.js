#!/usr/bin/env node
"use strict";
/** Inspect APIGuard kernel globals after bootstrap for ck/sk decrypt artifacts. */
const fs = require("fs");
const { JSDOM } = require("jsdom");
const canvas = require("canvas");

const init = JSON.parse(fs.readFileSync("/tmp/init.json", "utf8"));
const ckJson = JSON.stringify(init.ck);
let kernel = init.kernel.replace(
  /createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",\[\],(\[\d+(?:,\d+){7}\])/,
  `createEvent("CustomEvent"),["$1","$2",${ckJson},$3`,
);

function nativeFn(name, impl = () => null) {
  Object.defineProperty(impl, "name", { value: name });
  return impl;
}

function summarize(val, depth = 0) {
  if (depth > 2) return typeof val;
  if (val == null) return val;
  if (typeof val === "function") return `[Function ${val.name || "anonymous"}]`;
  if (typeof val === "string") {
    const buf = Buffer.from(val, "latin1");
    const head = buf.slice(0, 4).toString("hex");
    return `str(len=${val.length},head=${head})`;
  }
  if (typeof val !== "object") return val;
  if (Array.isArray(val)) return `Array(${val.length})`;
  const out = {};
  for (const [k, v] of Object.entries(val).slice(0, 30)) {
    out[k] = summarize(v, depth + 1);
  }
  return out;
}

const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
  url: "https://mobile.southwest.com/",
  runScripts: "dangerously",
  beforeParse(w) {
    w.global = {
      nativeAgent: { ios: {}, invoke: nativeFn("invoke", (...a) => a) },
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
                  if (k === "send") return "[]";
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

const script = window.document.createElement("script");
script.textContent = kernel;
window.document.body.appendChild(script);

const interesting = {};
for (const scope of [window, window.global]) {
  if (!scope) continue;
  for (const key of Object.keys(scope)) {
    if (/ck|sk|lua|decrypt|cipher|LN2|module|byte/i.test(key)) {
      interesting[`${scope === window ? "window" : "global"}.${key}`] = summarize(scope[key]);
    }
  }
}

console.log(JSON.stringify({ interesting, hasCallback: typeof window.__callback === "function" }, null, 2));
