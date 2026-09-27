// Action: {{ACTION_ID}}
(function () {
  const ACTION_ID = '{{ACTION_ID}}';
  const startEnabled = {{enabled}};

  AgentBoot.registerAction(ACTION_ID, function (ctx) {
    let listener = null;

    function install() {
      if (typeof ObjC === 'undefined') {
        ctx.log('ObjC runtime not available');
        return;
      }
      const NSURLSession = ObjC.classes.NSURLSession;
      if (!NSURLSession) {
        ctx.log('NSURLSession not found');
        return;
      }
      const method = NSURLSession['- dataTaskWithRequest:completionHandler:'];
      if (!method) return;
      Interceptor.attach(method.implementation, {
        onEnter: function (args) {
          const req = new ObjC.Object(args[2]);
          const url = req.URL().absoluteString().toString();
          ctx.emit('request', { url });
        },
      });
      ctx.emit('ready', {});
    }

    if (startEnabled) install();

    return {
      dispose: function () {
        if (listener) listener.detach();
      },
    };
  });

  if (startEnabled) {
    AgentBoot.setActionEnabled(ACTION_ID, true);
  }
})();
