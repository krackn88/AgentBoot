#!/usr/bin/env node
"use strict";
/**
 * Extract APIGuard D-variant ChaCha-CFB parameters at runtime from /tmp/init.json kernel.
 *
 * Hooks VM dispatch (Gv), byte conversions, and Uint32Array writes; invokes the
 * D cipher VM function GI[127] (runtime GI[135]) via r(G,a,I,p); scans bytecode
 * call sites; and runs a bounded ChaCha search against the f5 known-plaintext anchor.
 *
 * Writes /tmp/d_cipher_findings.json and exits within 10 seconds.
 */
const fs = require("fs");
const zlib = require("zlib");
const { JSDOM } = require("jsdom");
const canvas = require("canvas");

const INIT_PATH = process.env.SW_INIT_JSON || "/tmp/init.json";
const OUT_PATH = "/tmp/d_cipher_findings.json";
const TIMEOUT_MS = Number(process.env.D_CIPHER_TIMEOUT_MS || 10000);

const PREFIX = Buffer.from("X-dUblrIiu-", "utf8");
const LJ_HEADER = Buffer.from("1b4c4a02000000000000", "hex");
const TARGET_KS_PREFIX = "51859262afb3edb6b357";
const VM_CRYPTO_STATIC_INDEX = 127;
const VM_CRYPTO_OFFSET = 45305;

const E_PARAMS = {
  constants: { 0: 0x2efb4565, 1: 0x4cda8c75, 2: 0xbc0768d6, 3: 0xf052c889, 4: 0x2b2f51a2, 9: 0x8627e318, 11: 0xae7324e8, 13: 0x34c382cc },
  keyLayout: [[5, 12], [6, 16], [7, 0], [8, 24], [10, 20], [12, 8], [14, 28], [15, 4]],
  rotations: [18, 13, 11, 4],
  doubleRounds: 11,
  schedule: [[3, 1, 0, 2], [4, 5, 7, 6], [10, 11, 9, 8], [12, 15, 14, 13], [0, 7, 11, 12], [2, 6, 10, 14], [3, 5, 9, 13], [1, 4, 8, 15]],
  counterIndex: 15,
  counterAdd: 68,
};

const POOL_WINDOWS = [
  [3626208099, 3022957240, 3237332618, 92629711, 1465041174, 260493787, 2902037745, 397208795],
  [1615452909, 784054202, 817987752, 453530294, 709842148, 644128859, 4198458437, 1643968964],
  [1643968964, 2013989403, 536870911, 2315245188, 1342646579, 1028213265, 1633026571, 1875227069],
  [1432042122, 371880221, 3925374456, 2910793789, 62232978, 1913507172, 69747568, 2153858718],
];

const CONST_INDEX_PATTERNS = [
  [0, 1, 2, 3, 4, 9, 11, 13],
  [1, 2, 3, 4, 8, 13, 14, 15],
  [2, 3, 6, 7, 8, 13, 14, 15],
  [0, 1, 2, 3, 4, 5, 6, 7],
  [8, 9, 10, 11, 12, 13, 14, 15],
];

function shiftSeed(seed) {
  const key = Buffer.from(seed);
  for (let i = 0; i < Math.min(PREFIX.length, key.length); i += 1) {
    key[i] ^= PREFIX[i];
  }
  return key;
}

function rotl(x, n) {
  x &= 0xffffffff;
  return ((x << n) | (x >>> (32 - n))) >>> 0;
}

function readU32LE(buf, off) {
  return buf.readUInt32LE(off);
}

function initState(key, params) {
  const state = new Array(16).fill(0);
  for (const [idx, val] of Object.entries(params.constants)) {
    state[idx] = val >>> 0;
  }
  for (const [idx, off] of params.keyLayout) {
    state[idx] = readU32LE(key, off);
  }
  return state;
}

function quarterRound(x, a, b, c, d, rots) {
  const [r0, r1, r2, r3] = rots;
  x[a] = (x[a] + x[b]) >>> 0;
  x[d] = rotl(x[d] ^ x[a], r0);
  x[c] = (x[c] + x[d]) >>> 0;
  x[b] = rotl(x[b] ^ x[c], r1);
  x[a] = (x[a] + x[b]) >>> 0;
  x[d] = rotl(x[d] ^ x[a], r2);
  x[c] = (x[c] + x[d]) >>> 0;
  x[b] = rotl(x[b] ^ x[c], r3);
}

function chachaBlock(state, params) {
  const x = state.slice();
  for (let i = 0; i < params.doubleRounds; i += 1) {
    for (const [a, b, c, d] of params.schedule) {
      quarterRound(x, a, b, c, d, params.rotations);
    }
  }
  const out = Buffer.alloc(64);
  for (let i = 0; i < 16; i += 1) {
    out.writeUInt32LE((x[i] + state[i]) >>> 0, i * 4);
  }
  return out;
}

function cfbKeystreamPrefix(ciphertext, plaintext) {
  const out = Buffer.alloc(plaintext.length);
  for (let i = 0; i < plaintext.length; i += 1) {
    const fb = i === 0 ? 0 : plaintext[i - 1];
    out[i] = ciphertext[i] ^ plaintext[i] ^ fb;
  }
  return out;
}

function scoreKeystream(generated, target) {
  let score = 0;
  for (let i = 0; i < Math.min(generated.length, target.length); i += 1) {
    if (generated[i] === target[i]) score += 1;
  }
  return score;
}

function boundedSearch(targetKs, key) {
  const bases = { E: E_PARAMS };
  const rots = [[16, 12, 8, 7], [18, 13, 11, 4], [17, 18, 13, 6], [19, 14, 3, 10]];
  const hits = [];
  for (const [baseName, base] of Object.entries(bases)) {
    for (const rot of rots) {
      for (let dr = Math.max(6, base.doubleRounds - 3); dr <= base.doubleRounds + 3; dr += 1) {
        for (let ca = Math.max(0, base.counterAdd - 16); ca <= base.counterAdd + 16; ca += 1) {
          for (let ci = 0; ci < 16; ci += 1) {
            const params = { ...base, rotations: rot, doubleRounds: dr, counterIndex: ci, counterAdd: ca };
            const ks = chachaBlock(initState(key, params), params);
            const score = scoreKeystream(ks, targetKs);
            if (score >= 3) {
              hits.push({ score, baseName, rotations: rot, doubleRounds: dr, counterIndex: ci, counterAdd: ca, head: ks.slice(0, 10).toString("hex") });
            }
          }
        }
      }
    }
  }
  hits.sort((a, b) => b.score - a.score);
  return hits.slice(0, 10);
}

function poolSearch(targetKs, key) {
  const hits = [];
  for (const window of POOL_WINDOWS) {
    for (const idxs of CONST_INDEX_PATTERNS) {
      const constants = {};
      idxs.forEach((idx, i) => {
        constants[idx] = window[i] >>> 0;
      });
      const params = { ...E_PARAMS, constants };
      const ks = chachaBlock(initState(key, params), params);
      const score = scoreKeystream(ks, targetKs);
      if (score >= 4) {
        hits.push({ score, source: "pool", constants, head: ks.slice(0, 10).toString("hex") });
      }
    }
  }
  hits.sort((a, b) => b.score - a.score);
  return hits.slice(0, 10);
}

function extractPoolFromKernel(kernel) {
  const start = kernel.indexOf("4294967296,3735928559");
  if (start < 0) return [];
  const chunk = kernel.substring(start, start + 700);
  const nums = chunk.match(/\d+/g)?.map(Number).filter((n) => n > 1000 && n < 0x100000000) || [];
  return nums.slice(0, 32);
}

function findGiBlocks(kernel) {
  const blocks = [];
  const re = /\{H:\[([^\]]*)\],L:\[([^\]]*)\],V:\[([^\]]*)\]\}/g;
  let m;
  while ((m = re.exec(kernel)) !== null) {
    blocks.push({
      offset: m.index,
      H: m[1] ? m[1].split(",").map(Number) : [],
      L: m[2] ? m[2].split(",").map(Number) : [],
      V: m[3] ? m[3].split(",").map(Number) : [],
    });
  }
  return blocks;
}

function runtimeCryptoIndex(gi) {
  for (let i = 0; i < gi.length; i += 1) {
    const b = gi[i];
    if (b?.V?.includes(96) && b?.V?.includes(159)) return i;
  }
  return null;
}

function denseBytes(q) {
  const bytes = new Uint8Array(q.length);
  for (let i = 0; i < q.length; i += 1) bytes[i] = q[i] || 0;
  return bytes;
}

function gi135CallSites(bytes) {
  const sites = [];
  for (let i = 0; i < bytes.length - 1; i += 1) {
    if ((bytes[i] | (bytes[i + 1] << 8)) === 135) sites.push(i);
  }
  return sites;
}

function candidateAiPairs(bytes, pos) {
  const pairs = [];
  for (const z of [pos, pos - 2, pos - 4, pos + 2]) {
    if (z < 0 || z + 3 >= bytes.length) continue;
    pairs.push([(bytes[z] | (bytes[z + 1] << 8)) & 0xffff, (bytes[z + 2] | (bytes[z + 3] << 8)) & 0xffff]);
  }
  return pairs;
}

function toHexBytes(data) {
  if (data == null) return null;
  if (typeof data === "string") return Buffer.from(data, "latin1").slice(0, 16).toString("hex");
  if (data instanceof Uint8Array || Array.isArray(data)) return Buffer.from(data).slice(0, 16).toString("hex");
  return null;
}

function buildHooks() {
  return `
window.__dFindings={
  states:[],
  keystreams:[],
  u32Sets:[],
  gvSteps:0,
  cipherAttempts:[],
  matches:[],
};
window.__gvHook=function(G){
  window.__dFindings.gvSteps+=1;
  if(!G.NP||G.NP.length<16) return;
  const tail=G.NP.slice(-16);
  if(!tail.every((v)=>typeof v==="number"&&(v>>>0)===v)) return;
  if(!tail.some((v)=>v>0)) return;
  const words=tail.map((v)=>v>>>0);
  window.__dFindings.states.push({pc:G.Z,opMap:G.l,words});
  const hex=words.map((w)=>w.toString(16).padStart(8,"0")).join("");
  if(hex.includes("${TARGET_KS_PREFIX.slice(0, 8)}")) {
    window.__dFindings.matches.push({type:"state",words});
  }
};
(function(){
  const origFcc=String.fromCharCode;
  String.fromCharCode=function(...codes){
    if(codes.length>=4){
      const bytes=codes.slice(0,64).map((c)=>c&255);
      const hex=bytes.map((b)=>b.toString(16).padStart(2,"0")).join("");
      window.__dFindings.keystreams.push({len:codes.length,hex:hex.slice(0,40),bytes:bytes.slice(0,16)});
      if(hex.startsWith("${TARGET_KS_PREFIX.slice(0, 10)}")) {
        window.__dFindings.matches.push({type:"keystream",hex:hex.slice(0,20)});
      }
    }
    return origFcc(...codes);
  };
  const origSet=Uint32Array.prototype.set;
  Uint32Array.prototype.set=function(src,off){
    if(src&&src.length===16){
      const words=[...src].map((v)=>v>>>0);
      window.__dFindings.u32Sets.push({off:off||0,words});
    }
    return origSet.call(this,src,off);
  };
})();
`;
}

function patchKernel(kernel, ck) {
  const ckJson = JSON.stringify(ck || {});
  let patched = buildHooks() + kernel;
  patched = patched.replace(
    /createEvent\("CustomEvent"\),\["([^"]+)","([^"]+)",\[\],(\[\d+(?:,\d+){7}\])/,
    `createEvent("CustomEvent"),["$1","$2",${ckJson},$3`,
  );
  patched = patched.replace(
    'function r(G,a,I,p){"use strict";var X=GI[G];return M(a,I,p,X.L,X.V,X.H,X.J,X.g)};',
    'function r(G,a,I,p){"use strict";var X=GI[G];window.__vm={Gv,GY,GI,A,Gl,Gt,GC,Q,b,z,M,GU,C,r};return M(a,I,p,X.L,X.V,X.H,X.J,X.g)};',
  );
  patched = patched.replace(
    "function Gv(G){var X,I;for(;;){",
    "function Gv(G){var X,I;window.__gvHook&&window.__gvHook(G);for(;;){",
  );
  return patched;
}

function nativeFn(name, impl = () => null) {
  Object.defineProperty(impl, "name", { value: name });
  return impl;
}

function loadSample(init) {
  const modName = "f5";
  const mod = init.ck?.[modName];
  if (!mod) throw new Error("f5 module missing from init.ck");
  const body = zlib.inflateSync(Buffer.from(mod.c, "base64"));
  const prefix = body.subarray(0, 4);
  const ciphertext = body.subarray(4);
  const keyShifted = shiftSeed(Buffer.from(mod.d, "hex"));
  const targetKeystream = cfbKeystreamPrefix(ciphertext, LJ_HEADER);
  return { modName, mod, prefix, ciphertext, keyShifted, targetKeystream };
}

function makeParentFrame(vm, block) {
  const parent = new vm.Gl();
  for (const slot of block.L || []) {
    parent.N(slot);
    parent.Nf(slot, undefined);
  }
  return parent;
}

function tryCipherInvocation(window, sample, giRuntime, giStatic, sites, bytes) {
  const vm = window.__vm;
  if (!vm?.r || giRuntime == null) return [];
  const block = vm.GI[giRuntime];
  const parent = makeParentFrame(vm, block);
  const attempts = [];
  const argSets = [
    [sample.ciphertext, sample.keyShifted],
    [sample.ciphertext, sample.mod.d],
    [Buffer.from(sample.ciphertext), sample.keyShifted],
    [new Uint8Array(sample.ciphertext), new Uint8Array(sample.keyShifted)],
    [Array.from(sample.ciphertext), Array.from(sample.keyShifted)],
    [sample.mod.c, sample.mod.d],
  ];

  const tried = new Set();
  const tryPair = (a, I, source) => {
    const key = `${a},${I}`;
    if (tried.has(key)) return;
    tried.add(key);
    const entry = { giRuntime, giStatic, a, I, source, ok: false };
    try {
      const fn = vm.r(giRuntime, a, I, parent);
      const stepsBefore = window.__dFindings.gvSteps;
      let result;
      let threw = null;
      for (const args of argSets) {
        try {
          result = fn(...args);
          if (result != null) break;
        } catch (err) {
          threw = err.message;
        }
      }
      entry.ok = true;
      entry.gvSteps = window.__dFindings.gvSteps - stepsBefore;
      entry.resultType = typeof result;
      entry.resultHead = toHexBytes(result);
      entry.error = threw;
      if (entry.resultHead?.startsWith("1b4c4a")) entry.luaJit = true;
    } catch (err) {
      entry.error = err.message;
    }
    attempts.push(entry);
  };

  tryPair(0, 0, "direct");
  for (const pos of sites.slice(0, 20)) {
    for (const [a, I] of candidateAiPairs(bytes, pos)) {
      tryPair(a, I, `bytecode@${pos}`);
    }
  }
  return attempts;
}

function summarizeStates(findings) {
  const unique = [];
  const seen = new Set();
  for (const item of [...findings.states, ...findings.u32Sets.map((u) => ({ words: u.words }))]) {
    const words = item.words;
    if (!words || words.length !== 16) continue;
    const key = words.join(",");
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(words);
  }
  return unique.slice(0, 20);
}

function main() {
  const init = JSON.parse(fs.readFileSync(INIT_PATH, "utf8"));
  const kernel = init.kernel || "";
  const sample = loadSample(init);
  const staticBlocks = findGiBlocks(kernel);
  const staticBlock = staticBlocks[VM_CRYPTO_STATIC_INDEX] || null;
  const poolFromKernel = extractPoolFromKernel(kernel);

  const patched = patchKernel(kernel, init.ck);
  const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
    url: "https://mobile.southwest.com/",
    runScripts: "dangerously",
    pretendToBeVisual: true,
    beforeParse(w) {
      w.global = {
        nativeAgent: { ios: {}, invoke: nativeFn("invoke", () => null) },
        ck: init.ck,
        sk: init.sk,
        kernelId: init.kernelId,
      };
      w.webkit = {
        messageHandlers: {
          send: { postMessage: nativeFn("postMessage", () => "[]") },
          pushMinPayload: { postMessage: nativeFn("postMessage", () => {}) },
          pushMaxPayload: { postMessage: nativeFn("postMessage", () => {}) },
        },
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
  script.textContent = patched;
  window.document.body.appendChild(script);

  const bootstrapSteps = window.__dFindings?.gvSteps || 0;
  const giRuntime = runtimeCryptoIndex(window.__vm?.GI || []);
  const bytes = window.__vm?.Q ? denseBytes(window.__vm.Q) : new Uint8Array();
  const sites = gi135CallSites(bytes);

  const cipherAttempts = tryCipherInvocation(
    window,
    sample,
    giRuntime,
    VM_CRYPTO_STATIC_INDEX,
    sites,
    bytes,
  );

  try {
    if (typeof window.__callback === "function") {
      window.__callback("POST", "https://mobile.southwest.com/api/security/v4/security/token");
    }
  } catch {
    /* ignore */
  }

  const boundedHits = boundedSearch(sample.targetKeystream.slice(0, 10), sample.keyShifted);
  const poolHits = poolSearch(sample.targetKeystream.slice(0, 10), sample.keyShifted);
  const states = summarizeStates(window.__dFindings || { states: [], u32Sets: [] });

  const bestCipherAttempts = [...cipherAttempts]
    .sort((a, b) => (b.gvSteps || 0) - (a.gvSteps || 0))
    .slice(0, 12);

  const findings = {
    generatedAt: new Date().toISOString(),
    initPath: INIT_PATH,
    kernelId: init.kernelId || "",
    kernelBytes: kernel.length,
    vmCrypto: {
      staticGiIndex: VM_CRYPTO_STATIC_INDEX,
      runtimeGiIndex: giRuntime,
      fileOffset: staticBlock?.offset ?? VM_CRYPTO_OFFSET,
      staticBlock: staticBlock
        ? { H: staticBlock.H.length, L: staticBlock.L.length, V: staticBlock.V.length, Vhead: staticBlock.V.slice(0, 8) }
        : null,
      runtimeBlock: giRuntime != null
        ? {
            H: window.__vm.GI[giRuntime].H?.length || 0,
            L: window.__vm.GI[giRuntime].L?.length || 0,
            V: window.__vm.GI[giRuntime].V?.length || 0,
          }
        : null,
      bytecodeRefsTo135: sites.length,
      callSitesSample: sites.slice(0, 10),
    },
    f5: {
      prefix: sample.prefix.toString("hex"),
      ciphertextHead: sample.ciphertext.slice(0, 8).toString("hex"),
      dKeyHex: sample.mod.d,
      keyShiftedHex: sample.keyShifted.toString("hex"),
      targetKeystreamPrefix: sample.targetKeystream.slice(0, 10).toString("hex"),
      targetAnchor: TARGET_KS_PREFIX,
    },
    runtime: {
      bootstrapGvSteps: bootstrapSteps,
      totalGvSteps: window.__dFindings?.gvSteps || 0,
      statesCaptured: window.__dFindings?.states?.length || 0,
      u32SetsCaptured: window.__dFindings?.u32Sets?.length || 0,
      keystreamEvents: window.__dFindings?.keystreams?.length || 0,
      matches: window.__dFindings?.matches || [],
      uniqueStates: states,
      keystreamSample: (window.__dFindings?.keystreams || []).slice(0, 10),
      cipherAttemptsTotal: cipherAttempts.length,
      cipherAttemptsBest: bestCipherAttempts,
      decryptedDuringRun: cipherAttempts.some((a) => a.luaJit),
    },
    staticAnalysis: {
      kernelPoolHead: poolFromKernel.slice(0, 16),
      boundedEgTagSearchBest: boundedHits,
      kernelPoolSearchBest: poolHits,
      note: "E/G/TAG mutations and kernel pool windows score <=3/10 for f5 anchor; D params live in VM GI[127]/GI[135].",
    },
    conclusion: {
      targetKeystreamMatched: Boolean(
        (window.__dFindings?.matches || []).some((m) => m.hex?.startsWith(TARGET_KS_PREFIX.slice(0, 10))) ||
          cipherAttempts.some((a) => a.resultHead?.startsWith("1b4c4a")),
      ),
      dParamsExtracted: states.length > 0 || poolHits.some((h) => h.score >= 6),
      recommendation: states.length
        ? "Inspect uniqueStates for 16-word ChaCha state; map constants to CipherParams."
        : "Invoke GI[135] from real ck module load path (lazy decrypt); static GI[127] offset 45305 is sole charCodeAt/fromCharCode block.",
    },
  };

  fs.writeFileSync(OUT_PATH, JSON.stringify(findings, null, 2));
  return findings;
}

let finished = false;
const timer = setTimeout(() => {
  if (!finished) {
    finished = true;
    try {
      const partial = fs.existsSync(OUT_PATH)
        ? JSON.parse(fs.readFileSync(OUT_PATH, "utf8"))
        : { timeout: true, message: "exceeded time budget" };
      partial.timeout = true;
      fs.writeFileSync(OUT_PATH, JSON.stringify(partial, null, 2));
    } catch {
      fs.writeFileSync(OUT_PATH, JSON.stringify({ timeout: true }, null, 2));
    }
    process.exit(0);
  }
}, TIMEOUT_MS);

try {
  const findings = main();
  if (!finished) {
    finished = true;
    clearTimeout(timer);
    console.log(JSON.stringify(findings, null, 2));
    process.exit(0);
  }
} catch (err) {
  if (!finished) {
    finished = true;
    clearTimeout(timer);
    const payload = { error: err.message, stack: err.stack };
    fs.writeFileSync(OUT_PATH, JSON.stringify(payload, null, 2));
    console.error(JSON.stringify(payload, null, 2));
    process.exit(1);
  }
}
