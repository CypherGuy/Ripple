import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

HIT = {
    "service": "auth-service",
    "file_path": "src/clients/downstream.py",
    "matching_lines": [{"line_number": 42, "content": "response = requests.get(url)"}],
    "incident_context": {"incident_id": "DT-4821", "duration_minutes": 47, "estimated_cost": "£23,000"},
    "per_service_history": [],
}

GOOD_FIX = {
    "old_line": "    response = requests.get(url)",
    "new_line": "    response = requests.get(url, timeout=5)",
    "patch": "-    response = requests.get(url)\n+    response = requests.get(url, timeout=5)",
    "fix_explanation": "Added 5s timeout preventing thread pool exhaustion from DT-4821.",
}

MOCK_MR_URL = "https://gitlab.com/demo-org/auth-service/merge_requests/1"


@pytest.fixture
def client():
    from fix_factory.main import app
    return TestClient(app)


# --- evaluate_fix unit tests ---

def test_evaluate_fix_returns_passed_and_rationale():
    from fix_factory.evaluator import evaluate_fix
    result = evaluate_fix(
        HIT,
        GOOD_FIX["patch"],
        _gemini_fn=lambda _: '{"passed": true, "rationale": "Timeout added directly to the failing call."}',
    )
    assert result["passed"] is True
    assert "rationale" in result


def test_evaluate_fix_returns_false_with_rationale_on_fail():
    from fix_factory.evaluator import evaluate_fix
    result = evaluate_fix(
        HIT,
        "no real change",
        _gemini_fn=lambda _: '{"passed": false, "rationale": "Timeout not added to the right line."}',
    )
    assert result["passed"] is False
    assert result["rationale"] != ""


def test_evaluate_fix_returns_evaluated_on_field():
    from fix_factory.evaluator import evaluate_fix
    result = evaluate_fix(
        HIT,
        GOOD_FIX["patch"],
        _gemini_fn=lambda _: '{"passed": true, "rationale": "Sound fix."}',
    )
    assert "evaluated_on" in result
    assert result["evaluated_on"] in ("incident_context", "technical_merit")


def test_evaluate_fix_uses_technical_merit_when_root_cause_missing():
    from fix_factory.evaluator import evaluate_fix
    hit_no_cause = {**HIT, "incident_context": {"incident_id": "DT-4821"}}
    prompts_seen = []
    def capture(prompt):
        prompts_seen.append(prompt)
        return '{"passed": true, "rationale": "Technically sound."}'
    result = evaluate_fix(hit_no_cause, GOOD_FIX["patch"], _gemini_fn=capture)
    assert result["evaluated_on"] == "technical_merit"
    assert "technical merit" in prompts_seen[0].lower()


def test_evaluate_fix_uses_technical_merit_when_root_cause_is_default_string():
    from fix_factory.evaluator import evaluate_fix
    hit_default = {**HIT, "incident_context": {**HIT["incident_context"], "root_cause_summary": "No summary provided."}}
    prompts_seen = []
    def capture(prompt):
        prompts_seen.append(prompt)
        return '{"passed": true, "rationale": "Technically sound."}'
    result = evaluate_fix(hit_default, GOOD_FIX["patch"], _gemini_fn=capture)
    assert result["evaluated_on"] == "technical_merit"


def test_evaluate_fix_technical_merit_prompt_constrains_to_http_calls():
    from fix_factory.evaluator import evaluate_fix
    hit_no_cause = {**HIT, "incident_context": {"incident_id": "DT-4821"}}
    prompts_seen = []
    def capture(prompt):
        prompts_seen.append(prompt)
        return '{"passed": false, "rationale": "Not an HTTP call modification."}'
    evaluate_fix(hit_no_cause, '-BASE_URL = "https://example.com"\n+BASE_URL = {"url": "..."}', _gemini_fn=capture)
    prompt = prompts_seen[0].lower()
    assert "http" in prompt
    assert any(kw in prompt for kw in ["only", "must", "constraint", "function call"])


def test_evaluate_fix_uses_incident_context_when_root_cause_present():
    from fix_factory.evaluator import evaluate_fix
    hit_with_cause = {**HIT, "incident_context": {
        **HIT["incident_context"],
        "root_cause_summary": "Thread pool exhaustion caused by missing HTTP timeout on downstream client.",
    }}
    prompts_seen = []
    def capture(prompt):
        prompts_seen.append(prompt)
        return '{"passed": true, "rationale": "Directly addresses thread pool exhaustion."}'
    result = evaluate_fix(hit_with_cause, GOOD_FIX["patch"], _gemini_fn=capture)
    assert result["evaluated_on"] == "incident_context"
    assert "thread pool" in prompts_seen[0].lower()


# --- run_with_correction scenarios ---

def _always_pass_eval(hit, patch, _gemini_fn=None):
    return {"passed": True, "rationale": "Looks good."}


def _always_fail_eval(hit, patch, _gemini_fn=None):
    return {"passed": False, "rationale": "Fix incomplete."}


def _fix_fn(hit, traces, precedents, _gemini_fn=None):
    return GOOD_FIX.copy()


def test_correction_passes_on_first_iteration():
    from fix_factory.agent import run_with_correction
    result = run_with_correction(
        HIT, [], [],
        _fix_fn=_fix_fn,
        _eval_fn=_always_pass_eval,
        _mr_fn=lambda *a, **kw: MOCK_MR_URL,
        _store_fn=lambda d: None,
    )
    assert result["self_correction_passed"] is True
    assert result["correction_iterations"] == 1
    assert result["mr_url"] == MOCK_MR_URL
    assert result["failure_reason"] is None


def test_correction_fails_once_then_passes():
    from fix_factory.agent import run_with_correction

    call_count = {"n": 0}
    def flaky_eval(hit, patch, _gemini_fn=None):
        call_count["n"] += 1
        if call_count["n"] < 2:
            return {"passed": False, "rationale": "Not quite right."}
        return {"passed": True, "rationale": "Now correct."}

    result = run_with_correction(
        HIT, [], [],
        _fix_fn=_fix_fn,
        _eval_fn=flaky_eval,
        _mr_fn=lambda *a, **kw: MOCK_MR_URL,
        _store_fn=lambda d: None,
    )
    assert result["self_correction_passed"] is True
    assert result["correction_iterations"] == 2
    assert result["mr_url"] == MOCK_MR_URL


def test_correction_fails_all_iterations():
    from fix_factory.agent import run_with_correction
    result = run_with_correction(
        HIT, [], [],
        _fix_fn=_fix_fn,
        _eval_fn=_always_fail_eval,
        _mr_fn=lambda *a, **kw: MOCK_MR_URL,
        _store_fn=lambda d: None,
    )
    assert result["self_correction_passed"] is False
    assert result["correction_iterations"] == 3
    assert result["mr_url"] is None
    assert result["failure_reason"] is not None


def test_correction_handles_exception_in_fix_generation():
    from fix_factory.agent import run_with_correction

    def exploding_fix(hit, traces, precedents, _gemini_fn=None):
        raise RuntimeError("Gemini rate limit exceeded")

    result = run_with_correction(
        HIT, [], [],
        _fix_fn=exploding_fix,
        _eval_fn=lambda *a, **kw: {"passed": False, "rationale": "", "evaluated_on": "technical_merit"},
        _mr_fn=lambda *a, **kw: None,
        _store_fn=lambda d: None,
    )
    assert result["self_correction_passed"] is False
    assert result["failure_reason"] != ""
    assert "Gemini rate limit" in result["failure_reason"]


def test_store_outcome_writes_to_collection():
    from fix_factory.tools.mongodb_outcomes import store_outcome
    col = MagicMock()
    store_outcome({"service": "auth-service", "mr_url": MOCK_MR_URL}, _col=col)
    col.insert_one.assert_called_once()


def test_post_fix_returns_full_result(client):
    with patch("fix_factory.routes.fix.get_incident_traces", return_value=[]), \
         patch("fix_factory.routes.fix.get_fix_precedents", return_value=[]), \
         patch("fix_factory.routes.fix.run_with_correction", return_value={
             **GOOD_FIX,
             "mr_url": MOCK_MR_URL,
             "self_correction_passed": True,
             "correction_iterations": 1,
             "failure_reason": None,
         }):
        r = client.post("/fix", json=HIT)

    assert r.status_code == 200
    body = r.json()
    assert body["mr_url"] == MOCK_MR_URL
    assert body["self_correction_passed"] is True
