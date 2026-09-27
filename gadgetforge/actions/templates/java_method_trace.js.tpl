// Action: {{ACTION_ID}}
(function () {
  const ACTION_ID = '{{ACTION_ID}}';
  const className = '{{className}}';
  const methodFilter = '{{methodName}}';

  AgentBoot.registerAction(ACTION_ID, function (ctx) {
    let hooks = [];
    const dispose = function () {
      hooks.forEach((h) => {
        try {
          h.detach();
        } catch (_) {}
      });
      hooks = [];
    };

    Java.perform(function () {
      try {
        const Klass = Java.use(className);
        const methods = Klass.class.getDeclaredMethods();
        methods.forEach(function (m) {
          const name = m.getName();
          if (methodFilter !== '*' && name !== methodFilter) return;
          const overloads = Klass[name].overloads;
          overloads.forEach(function (ovl) {
            const hook = ovl.implementation;
            ovl.implementation = function () {
              ctx.log('enter ' + className + '.' + name);
              const ret = hook.apply(this, arguments);
              ctx.log('leave ' + className + '.' + name);
              return ret;
            };
            hooks.push(ovl);
          });
        });
        ctx.emit('ready', { className, methodFilter });
      } catch (e) {
        ctx.log('setup failed: ' + e);
      }
    });

    return { dispose };
  });
})();
