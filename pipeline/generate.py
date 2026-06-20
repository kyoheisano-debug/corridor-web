#!/usr/bin/env python3
"""Corridor anime pipeline orchestrator.

Turns a structured episode spec (episodes/*.json) into per-shot video clips via
Seedance, while keeping characters visually consistent by generating locked
reference images first and feeding them into image-to-video shots.

Flow:
  1. Load characters.json (style token + per-character ref prompts).
  2. Generate (or reuse cached) character reference images.
  3. For each shot, build the full prompt (style + shot) and generate a clip.
     i2v shots attach the primary character's reference image.
  4. Write a manifest.json capturing every request, output path and status.

Designed to be driven by Claude Code: a future session can edit the JSON spec
(or generate a new episode spec from a markdown script) and re-run this.

Examples:
  python3 generate.py --episode episodes/ep01.json --provider mock
  python3 generate.py --episode episodes/ep01.json --provider fal --only S6
  python3 generate.py --episode episodes/ep01.json --provider mock --skip-refs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from providers import get_provider

ROOT = Path(__file__).resolve().parent


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_refs(provider, characters: dict, style: str, refs_dir: Path,
               needed: set[str], skip: bool) -> dict:
    """Generate reference images for the characters used in this episode."""
    ref_map: dict[str, dict] = {}
    refs_dir.mkdir(parents=True, exist_ok=True)
    for cid in sorted(needed):
        meta = characters.get(cid)
        if not meta:
            print(f"  ! unknown character id '{cid}' — skipping ref", file=sys.stderr)
            continue
        out = refs_dir / f"{cid}.png"
        if skip and out.exists():
            print(f"  = ref {cid}: cached")
            ref_map[cid] = {"id": cid, "image": str(out), "status": "cached"}
            continue
        prompt = f"{style}, {meta['ref_prompt']}"
        res = provider.generate_image(prompt, out)
        status = "ok" if res.ok else "error"
        print(f"  {'+' if res.ok else 'x'} ref {cid}: {status}"
              + (f" ({res.error})" if res.error else ""))
        ref_map[cid] = {"id": cid, "image": res.output_path, "status": status,
                        "error": res.error, "request": res.request}
    return ref_map


def run(episode_path: Path, provider_name: str, out_root: Path,
        only: list[str] | None, skip_refs: bool) -> int:
    chars_doc = load_json(ROOT / "characters.json")
    style = chars_doc["style_token"]
    characters = chars_doc["characters"]
    ep = load_json(episode_path)

    provider = get_provider(provider_name)
    out_dir = out_root / ep["id"]
    refs_dir = out_dir / "refs"
    clips_dir = out_dir / "clips"

    shots = ep["shots"]
    if only:
        shots = [s for s in shots if s["id"] in set(only)]
        if not shots:
            raise SystemExit(f"No shots match {only}")

    needed = {cid for s in shots for cid in s.get("characters", [])}
    print(f"Episode {ep['id']} — {ep.get('title', '')}")
    print(f"Provider: {provider.name} | shots: {len(shots)} | characters: {len(needed)}")

    print("\n[1/2] Reference images")
    ref_map = build_refs(provider, characters, style, refs_dir, needed,
                         skip=skip_refs)

    print("\n[2/2] Shots")
    manifest_shots = []
    for s in shots:
        full_prompt = f"{style}, {s['prompt']}"
        primary = (s.get("characters") or [None])[0]
        image = None
        if s.get("mode") == "i2v" and primary and ref_map.get(primary, {}).get("image"):
            image = Path(ref_map[primary]["image"])
        out = clips_dir / f"{s['id']}.mp4"
        res = provider.generate_video(
            full_prompt, out, image=image,
            duration=s.get("duration", 5),
            resolution=ep.get("resolution", "720p"),
            aspect_ratio=ep.get("aspect_ratio", "9:16"),
        )
        status = "ok" if res.ok else "error"
        print(f"  {'+' if res.ok else 'x'} {s['id']} ({s.get('duration')}s, "
              f"{s.get('mode')}, ref={primary or '-'}): {status}"
              + (f" ({res.error})" if res.error else ""))
        manifest_shots.append({
            "id": s["id"], "mode": s.get("mode"), "duration": s.get("duration"),
            "characters": s.get("characters", []), "ref_image": str(image) if image else None,
            "output": res.output_path, "status": status, "error": res.error,
            "prompt": full_prompt, "request": res.request,
        })

    manifest = {
        "episode": ep["id"], "title": ep.get("title"), "provider": provider.name,
        "resolution": ep.get("resolution"), "aspect_ratio": ep.get("aspect_ratio"),
        "refs": ref_map, "shots": manifest_shots,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    errors = [s for s in manifest_shots if s["status"] != "ok"]
    print(f"\nManifest: {manifest_path}")
    print(f"Done. {len(manifest_shots) - len(errors)}/{len(manifest_shots)} shots ok.")
    return 1 if errors else 0


def main() -> int:
    p = argparse.ArgumentParser(description="Corridor anime generation pipeline")
    p.add_argument("--episode", required=True, help="Path to episode spec JSON")
    p.add_argument("--provider", default="mock", help="mock | fal | kie")
    p.add_argument("--out", default=str(ROOT / "output"), help="Output root dir")
    p.add_argument("--only", nargs="*", help="Only run these shot ids (e.g. S6 S9)")
    p.add_argument("--skip-refs", action="store_true",
                   help="Reuse cached reference images if present")
    a = p.parse_args()
    return run(Path(a.episode), a.provider, Path(a.out), a.only, a.skip_refs)


if __name__ == "__main__":
    raise SystemExit(main())
