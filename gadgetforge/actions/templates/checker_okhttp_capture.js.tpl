// Action: {{ACTION_ID}}
(function () {
  const ACTION_ID = '{{ACTION_ID}}';
  const urlPattern = '{{urlPattern}}';
  const maxBody = {{maxBodyChars}};

  function matches(url) {
    if (!urlPattern || urlPattern === '*') return true;
    try {
      return new RegExp(urlPattern, 'i').test(url);
    } catch (e) {
      return url.indexOf(urlPattern) >= 0;
    }
  }

  function trunc(s) {
    if (!s) return s;
    s = String(s);
    return s.length > maxBody ? s.substring(0, maxBody) + '…' : s;
  }

  AgentBoot.registerAction(ACTION_ID, function (ctx) {
    Java.perform(function () {
      try {
        const RealCall = Java.use('okhttp3.RealCall');
        const execute = RealCall.execute;
        execute.implementation = function () {
          const req = this.request();
          const url = req.url().toString();
          const method = req.method();
          const hit = matches(url);
          if (hit) {
            let reqBody = null;
            try {
              const body = req.body();
              if (body) {
                const OkBuffer = Java.use('okio.Buffer');
                const buffer = OkBuffer.$new();
                body.writeTo(buffer);
                reqBody = buffer.readUtf8();
              }
            } catch (_) {}
            const hdrs = {};
            const rh = req.headers();
            for (let i = 0; i < rh.size(); i++) {
              hdrs[rh.name(i)] = rh.value(i);
            }
            AgentBoot.emit('checker:capture', {
              phase: 'request',
              ts: Date.now() / 1000,
              url,
              method,
              request_headers: hdrs,
              request_body: trunc(reqBody),
              source: 'okhttp',
            });
          }
          const resp = execute.call(this);
          if (hit) {
            const code = resp.code();
            const rhdrs = {};
            const headers = resp.headers();
            for (let i = 0; i < headers.size(); i++) {
              rhdrs[headers.name(i)] = headers.value(i);
            }
            let respBody = null;
            try {
              respBody = resp.peekBody(maxBody).string();
            } catch (_) {}
            AgentBoot.emit('checker:capture', {
              phase: 'response',
              ts: Date.now() / 1000,
              url,
              method,
              status: code,
              response_headers: rhdrs,
              response_body: trunc(respBody),
              source: 'okhttp',
            });
          }
          return resp;
        };
        ctx.emit('ready', { urlPattern });
      } catch (e) {
        ctx.log('OkHttp capture failed: ' + e);
      }
    });

    return { dispose: function () {} };
  });

  Java.perform(function () {
    AgentBoot.setActionEnabled(ACTION_ID, true);
  });
})();
