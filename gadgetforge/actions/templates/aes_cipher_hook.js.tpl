// Action: {{ACTION_ID}}
(function () {
  const ACTION_ID = '{{ACTION_ID}}';
  const startEnabled = {{enabled}};

  AgentBoot.registerAction(ACTION_ID, function (ctx) {
    let hooks = [];

    function install() {
      Java.perform(function () {
        try {
          const Cipher = Java.use('javax.crypto.Cipher');
          const init = Cipher.init.overload('int', 'java.security.Key');
          init.implementation = function (opmode, key) {
            ctx.emit('cipher_init', {
              opmode: opmode,
              algorithm: key.getAlgorithm(),
            });
            return init.call(this, opmode, key);
          };
          hooks.push(init);
          ctx.emit('ready', {});
        } catch (e) {
          ctx.log('AES hook failed: ' + e);
        }
      });
    }

    if (startEnabled) install();

    return {
      dispose: function () {
        hooks = [];
      },
    };
  });

  if (startEnabled) {
    Java.perform(function () {
      AgentBoot.setActionEnabled(ACTION_ID, true);
    });
  }
})();
