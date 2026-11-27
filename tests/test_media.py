import asyncio
import base64
import json
import shutil
import subprocess

import httpx
import pytest

from newtempsx import http_utils, image_generator as ig
from newtempsx.audio_generator import AudioGenerator, TTSProvider
from newtempsx.models import Act, Episode


# --- http_utils -------------------------------------------------------------
async def test_retry_on_429_then_success(monkeypatch):
    sleeps = []
    real_sleep = asyncio.sleep
    async def fake_sleep(d):
        sleeps.append(d)
        await real_sleep(0)
    monkeypatch.setattr(http_utils.asyncio, "sleep", fake_sleep)
    statuses = iter([429, 503, 200])
    handler = lambda req: httpx.Response(next(statuses), json={"ok": 1})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        r = await http_utils.request_with_retry(c, "POST", "https://x.test/a", base_delay=0.01)
    assert r.status_code == 200 and len(sleeps) == 2


async def test_no_retry_on_400():
    calls = []
    def handler(req):
        calls.append(1)
        return httpx.Response(400, json={"error": {"message": "bad"}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        with pytest.raises(httpx.HTTPStatusError):
            await http_utils.request_with_retry(c, "POST", "https://x.test/a")
    assert len(calls) == 1


async def test_gives_up_after_max_attempts(monkeypatch):
    real_sleep = asyncio.sleep
    async def fake_sleep(d):
        await real_sleep(0)
    monkeypatch.setattr(http_utils.asyncio, "sleep", fake_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500))) as c:
        with pytest.raises(httpx.HTTPStatusError):
            await http_utils.request_with_retry(c, "GET", "https://x.test/a", max_attempts=3)


# --- audio ------------------------------------------------------------------
@pytest.fixture
def audio(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    return AudioGenerator(output_dir=tmp_path, provider=TTSProvider.OPENAI)


def test_split_chunks_respect_limit_and_content(audio):
    text = " ".join(f"Phrase numéro {i}." for i in range(800))
    chunks = audio._split_text_into_chunks(text, 4096)
    assert len(chunks) > 1 and all(len(c) <= 4096 for c in chunks)
    assert " ".join(chunks).split() == text.split()


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg absent")
async def test_ffmpeg_concat_produces_valid_mp3(audio, tmp_path):
    parts = []
    for i in range(2):
        f = tmp_path / f"p{i}.mp3"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(f)], check=True)
        parts.append(f)
    out = tmp_path / "out.mp3"
    await audio._concatenate_audio_files(parts, out)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                               capture_output=True, text=True).stdout)
    assert 1.8 < dur < 2.3


async def test_long_text_chunked_cleanup_and_concat(audio, tmp_path, monkeypatch):
    seen = []
    async def fake_single(text, path, voice="fable"):
        seen.append(len(text))
        path.write_bytes(b"MP3")
        return path
    monkeypatch.setattr(audio, "_generate_openai_single", fake_single)
    monkeypatch.setattr(shutil, "which", lambda n: None)  # force le repli binaire
    out = tmp_path / "a.mp3"
    await audio._generate_openai_async("Une phrase. " * 1000, out)
    assert len(seen) > 1 and all(n <= 4096 for n in seen)
    assert out.read_bytes() == b"MP3" * len(seen)
    assert not list(tmp_path.glob("*_chunk_*"))


async def test_failure_leaves_no_partial_file(audio, tmp_path, monkeypatch):
    n = 0
    async def flaky(text, path, voice="fable"):
        nonlocal n
        n += 1
        if n == 2:
            raise RuntimeError("boom")
        path.write_bytes(b"x")
        return path
    monkeypatch.setattr(audio, "_generate_openai_single", flaky)
    with pytest.raises(RuntimeError):
        await audio._generate_openai_async("Une phrase. " * 1000, tmp_path / "a.mp3")
    assert list(tmp_path.iterdir()) == []


def make_episode(n_acts=7):
    acts = {f"acte_{i}": Act(title=f"T{i}", content=f"Contenu {i}", image_prompts=["p1", "p2"]) for i in range(1, n_acts + 1)}
    return Episode(episode_title="Ep", scenario_input="s", narrative_arc="a", acts=acts)


async def test_episode_audio_parallel_bounded_and_isolates_errors(audio, monkeypatch):
    audio.max_concurrent = 3
    running = peak = 0
    async def fake(act, key, title):
        nonlocal running, peak
        if key == "acte_3":
            raise RuntimeError("x")
        running += 1; peak = max(peak, running)
        await asyncio.sleep(0.02)
        running -= 1
        return audio.output_dir / f"{key}.mp3"
    monkeypatch.setattr(audio, "_generate_act_audio_async", fake)
    res = await audio.generate_episode_audio(make_episode())
    assert peak == 3 and res["acte_3"] is None and sum(v is not None for v in res.values()) == 6


# --- images -----------------------------------------------------------------
@pytest.fixture
def images(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    return ig.ImageGenerator(output_dir=tmp_path / "images", max_concurrent=2)


def fake_request(payloads):
    async def _req(client, method, url, **kw):
        if method == "POST":
            _req.models.append(kw["json"]["model"])
            return httpx.Response(200, json=payloads, request=httpx.Request(method, url))
        return httpx.Response(200, content=b"IMGDATA", request=httpx.Request(method, url))
    _req.models = []
    return _req


async def test_image_url_and_b64_responses(images, monkeypatch):
    req = fake_request({"data": [{"url": "https://cdn.test/i.png"}]})
    monkeypatch.setattr(ig, "request_with_retry", req)
    p = await images.generate_image_from_prompt("a", images.output_dir / "u.png")
    assert p.read_bytes() == b"IMGDATA"

    req = fake_request({"data": [{"b64_json": base64.b64encode(b"B64").decode()}]})
    monkeypatch.setattr(ig, "request_with_retry", req)
    p = await images.generate_image_from_prompt("b", images.output_dir / "b.png", model="gpt-image-1")
    assert p.read_bytes() == b"B64" and req.models == ["gpt-image-1"]


async def test_image_error_returns_none(images, monkeypatch):
    async def boom(*a, **k):
        raise httpx.HTTPStatusError("x", request=httpx.Request("POST", "https://x"), response=httpx.Response(400, json={"error": {"message": "refusé"}}))
    monkeypatch.setattr(ig, "request_with_retry", boom)
    assert await images.generate_image_from_prompt("c", images.output_dir / "c.png") is None


async def test_episode_images_integrated_in_order(images, monkeypatch):
    async def fake_gen(prompt, path, **kw):
        await asyncio.sleep(0.05 if prompt == "p1" else 0)  # p2 termine avant p1
        path.write_bytes(b"I")
        return path
    monkeypatch.setattr(images, "generate_image_from_prompt", fake_gen)
    order = []
    monkeypatch.setattr(images, "_integrate_single_image_into_act",
                        lambda act, path, key, i, total_images, prompt: order.append((key, i)))
    ep = make_episode(2)
    res = await images.generate_episode_images(ep)
    assert set(res) == {"acte_1", "acte_2"} and len(res["acte_1"]) == 2
    assert [i for k, i in order if k == "acte_1"] == [1, 2]
