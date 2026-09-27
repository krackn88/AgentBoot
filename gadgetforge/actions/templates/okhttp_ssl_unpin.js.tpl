// Action: {{ACTION_ID}}
(function () {
  const ACTION_ID = '{{ACTION_ID}}';
  const startEnabled = {{enabled}};

  AgentBoot.registerAction(ACTION_ID, function (ctx) {
    let patched = false;

    function patch() {
      if (patched) return;
      Java.perform(function () {
        try {
          const ArrayList = Java.use('java.util.ArrayList');
          const Pinning = Java.use('okhttp3.CertificatePinner');
          Pinning.check.overload('java.lang.String', 'java.util.List').implementation = function (a, b) {
            ctx.log('CertificatePinner.check bypassed for ' + a);
            return;
          };
          patched = true;
          ctx.emit('patched', {});
        } catch (e) {
          ctx.log('OkHttp patch failed: ' + e);
        }
      });
    }

    if (startEnabled) patch();

    return {
      enablePinningBypass: patch,
      dispose: function () {
        patched = false;
      },
    };
  });

  if (startEnabled) {
    Java.perform(function () {
      AgentBoot.setActionEnabled(ACTION_ID, true);
    });
  }
})();
