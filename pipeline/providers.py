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


# --------------------------------------------------------------------------- #
# seedance2.ai provider — the route the project is contracted on.
#
# Documented shape (verify exact field names at https://seedance2.ai/api-docs
# while logged in — the page is not publicly fetchable):
#   - Auth   : Authorization: Bearer sk_live_...
#   - Create : POST {BASE}/v1/videos/generations
#              body: {"model": ..., "callback_url"?: ..., "input": {prompt, ...}}
#              -> returns a task id immediately (async)
#   - Poll   : GET {BASE}/v1/videos/generations/{id} until status completed
#
# Everything that might differ between the docs and this guess is read from env
# so it can be corrected without touching code. Image-to-video reference images
# are embedded as base64 data URIs by default (set SEEDANCE2_IMAGE_AS_URL=1 if
# the API expects a hosted URL instead).
# --------------------------------------------------------------------------- #
class Seedance2Provider(VideoProvider):
    name = "seedance2"

    def __init__(self):
        self.key = os.environ.get("SEEDANCE2_API_KEY")
        if not self.key:
            raise RuntimeError("SEEDANCE2_API_KEY is not set (see pipeline/.env.example)")
        self.base = os.environ.get("SEEDANCE2_BASE_URL", "https://seedance2.ai/api").rstrip("/")
        self.video_create = os.environ.get("SEEDANCE2_VIDEO_CREATE", "/v1/videos/generations")
        self.image_create = os.environ.get("SEEDANCE2_IMAGE_CREATE", "/v1/images/generations")
        # Task status lives on its own path (not {create}/{id}).
        self.task_status = os.environ.get("SEEDANCE2_TASK_STATUS", "/v1/tasks")
        self.video_model = os.environ.get("SEEDANCE2_VIDEO_MODEL", "seedance-2-0")
        self.image_model = os.environ.get("SEEDANCE2_IMAGE_MODEL", "seedance-2-0-image")
        self.image_as_url = os.environ.get("SEEDANCE2_IMAGE_AS_URL") == "1"

    # -- low-level helpers --------------------------------------------------- #
    def _headers(self) -> dict:
        # seedance2.ai sits behind Cloudflare, which 403s the default
        # "Python-urllib/x.y" UA; send a normal one (overridable via env).
        ua = os.environ.get("SEEDANCE2_USER_AGENT", "corridor-pipeline/1.0")
        return {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
                "User-Agent": ua}

    def _request(self, method: str, path_or_url: str, body: Optional[dict] = None) -> dict:
        url = path_or_url if path_or_url.startswith("http") else f"{self.base}{path_or_url}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _dig(d: dict, *keys):
        """Return the first present key from a (possibly nested) response.

        Supports list indices in dotted paths, e.g. "data.results.0".
        """
        for k in keys:
            cur = d
            ok = True
            for part in k.split("."):
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
                    cur = cur[int(part)]
                else:
                    ok = False
                    break
            if ok and cur:
                return cur
        return None

    def _poll(self, task_id: str, kind: str) -> dict:
        path = f"{self.task_status}/{task_id}"
        for _ in range(120):  # up to ~10 min at 5s
            data = self._request("GET", path)
            status = (self._dig(data, "status", "state", "data.status") or "").lower()
            if status in {"completed", "succeeded", "success", "done"}:
                return data
            if status in {"failed", "error", "canceled"}:
                reason = self._dig(data, "failed_reason", "error", "message") or data
                raise RuntimeError(f"seedance2 task failed: {reason}")
            time.sleep(5)
        raise TimeoutError("seedance2 task did not complete in time")

    @staticmethod
    def _download(url: str, out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=300) as r, open(out_path, "wb") as f:
            f.write(r.read())

    @staticmethod
    def _data_uri(image: Path) -> str:
        import base64
        mime = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
        return f"data:{mime};base64," + base64.b64encode(image.read_bytes()).decode("ascii")

    # -- public API ---------------------------------------------------------- #
    def generate_image(self, prompt: str, out_path: Path, **opts) -> GenResult:
        body = {"model": self.image_model,
                "input": {"prompt": prompt, "aspect_ratio": opts.get("aspect_ratio", "9:16")}}
        try:
            created = self._request("POST", self.image_create, body)
            task_id = self._dig(created, "taskId", "id", "task_id", "data.id")
            done = self._poll(task_id, "image") if task_id else created
            url = self._dig(done, "data.results.0", "output.image_url", "output.url",
                            "images.0.url", "data.url", "image_url")
            if not url:
                return GenResult(ok=False, request=body, response=done,
                                 error="could not find image url in response (check field mapping)")
            self._download(url, out_path)
            return GenResult(ok=True, output_path=str(out_path), request=body, response=done)
        except (urllib.error.URLError, RuntimeError, TimeoutError, KeyError) as e:
            return GenResult(ok=False, request=body, error=str(e))

    def generate_video(self, prompt, out_path, image=None, duration=5,
                       resolution="720p", **opts) -> GenResult:
        inp = {"prompt": prompt, "duration": duration, "resolution": resolution,
               "aspect_ratio": opts.get("aspect_ratio", "9:16")}
        if image:
            inp["image"] = str(image) if self.image_as_url else self._data_uri(Path(image))
        body = {"model": self.video_model, "input": inp}
        try:
            created = self._request("POST", self.video_create, body)
            task_id = self._dig(created, "taskId", "id", "task_id", "data.id")
            done = self._poll(task_id, "video") if task_id else created
            url = self._dig(done, "data.results.0", "output.video_url", "output.url",
                            "video.url", "data.video_url", "video_url")
            if not url:
                return GenResult(ok=False, request={**body, "input": {**inp, "image": "<omitted>"}},
                                 response=done,
                                 error="could not find video url in response (check field mapping)")
            req_log = {**body, "input": {**inp, "image": "<base64 omitted>" if image else None}}
            try:
                self._download(url, out_path)
            except urllib.error.URLError as e:
                # The clip was generated (and billed) — keep the remote URL so it
                # isn't lost even if this network can't reach the CDN host.
                return GenResult(ok=False, output_path=url, request=req_log, response=done,
                                 error=f"generated ok but download failed ({e}); video url: {url}")
            return GenResult(ok=True, output_path=str(out_path), request=req_log, response=done)
        except (urllib.error.URLError, RuntimeError, TimeoutError, KeyError) as e:
            return GenResult(ok=False, request={**body, "input": {**inp, "image": "<omitted>"}},
                             error=str(e))


PROVIDERS = {
    "mock": MockProvider,
    "seedance2": Seedance2Provider,
    "fal": FalProvider,
    "kie": KieProvider,
}


def get_provider(name: str) -> VideoProvider:
    if name not in PROVIDERS:
        raise SystemExit(f"Unknown provider '{name}'. Options: {', '.join(PROVIDERS)}")
    try:
        return PROVIDERS[name]()
    except RuntimeError as e:
        raise SystemExit(f"Cannot use provider '{name}': {e}")
