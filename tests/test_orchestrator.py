import pytest

from newtempsx import orchestrator as orch
from newtempsx.models import ActOutput

ACT = {"title": "T", "content": "C", "references": [{"title": "r", "url": "https://x.org"}]}
ARC = {"episode_title": "E", "narrative_arc": "A", "themes": {f"acte_{i}": f"t{i}" for i in range(1, 8)}}


class FakeResult:
    pass


def make_fake_client(responses, calls):
    """responses: file de dicts (structured_output) ou ('text', str)."""

    class FakeClient:
        def __init__(self, options):
            self.options = options
            calls.append(options)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def query(self, prompt):
            self.prompt = prompt

        async def receive_response(self):
            item = responses.pop(0)
            if isinstance(item, tuple):
                yield orch.AssistantMessage(content=[orch.TextBlock(text=item[1])], model="m")
                structured = None
            else:
                structured = item
            yield orch.ResultMessage(
                subtype="success", duration_ms=1, duration_api_ms=1, is_error=False,
                num_turns=1, session_id="sess-1", total_cost_usd=0.5, structured_output=structured,
            )

    return FakeClient


def full_run(validated=True):
    return [
        ARC,
        {"acte_1": ACT, "acte_2": ACT, "acte_3": ACT},
        ACT, ACT, ACT, ACT,
        {"validated": validated, "message": "nope", "issues": ["bad url"]},
        {"title": "S", "story": "...", "theme": "th"},
    ]


async def test_full_episode_resumes_session_and_tracks_cost(monkeypatch):
    calls = []
    monkeypatch.setattr(orch, "ClaudeSDKClient", make_fake_client(full_run(), calls))
    o = orch.EpisodeOrchestrator()
    ep = await o.generate_episode("scénario")
    assert ep.has_all_acts() and ep.twilight_zone_story.title == "S"
    assert [ep.acts[f"acte_{i}"].narrator for i in (1, 2, 3, 4)] == ["narrator_1", "narrator_2", "narrator_1", "narrator_2"]
    assert calls[0].resume is None and all(c.resume == "sess-1" for c in calls[1:])
    assert all(c.output_format["type"] == "json_schema" for c in calls)
    assert o.total_cost_usd == pytest.approx(0.5 * 8)
    assert "WebFetch" in calls[0].allowed_tools and "Browser" not in calls[0].allowed_tools


async def test_rejection_triggers_one_retry_then_raises(monkeypatch):
    calls = []
    monkeypatch.setattr(orch, "ClaudeSDKClient", make_fake_client(full_run(False)[:-1] * 2, calls))
    o = orch.EpisodeOrchestrator()
    with pytest.raises(orch.EpisodeRejectedError):
        await o.generate_episode("s")
    assert len(calls) == 14  # 7 étapes x 2 tentatives (pas de bonus Twilight)


async def test_other_errors_do_not_retry(monkeypatch):
    calls = []
    monkeypatch.setattr(orch, "ClaudeSDKClient", make_fake_client([{"bad": 1}], calls))
    with pytest.raises(orch.StructuredOutputError):
        await orch.EpisodeOrchestrator().generate_episode("s")
    assert len(calls) == 1


async def test_text_fallback_parsing(monkeypatch):
    calls = []
    text = 'Voici:\n```json\n' + ActOutput(title="a", content="b").model_dump_json() + '\n```'
    monkeypatch.setattr(orch, "ClaudeSDKClient", make_fake_client([("text", text)], calls))
    act = await orch.EpisodeOrchestrator()._run_step("p", ActOutput)
    assert act.title == "a"


def test_parse_json_response_variants():
    p = orch.EpisodeOrchestrator._parse_json_response
    assert p('{"a": 1}') == {"a": 1}
    assert p('bla {"a": {"b": "}"}} fin') == {"a": {"b": "}"}}
    assert p('{"a": "ligne1\nligne2"}') == {"a": "ligne1\nligne2"}
    with pytest.raises(orch.StructuredOutputError):
        p("rien")
