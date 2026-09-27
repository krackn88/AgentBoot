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
    if (typeof ObjC === 'undefined') {
      ctx.log('ObjC not available');
      return { dispose: function () {} };
    }

    const NSURLSession = ObjC.classes.NSURLSession;
    const method = NSURLSession['- dataTaskWithRequest:completionHandler:'];
    Interceptor.attach(method.implementation, {
      onEnter: function (args) {
        const req = new ObjC.Object(args[2]);
        const url = req.URL().absoluteString().toString();
        if (!matches(url)) return;
        const m = req.HTTPMethod().toString();
        AgentBoot.emit('checker:capture', {
          phase: 'request',
          ts: Date.now() / 1000,
          url,
          method: m,
          request_headers: {},
          source: 'ios',
        });
      },
    });

    ctx.emit('ready', { urlPattern });
    return { dispose: function () {} };
  });

  AgentBoot.setActionEnabled(ACTION_ID, true);
})();
