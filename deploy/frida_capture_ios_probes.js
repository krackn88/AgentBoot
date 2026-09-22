/**
 * Frida script to capture APIGuard iOS probe request/response pairs.
 *
 * Usage (on jailbroken device or with objection):
 *   frida -U -f com.southwest.iphoneprod -l deploy/frida_capture_ios_probes.js
 *
 * Then trigger a Southwest login in the app. Pairs are printed as JSON lines.
 */
"use strict";

const pairs = [];

function hookWebKit() {
  if (!ObjC.available) {
    console.log("ObjC runtime unavailable");
    return;
  }

  const handler = ObjC.classes.WKScriptMessageHandler;
  if (!handler) {
    console.log("WKScriptMessageHandler not found");
  }

  Interceptor.attach(Module.findExportByName(null, "objc_msgSend"), {
    onEnter(args) {
      try {
        const sel = ObjC.selectorAsString(args[1]);
        if (!sel || sel.indexOf("postMessage") === -1) {
          return;
        }
        const body = new ObjC.Object(args[2]);
        const text = body.toString();
        if (text.indexOf("ios") === -1 || text.indexOf("[") !== 0) {
          return;
        }
        this.probeReq = text;
      } catch (_) {}
    },
    onLeave(retval) {
      if (!this.probeReq) return;
      try {
        const resp = new ObjC.Object(retval).toString();
        pairs.push({ request: JSON.parse(this.probeReq), response: JSON.parse(resp) });
        console.log(JSON.stringify({ type: "probe_pair", pair: pairs[pairs.length - 1] }));
      } catch (_) {}
    },
  });
}

rpc.exports = {
  dump() {
    return pairs;
  },
};

setImmediate(hookWebKit);
