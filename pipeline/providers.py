"""Video/image generation providers for the Corridor pipeline.

Provider abstraction so the orchestrator stays the same regardless of which
Seedance access route is used. Implementations:

- MockProvider     : no network, writes placeholder artifacts + request sidecars.
                     Used for dry runs and for letting Claude Code exercise the
                     full pipeline without API keys.
- FalProvider      : Seedance via fal.ai (FAL_KEY).
- KieProvider      : Seedance via kie.ai (KIE_API_KEY).
- VolcengineProvider: Seedance via ByteDance Volcengine (placeholder for the
                     official API; fill in once credentials are provisioned).

Only the standard library is used, so the pipeline runs anywhere Python 3.10+
is available. Real providers do plain HTTP via urllib; swap to `requests` later
if preferred.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class GenResult:
    """Outcome of a single generation call."""

    ok: bool
    output_path: Optional[str] = None
    request: dict = field(default_factory=dict)
    response: dict = field(default_factory=dict)
    error: Optional[str] = None


class VideoProvider:
    """Base interface. Subclasses implement image + video generation."""

    name = "base"

    def generate_image(self, prompt: str, out_path: Path, **opts) -> GenResult:
        raise NotImplementedError

    def generate_video(
        self,
        prompt: str,
        out_path: Path,
        image: Optional[Path] = None,
        duration: int = 5,
        resolution: str = "720p",
        **opts,
    ) -> GenResult:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Mock provider (no network) — default for dry runs.
# --------------------------------------------------------------------------- #
class MockProvider(VideoProvider):
    """Writes the exact request payload next to a placeholder artifact.

    Lets you validate specs, prompts, refs and the manifest end-to-end without
    spending money or needing a key. The `.request.json` sidecars are the same
    payloads a real provider would receive, so they double as a review surface.
    """

    name = "mock"

    def _write(self, kind: str, payload: dict, out_path: Path) -> GenResult:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            f"[MOCK {kind}] {payload.get('prompt', '')[:80]}\n", encoding="utf-8"
        )
        sidecar = out_path.with_suffix(out_path.suffix + ".request.json")
        sidecar.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return GenResult(ok=True, output_path=str(out_path), request=payload,
                         response={"mock": True})

    def generate_image(self, prompt: str, out_path: Path, **opts) -> GenResult:
        return self._write("image", {"prompt": prompt, **opts}, out_path)

    def generate_video(self, prompt, out_path, image=None, duration=5,
                       resolution="720p", **opts) -> GenResult:
        payload = {
            "prompt": prompt,
            "image": str(image) if image else None,
            "duration": duration,
            "resolution": resolution,
            **opts,
        }
        return self._write("video", payload, out_path)


# --------------------------------------------------------------------------- #
# fal.ai provider — Seedance via fal queue API.
# Docs: https://fal.ai/models (search "seedance"). Endpoints may change; keep
# model ids in env so they can be updated without code changes.
# --------------------------------------------------------------------------- #
class FalProvider(VideoProvider):
    name = "fal"

    def __init__(self):
        self.key = os.environ.get("FAL_KEY")
        if not self.key:
            raise RuntimeError("FAL_KEY is not set (see pipeline/.env.example)")
        self.image_model = os.environ.get("FAL_IMAGE_MODEL", "fal-ai/bytedance/seedream/v4")
        self.video_model = os.environ.get("FAL_VIDEO_MODEL", "fal-ai/bytedance/seedance/v1/pro")
        self.base = "https://queue.fal.run"

    def _post(self, model: str, body: dict) -> dict:
        req = urllib.request.Request(
            f"{self.base}/{model}",
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Key {self.key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _poll(self, status_url: str) -> dict:
        for _ in range(120):  # up to ~10 min
            req = urllib.request.Request(status_url, headers={"Authorization": f"Key {self.key}"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "COMPLETED":
                return data
            if data.get("status") in {"FAILED", "ERROR"}:
                raise RuntimeError(f"fal job failed: {data}")
            time.sleep(5)
        raise TimeoutError("fal job did not complete in time")

    @staticmethod
    def _download(url: str, out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=300) as r, open(out_path, "wb") as f:
            f.write(r.read())

    def generate_image(self, prompt: str, out_path: Path, **opts) -> GenResult:
        body = {"prompt": prompt, "image_size": {"width": 720, "height": 1280}}
        try:
            submit = self._post(self.image_model, body)
            done = self._poll(submit["status_url"]) if "status_url" in submit else submit
            url = done["images"][0]["url"]
            self._download(url, out_path)
            return GenResult(ok=True, output_path=str(out_path), request=body, response=done)
        except (urllib.error.URLError, KeyError, RuntimeError, TimeoutError) as e:
            return GenResult(ok=False, request=body, error=str(e))

    def generate_video(self, prompt, out_path, image=None, duration=5,
                       resolution="720p", **opts) -> GenResult:
        body = {"prompt": prompt, "resolution": resolution, "duration": duration,
                "aspect_ratio": opts.get("aspect_ratio", "9:16")}
        if image:
            body["image_url"] = str(image)  # for hosted refs, replace with an uploaded URL
        try:
            submit = self._post(self.video_model, body)
            done = self._poll(submit["status_url"]) if "status_url" in submit else submit
            url = done["video"]["url"]
            self._download(url, out_path)
            return GenResult(ok=True, output_path=str(out_path), request=body, response=done)
        except (urllib.error.URLError, KeyError, RuntimeError, TimeoutError) as e:
            return GenResult(ok=False, request=body, error=str(e))


# --------------------------------------------------------------------------- #
# kie.ai provider — stub. Fill request/response shapes from kie.ai's Seedance
# docs when an account is ready. Kept as a clearly-marked placeholder so the
# selector works and the integration point is obvious.
# --------------------------------------------------------------------------- #
class KieProvider(VideoProvider):
    name = "kie"

    def __init__(self):
        self.key = os.environ.get("KIE_API_KEY")
        if not self.key:
            raise RuntimeError("KIE_API_KEY is not set (see pipeline/.env.example)")

    def generate_image(self, prompt: str, out_path: Path, **opts) -> GenResult:
        return GenResult(ok=False, error="KieProvider.generate_image not implemented yet")

    def generate_video(self, prompt, out_path, image=None, duration=5,
                       resolution="720p", **opts) -> GenResult:
        return GenResult(ok=False, error="KieProvider.generate_video not implemented yet")


PROVIDERS = {
    "mock": MockProvider,
    "fal": FalProvider,
    "kie": KieProvider,
}


def get_provider(name: str) -> VideoProvider:
    if name not in PROVIDERS:
        raise SystemExit(f"Unknown provider '{name}'. Options: {', '.join(PROVIDERS)}")
    return PROVIDERS[name]()
