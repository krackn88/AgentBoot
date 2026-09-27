// Action: {{ACTION_ID}}
(function () {
  const ACTION_ID = '{{ACTION_ID}}';
  const moduleName = '{{module}}';
  const exportName = '{{export}}';

  AgentBoot.registerAction(ACTION_ID, function (ctx) {
    const ptr = Module.findExportByName(moduleName, exportName);
    if (!ptr) {
      ctx.log('export not found: ' + moduleName + '!' + exportName);
      return { dispose: function () {} };
    }
    const listener = Interceptor.attach(ptr, {
      onEnter: function (args) {
        ctx.emit('call', { module: moduleName, export: exportName });
      },
    });
    ctx.emit('ready', { module: moduleName, export: exportName });
    return {
      dispose: function () {
        listener.detach();
      },
    };
  });
})();
