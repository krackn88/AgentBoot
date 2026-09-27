'use strict';

/**
 * AgentBoot runtime — fine-grained hook control via RPC.
 * Actions register with registerAction(id, factory) and can be toggled from the UI.
 */
(function () {
  const actions = new Map();
  const state = { version: 1, actions: {} };

  function emit(event, payload) {
    try {
      send({ type: 'agentboot', event, payload, ts: Date.now() });
    } catch (_) {}
  }

  function registerAction(id, factory) {
    if (actions.has(id)) return;
    actions.set(id, { factory, instance: null, enabled: false });
    state.actions[id] = { enabled: false };
    emit('action_registered', { id });
  }

  function setActionEnabled(id, enabled) {
    const entry = actions.get(id);
    if (!entry) {
      emit('error', { message: 'Unknown action: ' + id });
      return false;
    }
    if (enabled === entry.enabled) return true;
    if (enabled) {
      try {
        entry.instance = entry.factory({
          emit: (ev, data) => emit(id + ':' + ev, data),
          log: (msg) => emit('log', { action: id, message: String(msg) }),
        });
        entry.enabled = true;
        state.actions[id].enabled = true;
        emit('action_enabled', { id });
      } catch (e) {
        emit('error', { action: id, message: String(e) });
        entry.instance = null;
        entry.enabled = false;
        state.actions[id].enabled = false;
        return false;
      }
    } else {
      try {
        if (entry.instance && typeof entry.instance.dispose === 'function') {
          entry.instance.dispose();
        }
      } catch (_) {}
      entry.instance = null;
      entry.enabled = false;
      state.actions[id].enabled = false;
      emit('action_disabled', { id });
    }
    return true;
  }

  rpc.exports = {
    ping: function () {
      return { ok: true, runtime: 'agentboot', version: state.version };
    },
    listActions: function () {
      return Object.keys(state.actions).map((id) => ({
        id,
        enabled: state.actions[id].enabled,
      }));
    },
    setAction: function (id, enabled) {
      return setActionEnabled(id, !!enabled);
    },
    getState: function () {
      return state;
    },
  };

  globalThis.AgentBoot = {
    registerAction,
    setActionEnabled,
    emit,
  };

  emit('runtime_ready', { version: state.version });
})();
