import json

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
                subtype="success",
                duration_ms=1,
                duration_api_ms=1,
                is_error=False,
                num_turns=1,
                session_id="sess-1",
                total_cost_usd=0.5,
                structured_output=structured,
            )

    return FakeClient


def full_run(validated=True):
    return [
        ARC,
        {"acte_1": ACT, "acte_2": ACT, "acte_3": ACT},
        ACT,
        ACT,
        ACT,
        ACT,
        {"validated": validated, "message": "nope", "issues": ["bad url"]},
        {"title": "S", "story": "...", "theme": "th"},
    ]


async def test_full_episode_resumes_session_and_tracks_cost(monkeypatch):
    calls = []
    monkeypatch.setattr(orch, "ClaudeSDKClient", make_fake_client(full_run(), calls))
    o = orch.EpisodeOrchestrator()
    ep = await o.generate_episode("scénario")
    assert ep.has_all_acts() and ep.twilight_zone_story.title == "S"
    assert [ep.acts[f"acte_{i}"].narrator for i in (1, 2, 3, 4)] == [
        "narrator_1",
        "narrator_2",
        "narrator_1",
        "narrator_2",
    ]
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
    text = "Voici:\n```json\n" + ActOutput(title="a", content="b").model_dump_json() + "\n```"
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


# --- reprise ----------------------------------------------------------------
def partial_episode(n_acts, themes=True, cost=1.0):
    from newtempsx.models import Act, Episode

    return Episode(
        episode_title="E",
        scenario_input="s",
        narrative_arc="A",
        acts={f"acte_{i}": Act(title=f"T{i}", content="C") for i in range(1, n_acts + 1)},
        themes=ARC["themes"] if themes else None,
        cost_usd=cost,
    )


async def test_resume_skips_existing_steps_and_accumulates_cost(monkeypatch, tmp_path):
    from newtempsx.exporters import EpisodeExporter

    calls = []
    # Actes 1-5 existent : restent actes 6, 7, validation, Twilight
    responses = [ACT, ACT, {"validated": True, "message": "ok"}, {"title": "S", "story": "...", "theme": "th"}]
    monkeypatch.setattr(orch, "ClaudeSDKClient", make_fake_client(responses, calls))
    exporter = EpisodeExporter(output_dir=tmp_path, run_name="r")
    o = orch.EpisodeOrchestrator(exporter=exporter)
    ep = await o.generate_episode("s", resume=partial_episode(5))
    assert len(calls) == 4 and ep.has_all_acts()
    assert ep.acts["acte_1"].title == "T1"  # actes existants préservés
    assert ep.cost_usd == pytest.approx(1.0 + 0.5 * 4)
    saved = json.loads((tmp_path / "episode.json").read_text(encoding="utf-8"))
    assert saved["themes"]["acte_7"] == "t7" and saved["cost_usd"] == pytest.approx(3.0)


async def test_resume_without_themes_refuses_to_overwrite(monkeypatch):
    calls = []
    monkeypatch.setattr(orch, "ClaudeSDKClient", make_fake_client([], calls))
    with pytest.raises(ValueError, match="thèmes"):
        await orch.EpisodeOrchestrator().generate_episode("s", resume=partial_episode(3, themes=False))
    assert calls == []


async def test_resume_empty_run_starts_from_arc(monkeypatch):
    calls = []
    monkeypatch.setattr(orch, "ClaudeSDKClient", make_fake_client(full_run(), calls))
    ep = await orch.EpisodeOrchestrator().generate_episode("s", resume=partial_episode(0, themes=False, cost=None))
    assert len(calls) == 8 and ep.themes["acte_1"] == "t1"
