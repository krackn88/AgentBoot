from gadgetforge.gadget_config import GadgetConfig, ListenInteraction, default_listen_config


def test_default_listen():
    cfg = default_listen_config()
    assert cfg.interaction.type == "listen"
    assert cfg.interaction.port == 27042


def test_json_roundtrip():
    cfg = GadgetConfig(interaction=ListenInteraction(on_load="resume"))
    parsed = cfg.model_dump(mode="json")
    assert parsed["interaction"]["on_load"] == "resume"
