"""Crée un run de démonstration (avec une image) dans un dossier de sortie, pour les tests E2E."""

import json
import struct
import sys
import zlib
from pathlib import Path


def png(width=64, height=40, rgb=(240, 165, 58)) -> bytes:
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def make(
    output: Path,
    name="demo_conscience_20261127_100000",
    n_acts=7,
    cost=4.37,
    title="Les Machines qui rêvent de comprendre",
):
    run = output / name
    (run / "images").mkdir(parents=True, exist_ok=True)
    (run / "audio").mkdir(exist_ok=True)
    if name.startswith("demo_"):
        (run / "images" / "acte_1_demo_1_abc.png").write_bytes(png())
    names = ["Le Signal", "Le Décryptage", "La Tension", "La Fiction", "Le Dialogue", "La Mémoire", "La Transmission"]
    para = "Ce paragraphe explore la **conscience artificielle** et ses *zones d'ombre*. " * 4
    acts = {}
    for i, t in enumerate(names[:n_acts], start=1):
        body = f"{para}\n\n> « Que signifie vraiment comprendre ? »\n\n{para}\n\n- Premier point\n- Second point"
        if i == 1:
            body = f"{para}\n\n![Illustration](../images/acte_1_demo_1_abc.png)\n\n{para}"
        acts[f"acte_{i}"] = {
            "title": t,
            "content": body,
            "narrator": "narrator_1" if i % 2 else "narrator_2",
            "image_prompts": [],
            "references": [{"title": "Nature", "url": "https://www.nature.com/", "description": "Étude de référence."}],
        }
    episode = {
        "episode_title": title,
        "scenario_input": "La conscience artificielle : que signifie comprendre pour une machine ?",
        "narrative_arc": "Un épisode en **sept temps**.",
        "run_name": name,
        "cost_usd": cost,
        "themes": {f"acte_{i}": f"thème {i}" for i in range(1, 8)},
        "acts": acts,
    }
    if n_acts >= 7:
        episode["twilight_zone_story"] = {
            "title": "Le Dernier Interprète",
            "story": para * 3,
            "theme": "Solitude",
            "image_prompts": [],
        }
    (run / "episode.json").write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8")
    return run


def make_all(output: Path):
    """Un run complet avec image + trois autres (dont un en cours) : la recherche apparaît dès 4 épisodes."""
    make(output)
    make(output, "voyage_temps_20261126_090000", 7, 1.2, "Voyager dans le temps")
    make(output, "oceans_20261125_090000", 7, None, "La mémoire des océans")
    make(output, "en_cours_20261127_110000", 3, 0.8, "Un épisode en cours de génération")


if __name__ == "__main__":
    make_all(Path(sys.argv[1]))
