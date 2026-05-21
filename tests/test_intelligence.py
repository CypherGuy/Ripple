import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

DT4821_INCIDENTS = [
    {
        "incident_id": "DT-4821",
        "title": "Payment service cascade failure - no timeout on HTTP client",
        "duration_minutes": 47,
        "estimated_cost": "£23,000",
        "root_cause_summary": "HTTP client with no timeout caused thread pool exhaustion under load.",
        "affected_services": ["payment-service", "auth-service", "order-service"],
    }
]

SAMPLE_DIFF = "@@ -12,6 +12,8 @@\n-  timeout=None\n+  response = requests.get(url)"


@pytest.fixture
def client():
    from intelligence.main import app
    return TestClient(app)


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "intelligence"}


def test_analyze_returns_pattern_and_risk_score(client):
    with patch("intelligence.routes.analyze.fetch_incident_history", return_value=DT4821_INCIDENTS), \
            patch("intelligence.routes.analyze.extract_pattern", return_value={
                "pattern": "Synchronous HTTP call with no timeout configured.",
                "risk_score": 9,
                "risk_rationale": "Matches DT-4821 - 47-minute outage.",
                "incident_context": DT4821_INCIDENTS[0],
                "previous_scans": [],
            }):
        r = client.post("/analyze", json={
            "pr_id": "12345",
            "repo": "org/payment-service",
            "diff": SAMPLE_DIFF,
        })
    assert r.status_code == 200
    body = r.json()
    assert body["pattern"] != ""
    assert body["risk_score"] == 9


def test_analyze_pattern_is_non_empty_string(client):
    with patch("intelligence.routes.analyze.fetch_incident_history", return_value=DT4821_INCIDENTS), \
            patch("intelligence.routes.analyze.extract_pattern", return_value={
                "pattern": "Synchronous HTTP call with no timeout configured.",
                "risk_score": 9,
                "risk_rationale": "Matches DT-4821.",
                "incident_context": DT4821_INCIDENTS[0],
                "previous_scans": [],
            }):
        r = client.post("/analyze", json={
            "pr_id": "1",
            "repo": "org/svc",
            "diff": SAMPLE_DIFF,
        })
    assert isinstance(r.json()["pattern"], str)
    assert len(r.json()["pattern"]) > 0


def test_analyze_rejects_missing_diff(client):
    r = client.post("/analyze", json={"pr_id": "1", "repo": "org/svc"})
    assert r.status_code == 422


def test_analyze_rejects_diff_over_65536_chars(client):
    huge_diff = "a" * 65537
    r = client.post(
        "/analyze", json={"pr_id": "1", "repo": "org/svc", "diff": huge_diff})
    assert r.status_code == 422


def test_analyze_accepts_diff_at_65536_chars(client):
    with patch("intelligence.routes.analyze.fetch_incident_history", return_value=DT4821_INCIDENTS), \
            patch("intelligence.routes.analyze.extract_pattern", return_value={
                "pattern": "x", "risk_score": 1, "risk_rationale": "y",
                "incident_context": DT4821_INCIDENTS[0], "previous_scans": [],
            }), \
            patch("intelligence.routes.analyze.find_similar_wins", return_value=[]), \
            patch("intelligence.routes.analyze.find_similar_scars", return_value=[]):
        r = client.post(
            "/analyze", json={"pr_id": "1", "repo": "org/svc", "diff": "a" * 65536})
    assert r.status_code == 200


def test_fetch_incident_history_raises_on_bad_token():
    from intelligence.tools.dynatrace import fetch_incident_history
    with pytest.raises(Exception):
        fetch_incident_history("bad.env.com", "bad-token", SAMPLE_DIFF)


def test_extract_pattern_returns_required_keys():
    from intelligence.agent import extract_pattern
    with patch("intelligence.agent.call_gemini_adk", return_value=(
        "HTTP call with no timeout.", 9, "Matches DT-4821."
    )):
        result = extract_pattern(SAMPLE_DIFF, DT4821_INCIDENTS)
    assert "pattern" in result
    assert "risk_score" in result
    assert "risk_rationale" in result
    assert "incident_context" in result
    assert "previous_scans" in result


# ---------------------------------------------------------------------------
# call_gemini_adk - ADK LlmAgent integration (RED: these fail until implemented)
# ---------------------------------------------------------------------------

def _make_final_event(text: str):
    """Return a mock ADK Event whose is_final_response() returns True."""
    from unittest.mock import MagicMock
    event = MagicMock()
    event.is_final_response.return_value = True
    event.content = MagicMock()
    event.content.parts = [MagicMock(text=text)]
    return event


def _make_non_final_event():
    from unittest.mock import MagicMock
    event = MagicMock()
    event.is_final_response.return_value = False
    return event


def test_call_gemini_adk_returns_pattern_score_rationale_tuple():
    """call_gemini_adk parses the ADK final event into (pattern, score, rationale)."""
    from intelligence.agent import call_gemini_adk

    payload = '{"pattern": "HTTP call without timeout", "risk_score": 9, "risk_rationale": "Matches DT-4821 (47-min outage)"}'
    final = _make_final_event(payload)

    with patch("intelligence.agent.Runner") as MockRunner:
        MockRunner.return_value.run.return_value = iter(
            [_make_non_final_event(), final])
        pattern, score, rationale = call_gemini_adk("some prompt")

    assert pattern == "HTTP call without timeout"
    assert score == 9
    assert "DT-4821" in rationale


def test_call_gemini_adk_passes_prompt_as_content_to_runner():
    """call_gemini_adk passes the prompt text wrapped in a genai Content object."""
    from intelligence.agent import call_gemini_adk
    from google.genai import types as genai_types

    final = _make_final_event(
        '{"pattern": "x", "risk_score": 5, "risk_rationale": "y"}')
    run_calls = []

    def capture_run(**kwargs):
        run_calls.append(kwargs)
        return iter([final])

    with patch("intelligence.agent.Runner") as MockRunner:
        MockRunner.return_value.run.side_effect = capture_run
        call_gemini_adk("check this diff please")

    assert len(run_calls) == 1
    msg = run_calls[0]["new_message"]
    assert isinstance(msg, genai_types.Content)
    assert any("check this diff please" in (p.text or "") for p in msg.parts)


def test_call_gemini_adk_creates_llm_agent_with_function_tool():
    """call_gemini_adk constructs an LlmAgent that has at least one FunctionTool."""
    from intelligence.agent import call_gemini_adk
    from google.adk.tools import FunctionTool
    from google.adk.agents import LlmAgent as RealLlmAgent

    final = _make_final_event(
        '{"pattern": "x", "risk_score": 5, "risk_rationale": "y"}')

    with patch("intelligence.agent.Runner") as MockRunner, \
            patch("intelligence.agent.LlmAgent", side_effect=RealLlmAgent) as MockLlmAgent:
        MockRunner.return_value.run.return_value = iter([final])
        call_gemini_adk("prompt")

    assert MockLlmAgent.called, "LlmAgent was never instantiated"
    tools = MockLlmAgent.call_args[1].get("tools", [])
    assert any(isinstance(t, FunctionTool) for t in tools), \
        f"Expected at least one FunctionTool in tools, got: {tools}"


def test_call_gemini_adk_llm_agent_uses_gemini_model():
    """The LlmAgent is configured with a gemini model string."""
    from intelligence.agent import call_gemini_adk

    final = _make_final_event(
        '{"pattern": "x", "risk_score": 5, "risk_rationale": "y"}')

    with patch("intelligence.agent.Runner") as MockRunner, \
            patch("intelligence.agent.LlmAgent") as MockLlmAgent:
        MockLlmAgent.return_value = MagicMock()
        MockRunner.return_value.run.return_value = iter([final])
        call_gemini_adk("prompt")

    model = MockLlmAgent.call_args[1].get("model", "")
    assert "gemini" in model.lower(), f"Expected gemini model, got: {model!r}"


def test_call_gemini_adk_runner_receives_llm_agent_instance():
    """Runner is initialised with the LlmAgent instance created by call_gemini_adk."""
    from intelligence.agent import call_gemini_adk
    from unittest.mock import MagicMock

    final = _make_final_event(
        '{"pattern": "x", "risk_score": 5, "risk_rationale": "y"}')
    mock_agent = MagicMock()

    with patch("intelligence.agent.LlmAgent", return_value=mock_agent), \
            patch("intelligence.agent.Runner") as MockRunner:
        MockRunner.return_value.run.return_value = iter([final])
        call_gemini_adk("prompt")

    runner_kwargs = MockRunner.call_args[1]
    assert runner_kwargs.get("agent") is mock_agent


def test_call_gemini_adk_falls_back_when_json_unparseable():
    """Returns (raw_text, 5, fallback_rationale) when the event text is not valid JSON."""
    from intelligence.agent import call_gemini_adk

    final = _make_final_event("This is not JSON.")

    with patch("intelligence.agent.Runner") as MockRunner:
        MockRunner.return_value.run.return_value = iter([final])
        pattern, score, rationale = call_gemini_adk("prompt")

    assert score == 5
    assert isinstance(pattern, str)
    assert isinstance(rationale, str)


def test_call_gemini_adk_falls_back_when_no_final_event():
    """Returns fallback tuple when no event is a final response."""
    from intelligence.agent import call_gemini_adk

    with patch("intelligence.agent.Runner") as MockRunner:
        MockRunner.return_value.run.return_value = iter(
            [_make_non_final_event()])
        _, score, _ = call_gemini_adk("prompt")

    assert score == 5


def test_extract_pattern_calls_adk_when_no_gemini_fn_given():
    """extract_pattern uses call_gemini_adk by default (no _gemini_fn supplied)."""
    from intelligence.agent import extract_pattern

    adk_calls = []

    def fake_adk(prompt: str):
        adk_calls.append(prompt)
        return ("HTTP call without timeout", 9, "Matches DT-4821")

    with patch("intelligence.agent.call_gemini_adk", side_effect=fake_adk):
        result = extract_pattern(
            diff="@@ -12 +12 @@ response = httpx.get(url)",
            incidents=[{"incident_id": "DT-4821", "duration_minutes": 47}],
        )

    assert len(adk_calls) == 1
    assert result["pattern"] == "HTTP call without timeout"
    assert result["risk_score"] == 9


def test_extract_pattern_still_accepts_gemini_fn_override():
    """When _gemini_fn is supplied, extract_pattern uses it and skips ADK."""
    from intelligence.agent import extract_pattern

    override_calls = []

    def my_fn(prompt: str):
        override_calls.append(prompt)
        return ("custom pattern", 7, "custom rationale")

    with patch("intelligence.agent.call_gemini_adk") as mock_adk:
        result = extract_pattern(diff="diff", incidents=[], _gemini_fn=my_fn)

    mock_adk.assert_not_called()
    assert len(override_calls) == 1
    assert result["pattern"] == "custom pattern"


def test_call_gemini_adk_prompt_does_not_include_preloaded_incidents():
    """The ADK agent prompt must NOT contain pre-fetched incidents.
    The agent should call the FunctionTool to fetch them itself - that is
     agentic tool use. If incidents are pre-embedded in the prompt,
    the tool is never needed and the ADK integration is decorative."""
    from intelligence.agent import call_gemini_adk
    from unittest.mock import patch, MagicMock

    prompts_sent = []

    def fake_runner_run(user_id, session_id, new_message):
        prompts_sent.append(new_message.parts[0].text)
        event = MagicMock()
        event.is_final_response.return_value = True
        event.content.parts = [
            MagicMock(text='{"pattern":"p","risk_score":8,"risk_rationale":"r"}')]
        return [event]

    with patch("intelligence.agent.LlmAgent"), \
            patch("intelligence.agent.InMemorySessionService") as MockSvc, \
            patch("intelligence.agent.Runner") as MockRunner:
        MockSvc.return_value._create_session_impl.return_value = MagicMock(
            id="s1")
        MockRunner.return_value.run = fake_runner_run
        call_gemini_adk("@@ -12 +12 @@ response = httpx.get(url)")

    assert prompts_sent, "Runner.run was never called"
    # The prompt should contain the raw diff, not pre-loaded JSON incident data
    assert "Query result records" not in prompts_seen[0] if (
        prompts_seen := prompts_sent) else True
    assert "incident_id" not in prompts_sent[0], (
        "Prompt contains pre-fetched incident data - the FunctionTool will never be called"
    )


def test_adk_instruction_does_not_explicitly_direct_tool_call():
    """The LlmAgent instruction must not say 'call the tool' or 'use the tool'.
    It should mention the tool is available and let the model decide.
     agentic tool use requires the model to reason about whether to invoke it."""
    from intelligence.agent import call_gemini_adk
    from unittest.mock import patch, MagicMock

    captured_instruction = {}

    class CaptureLlmAgent:
        def __init__(self, *args, **kwargs):
            captured_instruction["text"] = kwargs.get("instruction", "")

        def __getattr__(self, name):
            return MagicMock()

    with patch("intelligence.agent.LlmAgent", CaptureLlmAgent), \
            patch("intelligence.agent.InMemorySessionService") as MockSvc, \
            patch("intelligence.agent.Runner") as MockRunner:
        mock_event = MagicMock()
        mock_event.is_final_response.return_value = True
        mock_event.content.parts = [
            MagicMock(text='{"pattern":"p","risk_score":8,"risk_rationale":"r"}')]
        MockSvc.return_value._create_session_impl.return_value = MagicMock(
            id="s1")
        MockRunner.return_value.run.return_value = [mock_event]
        try:
            call_gemini_adk("test diff")
        except Exception:
            pass

    instruction = captured_instruction.get("text", "").lower()
    assert "call the tool" not in instruction, \
        "Instruction explicitly directs tool call - model has no agency"
    assert "use the tool" not in instruction, \
        "Instruction explicitly directs tool use - model has no agency"
    assert "tool" in instruction or "dynatrace" in instruction, \
        "Instruction should mention the tool is available without mandating its use"


# ---------------------------------------------------------------------------
# Continuous severity scaling - _severity_adjustment and _parse_cost
# ---------------------------------------------------------------------------

def test_severity_adjustment_short_duration_no_floor():
    from intelligence.agent import _severity_adjustment
    floor, boost = _severity_adjustment(5, "£500")
    assert floor == 0
    assert boost == 0


def test_severity_adjustment_10_to_30_min():
    from intelligence.agent import _severity_adjustment
    floor, _ = _severity_adjustment(20, "£0")
    assert floor == 6


def test_severity_adjustment_30_to_60_min():
    from intelligence.agent import _severity_adjustment
    floor, _ = _severity_adjustment(47, "£0")
    assert floor == 8


def test_severity_adjustment_60_to_120_min():
    from intelligence.agent import _severity_adjustment
    floor, _ = _severity_adjustment(90, "£0")
    assert floor == 9


def test_severity_adjustment_over_120_min():
    from intelligence.agent import _severity_adjustment
    floor, _ = _severity_adjustment(150, "£0")
    assert floor == 10


def test_severity_adjustment_cost_boost_10k_to_50k():
    from intelligence.agent import _severity_adjustment
    _, boost = _severity_adjustment(0, "£23,000")
    assert boost == 2


def test_severity_adjustment_cost_boost_over_50k():
    from intelligence.agent import _severity_adjustment
    _, boost = _severity_adjustment(0, "£60,000")
    assert boost == 3


def test_severity_adjustment_cost_boost_under_1k():
    from intelligence.agent import _severity_adjustment
    _, boost = _severity_adjustment(0, "£500")
    assert boost == 0


def test_severity_adjustment_combined_47min_23k():
    from intelligence.agent import _severity_adjustment
    floor, boost = _severity_adjustment(47, "£23,000")
    assert floor == 8
    assert boost == 2


def test_parse_cost_handles_pound_with_commas():
    from intelligence.agent import _parse_cost
    assert _parse_cost("£23,000") == 23000


def test_parse_cost_handles_dollar():
    from intelligence.agent import _parse_cost
    assert _parse_cost("$5000") == 5000


def test_parse_cost_handles_unknown():
    from intelligence.agent import _parse_cost
    assert _parse_cost("unknown") == 0


def test_extract_pattern_uses_severity_adjustment():
    from intelligence.agent import extract_pattern
    incident = {"duration_minutes": 90,
                "estimated_cost": "£60,000", "incident_id": "X-1"}
    result = extract_pattern(
        "diff", [incident], _gemini_fn=lambda p: ("pattern", 5, "rationale"))
    # floor=9 (60-120min), boost=3 (>=£50k) → max(5+3, 9) = max(8, 9) = 9
    assert result["risk_score"] >= 9


def test_extract_pattern_p26051_still_scores_high():
    from intelligence.agent import extract_pattern
    incident = {"duration_minutes": 47,
                "estimated_cost": "£23,000", "incident_id": "P-26051"}
    result = extract_pattern(
        "diff", [incident], _gemini_fn=lambda p: ("pattern", 7, "rationale"))
    # floor=8, boost=2 → max(7+2, 8) = max(9, 8) = 9
    assert result["risk_score"] == 9


# ---------------------------------------------------------------------------
# ADK completeness - Scanner, Fix Factory agent, Fix Factory evaluator
# ---------------------------------------------------------------------------

def test_scanner_has_adk_function():
    """Scanner exposes a call_scanner_adk function using LlmAgent."""
    from scanner.agent import call_scanner_adk
    assert callable(call_scanner_adk)


def test_scanner_adk_uses_llm_agent():
    """call_scanner_adk is backed by an ADK LlmAgent with a GitLab FunctionTool."""
    import inspect
    from scanner import agent as scanner_mod
    src = inspect.getsource(scanner_mod)
    assert "LlmAgent" in src
    assert "FunctionTool" in src


def test_fix_factory_agent_has_adk_function():
    """Fix Factory agent exposes a call_fix_adk function using LlmAgent."""
    from fix_factory.agent import call_fix_adk
    assert callable(call_fix_adk)


def test_fix_factory_agent_adk_uses_llm_agent():
    """call_fix_adk is backed by an ADK LlmAgent with a GitLab history FunctionTool."""
    import inspect
    from fix_factory import agent as ff_mod
    src = inspect.getsource(ff_mod)
    assert "LlmAgent" in src
    assert "FunctionTool" in src


def test_fix_factory_evaluator_has_adk_function():
    """Fix Factory evaluator exposes a call_evaluator_adk function using LlmAgent."""
    from fix_factory.evaluator import call_evaluator_adk
    assert callable(call_evaluator_adk)


def test_fix_factory_evaluator_adk_uses_llm_agent():
    """call_evaluator_adk is backed by an ADK LlmAgent with a Dynatrace FunctionTool."""
    import inspect
    from fix_factory import evaluator as ev_mod
    src = inspect.getsource(ev_mod)
    assert "LlmAgent" in src
    assert "FunctionTool" in src
