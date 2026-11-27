import pytest

from newtempsx import cli
from newtempsx.models import Act, Episode


def test_slug():
    assert cli.create_slug_from_text("L'IA, et la Conscience ! Vraiment ?") == "lia_et_la_conscience"
    assert cli.create_slug_from_text("   ") == "episode"
    assert len(cli.create_slug_from_text("x" * 200)) <= 50


def test_load_episode_roundtrip_and_missing(tmp_path):
    ep = Episode(episode_title="T", scenario_input="s", narrative_arc="a", acts={"acte_1": Act(title="a", content="b")})
    (tmp_path / "episode.json").write_text(ep.model_dump_json(), encoding="utf-8")
    assert cli.load_episode(tmp_path).acts["acte_1"].title == "a"
    with pytest.raises(cli.CliError):
        cli.load_episode(tmp_path / "nope")


def test_only_modes_require_run_name(monkeypatch):
    args = cli.build_parser().parse_args(["--audio-only"])
    with pytest.raises(cli.CliError):
        cli.existing_run_dir(args)


def test_cli_exit_codes(monkeypatch):
    async def boom(args):
        raise cli.EpisodeRejectedError("x")

    monkeypatch.setattr(cli, "run", boom)
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    with pytest.raises(SystemExit) as e:
        cli.cli(["s"])
    assert e.value.code == 2


def test_rename_run(tmp_path):
    from newtempsx.exporters import EpisodeExporter

    run = tmp_path / "old"
    exporter = EpisodeExporter(output_dir=run, run_name="old")
    ep = Episode(episode_title="Un Titre Long", scenario_input="s", narrative_arc="a", acts={})
    new = cli.rename_run_after_title(ep, tmp_path, run, exporter)
    assert new.exists() and not run.exists() and new.name.startswith("un_titre_long_")
    assert (new / "episode.json").exists()
