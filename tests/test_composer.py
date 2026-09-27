from gadgetforge.composer import EnabledAction, compose_script


def test_compose_includes_bootstrap():
    script = compose_script([EnabledAction(id="hook.native_export", enabled=True, params={})])
    assert "AgentBoot" in script
    assert "runtime.bootstrap" in script or "registerAction" in script


def test_compose_native_hook_params():
    script = compose_script(
        [
            EnabledAction(
                id="hook.native_export",
                enabled=True,
                params={"module": "libc.so", "export": "read"},
            )
        ]
    )
    assert "libc.so" in script
    assert "read" in script
