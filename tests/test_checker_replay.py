from gadgetforge.checker.classify import classify_response
from gadgetforge.checker.models import CheckOutcome, CheckerRecipe, ClassifyRule, FlowStep
from gadgetforge.checker.recorder import FlowRecorder
from gadgetforge.checker.replay import parse_combo, run_recipe_check


def test_parse_combo():
    assert parse_combo("a@b.com:secret") == ("a@b.com", "secret")
    assert parse_combo("invalid") is None


def test_classify_hit_token():
    recipe = CheckerRecipe(
        name="t",
        base_url="https://api.test",
        classify=[
            ClassifyRule(
                outcome=CheckOutcome.HIT,
                step_id="login",
                status_codes=[200],
                json_path="accessToken",
            )
        ],
    )
    outcome = classify_response(
        recipe, "login", 200, '{"accessToken":"abc","points":10}'
    )
    assert outcome == CheckOutcome.HIT


def test_recorder_suggest_chain():
    rec = FlowRecorder()
    rec.ingest_capture(
        {
            "phase": "response",
            "url": "https://api.shop.com/api/sessions",
            "method": "GET",
            "status": 200,
            "response_headers": {"Authorization": "Bearer guest"},
            "response_body": "{}",
        }
    )
    rec.ingest_capture(
        {
            "phase": "response",
            "url": "https://api.shop.com/api/auth/login",
            "method": "POST",
            "status": 200,
            "request_body": '{"email":"x@y.com","password":"pw"}',
            "response_body": '{"accessToken":"tok123"}',
        }
    )
    recipe = rec.suggest_recipe()
    assert recipe.base_url == "https://api.shop.com"
    assert len(recipe.steps) >= 2
    login = next(s for s in recipe.steps if "login" in s.id)
    assert login.body_template
    assert "{{email}}" in str(login.body_template)


def test_run_recipe_mock():
    import httpx

    recipe = CheckerRecipe(
        name="mock",
        base_url="https://api.test",
        steps=[
            FlowStep(id="login", method="POST", path="/login", body_template={"email": "{{email}}", "password": "{{password}}"}),
        ],
        classify=[
            ClassifyRule(
                outcome=CheckOutcome.HIT,
                step_id="login",
                status_codes=[200],
                json_path="ok",
            )
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "points": 5})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    result = run_recipe_check(recipe, "u@e.com", "pass", client=client)
    assert result.outcome == CheckOutcome.HIT
