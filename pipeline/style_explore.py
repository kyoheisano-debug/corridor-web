#!/usr/bin/env python3
"""Corridor style explorer — lock the art touch before episode generation.

Generates the same character across several "touch" presets so a human can
pick the look before any video is produced. Once a preset is chosen, copy its
token into characters.json `style_token` and run generate.py as usual.

Each preset keeps the project's hard rules (Japanese TV-anime look,
Japanese-leaning faces, 13th-century Dai Viet costume / world) and only varies
the rendering touch (linework, shading, palette, mood).

Output: output/style-explore/<preset>__<char>.png  (+ index.json)

Examples:
  python3 style_explore.py --provider mock
  python3 style_explore.py --provider seedance2 --chars toan mai
  python3 style_explore.py --provider seedance2 --presets clean cinematic
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from providers import get_provider

ROOT = Path(__file__).resolve().parent

# Shared invariant rules (never vary these — project art rules).
BASE_RULES = ("Japanese-leaning facial features, vertical 9:16, "
              "13th-century Dai Viet (medieval East Asian) setting, "
              "full body character sheet, neutral background")

# Each preset varies only the rendering touch.
PRESETS = {
    "clean": "Japanese modern TV anime style, cel shading, clean confident "
             "linework, expressive eyes, bright crisp colors, high detail",
    "cinematic": "Japanese cinematic TV anime (ufotable-like), rich painterly "
                 "shading, atmospheric depth, muted desaturated palette, soft "
                 "film grain, dramatic volumetric lighting, high detail",
    "bold": "bold modern shonen anime (MAPPA-like), thick high-contrast "
            "linework, dynamic saturated colors, sharp angular faces, intense "
            "expressions, gritty dramatic lighting, high detail",
}


def run(provider_name: str, char_ids: list[str], preset_ids: list[str],
        out_root: Path) -> int:
    chars_doc = json.loads((ROOT / "characters.json").read_text(encoding="utf-8"))
    characters = chars_doc["characters"]

    out_dir = out_root / "style-explore"
    out_dir.mkdir(parents=True, exist_ok=True)
    provider = get_provider(provider_name)

    print(f"Style explore | provider: {provider.name} | "
          f"chars: {', '.join(char_ids)} | presets: {', '.join(preset_ids)}")

    index = []
    for cid in char_ids:
        meta = characters.get(cid)
        if not meta:
            print(f"  ! unknown character '{cid}' — skipping", file=sys.stderr)
            continue
        for pid in preset_ids:
            touch = PRESETS[pid]
            prompt = f"{touch}, {BASE_RULES}, {meta['ref_prompt']}"
            out = out_dir / f"{pid}__{cid}.png"
            res = provider.generate_image(prompt, out)
            status = "ok" if res.ok else "error"
            print(f"  {'+' if res.ok else 'x'} {pid} / {cid}: {status}"
                  + (f" ({res.error})" if res.error else ""))
            index.append({"char": cid, "preset": pid, "prompt": prompt,
                          "image": res.output_path, "status": status,
                          "error": res.error})

    (out_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for e in index if e["status"] == "ok")
    print(f"\nIndex: {out_dir / 'index.json'}")
    print(f"Done. {ok}/{len(index)} images ok.")
    return 1 if ok != len(index) else 0


def main() -> int:
    p = argparse.ArgumentParser(description="Corridor art-touch explorer")
    p.add_argument("--provider", default="mock", help="mock | seedance2 | fal | kie")
    p.add_argument("--chars", nargs="*", default=["toan", "mai"],
                   help="Character ids from characters.json")
    p.add_argument("--presets", nargs="*", default=list(PRESETS),
                   choices=list(PRESETS), help="Touch presets to render")
    p.add_argument("--out", default=str(ROOT / "output"), help="Output root dir")
    a = p.parse_args()
    return run(a.provider, a.chars, a.presets, Path(a.out))


if __name__ == "__main__":
    raise SystemExit(main())
