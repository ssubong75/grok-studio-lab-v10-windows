#!/usr/bin/env python3
"""CLI for xAI Grok Imagine image/video generation and editing."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import mimetypes
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


API_BASE = "https://api.x.ai/v1"
DEFAULT_AUTH_FILE = "~/.grok/auth.json"
DEFAULT_IMAGE_MODEL = "grok-imagine-image-quality"
DEFAULT_VIDEO_MODEL = "grok-imagine-video"
AUTH_REFRESH_SKEW = dt.timedelta(minutes=5)


class CliError(Exception):
    pass


_HTTPS_CONTEXT: ssl.SSLContext | None = None


def https_context() -> ssl.SSLContext:
    global _HTTPS_CONTEXT
    if _HTTPS_CONTEXT is not None:
        return _HTTPS_CONTEXT
    if os.environ.get("GROK_STUDIO_INSECURE_TLS") == "1":
        _HTTPS_CONTEXT = ssl._create_unverified_context()
        return _HTTPS_CONTEXT
    macos_pem = load_macos_certificates()
    if macos_pem:
        _HTTPS_CONTEXT = ssl.create_default_context(cadata=macos_pem)
    else:
        _HTTPS_CONTEXT = ssl.create_default_context()
    return _HTTPS_CONTEXT


def load_macos_certificates() -> str | None:
    security = Path("/usr/bin/security")
    if not security.exists():
        return None
    try:
        result = subprocess.run(
            [
                str(security),
                "find-certificate",
                "-a",
                "-p",
                "/System/Library/Keychains/SystemRootCertificates.keychain",
                "/Library/Keychains/System.keychain",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode == 0 and "BEGIN CERTIFICATE" in result.stdout:
        return result.stdout
    return None


def format_network_error(exc: urllib.error.URLError) -> str:
    reason = getattr(exc, "reason", exc)
    message = str(reason)
    if "CERTIFICATE_VERIFY_FAILED" in message:
        message += (
            "\nTLS certificate verification failed. Run the Python "
            "Install Certificates.command for your Python version, then retry."
        )
    return message


def eprint(*values: Any) -> None:
    print(*values, file=sys.stderr)


def compact(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def auth_candidates(raw: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if isinstance(raw, dict):
        if isinstance(raw.get("key"), str):
            candidates.append(raw)
        for value in raw.values():
            if isinstance(value, dict) and isinstance(value.get("key"), str):
                candidates.append(value)
    return candidates


def token_needs_refresh(item: dict[str, Any], now: dt.datetime, force: bool = False) -> bool:
    if force:
        return True
    expires = parse_time(item.get("expires_at"))
    return expires is not None and expires <= now + AUTH_REFRESH_SKEW


def choose_auth_candidate(candidates: list[dict[str, Any]], force_refresh: bool = False) -> dict[str, Any]:
    now = dt.datetime.now(dt.timezone.utc)
    usable = [item for item in candidates if not token_needs_refresh(item, now, force_refresh)]
    return usable[0] if usable else candidates[0]


def discover_oidc_token_endpoint(issuer: str) -> str:
    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=https_context()) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise CliError(f"OAuth discovery failed: {format_network_error(exc)}") from exc
    try:
        config = json.loads(body)
    except json.JSONDecodeError as exc:
        raise CliError(f"OAuth discovery returned non-JSON response: {body[:500]}") from exc
    token_endpoint = config.get("token_endpoint")
    if not isinstance(token_endpoint, str):
        raise CliError("OAuth discovery did not include a token endpoint.")
    return token_endpoint


def refresh_oauth_token(auth_file: str, force: bool = False) -> str | None:
    auth_path = Path(auth_file).expanduser()
    if not auth_path.exists() or os.environ.get("XAI_API_KEY"):
        return None

    try:
        raw = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(f"Could not read auth file {auth_path}: {exc}") from exc

    candidates = auth_candidates(raw)
    if not candidates:
        return None

    item = choose_auth_candidate(candidates, force)
    if not token_needs_refresh(item, dt.datetime.now(dt.timezone.utc), force):
        return str(item["key"])

    refresh_token = item.get("refresh_token")
    issuer = item.get("oidc_issuer") or "https://auth.x.ai"
    client_id = item.get("oidc_client_id")
    if not isinstance(refresh_token, str) or not isinstance(client_id, str):
        if force:
            raise CliError("OAuth token was rejected and cannot be refreshed. Run `grok login` again.")
        return None

    form = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        discover_oidc_token_endpoint(str(issuer)),
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30, context=https_context()) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise CliError(f"OAuth refresh failed HTTP {exc.code}. Run `grok login` again.\n{body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise CliError(f"OAuth refresh network error: {format_network_error(exc)}") from exc

    try:
        refreshed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise CliError(f"OAuth refresh returned non-JSON response: {body[:500]}") from exc

    access_token = refreshed.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise CliError("OAuth refresh did not return an access token. Run `grok login` again.")

    item["key"] = access_token
    if isinstance(refreshed.get("refresh_token"), str):
        item["refresh_token"] = refreshed["refresh_token"]
    expires_in = refreshed.get("expires_in")
    if isinstance(expires_in, (int, float)):
        expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=float(expires_in))
        item["expires_at"] = expires_at.isoformat().replace("+00:00", "Z")

    temp = auth_path.with_suffix(".json.tmp")
    try:
        temp.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(temp, 0o600)
        temp.replace(auth_path)
    except OSError as exc:
        raise CliError(f"Could not update refreshed OAuth token: {exc}") from exc

    eprint("OAuth token refreshed from auth.json refresh_token.")
    return access_token


def load_api_key(args: argparse.Namespace) -> str:
    if args.api_key:
        return args.api_key
    if os.environ.get("XAI_API_KEY"):
        return os.environ["XAI_API_KEY"]

    auth_path = Path(args.auth_file).expanduser()
    if not auth_path.exists():
        raise CliError(
            "No API key found. Set XAI_API_KEY, pass --api-key, "
            f"or keep auth at {auth_path}."
        )

    try:
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(f"Could not read auth file {auth_path}: {exc}") from exc

    candidates = auth_candidates(auth)
    if not candidates:
        raise CliError(f"Could not find a nested 'key' field in {auth_path}.")

    refreshed = refresh_oauth_token(args.auth_file)
    if refreshed:
        return refreshed
    chosen = choose_auth_candidate(candidates)
    return chosen["key"]


class XaiClient:
    def __init__(self, api_key: str, base_url: str, timeout: float, refresh=None) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.refresh = refresh

    def request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._request(method, path, payload, retried=False)

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None, retried: bool = False
    ) -> dict[str, Any]:
        data = None
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=https_context()) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code in {401, 403} and self.refresh is not None and not retried:
                self.api_key = self.refresh()
                return self._request(method, path, payload, retried=True)
            raise CliError(f"xAI API error HTTP {exc.code}:\n{body}") from exc
        except urllib.error.URLError as exc:
            raise CliError(f"Network error: {format_network_error(exc)}") from exc

        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise CliError(f"API returned non-JSON response: {body[:500]}") from exc

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", path, payload)

    def get(self, path: str) -> dict[str, Any]:
        return self.request("GET", path)


def is_url(value: str) -> bool:
    return urllib.parse.urlparse(value).scheme in {"http", "https"}


def is_data_uri(value: str) -> bool:
    return value.startswith("data:")


def file_to_data_uri(path_text: str, default_mime: str) -> str:
    path = Path(path_text).expanduser()
    if not path.is_file():
        raise CliError(f"Input file does not exist: {path}")
    mime, _ = mimetypes.guess_type(path.name)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime or default_mime};base64,{encoded}"


def media_object(value: str, default_mime: str, image_type: bool = False) -> dict[str, Any]:
    if value.startswith("file-"):
        obj: dict[str, Any] = {"file_id": value}
    elif is_url(value) or is_data_uri(value):
        obj = {"url": value}
    else:
        obj = {"url": file_to_data_uri(value, default_mime)}
    if image_type and "url" in obj:
        obj["type"] = "image_url"
    return obj


def now_tag() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def safe_name(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return cleaned[:64] or fallback


def output_dir(args: argparse.Namespace) -> Path:
    path = Path(args.output_dir).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise CliError(f"Could not find available filename near {path}")


def write_json(out: Path, name: str, data: dict[str, Any]) -> Path:
    path = unique_path(out / f"{now_tag()}-{name}.json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def extension_from_url(url: str, fallback: str) -> str:
    suffix = Path(urllib.parse.urlparse(url).path).suffix
    return suffix if suffix and len(suffix) <= 8 else fallback


def extension_from_mime(mime: str | None, fallback: str) -> str:
    if mime:
        ext = mimetypes.guess_extension(mime.split(";")[0].strip())
        if ext:
            return ".jpg" if ext == ".jpe" else ext
    return fallback


def download(url: str, out: Path, stem: str, fallback_ext: str, timeout: float) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": "grok-media-cli/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=https_context()) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type")
    except urllib.error.URLError as exc:
        raise CliError(f"Could not download generated media: {format_network_error(exc)}") from exc

    ext = extension_from_mime(content_type, extension_from_url(url, fallback_ext))
    path = unique_path(out / f"{stem}{ext}")
    path.write_bytes(body)
    return path


def save_b64_image(item: dict[str, Any], out: Path, stem: str) -> Path:
    b64 = item.get("b64_json")
    if not isinstance(b64, str):
        raise CliError("Image response did not contain b64_json.")
    path = unique_path(out / f"{stem}{extension_from_mime(item.get('mime_type'), '.jpg')}")
    path.write_bytes(base64.b64decode(b64))
    return path


def print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def handle_images(result: dict[str, Any], args: argparse.Namespace, name: str) -> None:
    out = output_dir(args)
    metadata = write_json(out, name, result)
    files: list[str] = []
    urls: list[str] = []
    for index, item in enumerate(result.get("data", []), start=1):
        if not isinstance(item, dict):
            continue
        stem = f"{now_tag()}-{name}-{index}"
        if item.get("b64_json"):
            files.append(str(save_b64_image(item, out, stem)))
        elif isinstance(item.get("url"), str):
            urls.append(item["url"])
            if args.download:
                files.append(str(download(item["url"], out, stem, ".jpg", args.http_timeout)))
    print_json({"metadata": str(metadata), "files": files, "urls": urls, "usage": result.get("usage")})


def poll_video(client: XaiClient, request_id: str, interval: float, timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    last_progress = None
    while True:
        result = client.get(f"/videos/{urllib.parse.quote(request_id)}")
        status = result.get("status")
        progress = result.get("progress")
        if progress != last_progress:
            eprint(f"Video status: {status or 'unknown'} ({progress if progress is not None else '?'}%)")
            last_progress = progress
        if status == "done":
            return result
        if status in {"failed", "expired", "cancelled"}:
            raise CliError(json.dumps(result, ensure_ascii=False, indent=2))
        if time.monotonic() - started > timeout:
            raise CliError(f"Timed out. Use video-status {request_id} --wait later.")
        time.sleep(interval)


def save_video(result: dict[str, Any], args: argparse.Namespace, name: str, request_id: str) -> None:
    out = output_dir(args)
    metadata = write_json(out, name, result)
    files: list[str] = []
    video = result.get("video") if isinstance(result.get("video"), dict) else {}
    url = video.get("url") if isinstance(video, dict) else None
    if isinstance(url, str) and args.download:
        stem = f"{now_tag()}-{name}-{safe_name(request_id, 'video')}"
        files.append(str(download(url, out, stem, ".mp4", args.http_timeout)))
    print_json({"request_id": request_id, "metadata": str(metadata), "files": files, "url": url, "usage": result.get("usage")})


def submit_video(client: XaiClient, path: str, payload: dict[str, Any], args: argparse.Namespace, name: str) -> None:
    initial = client.post(path, payload)
    request_id = initial.get("request_id")
    if not isinstance(request_id, str):
        raise CliError(f"Video API response did not include request_id: {initial}")
    request_meta = write_json(output_dir(args), f"{name}-request", initial)
    if not args.poll:
        print_json({"request_id": request_id, "metadata": str(request_meta)})
        return
    save_video(poll_video(client, request_id, args.poll_interval, args.timeout_seconds), args, name, request_id)


def cmd_image_generate(client: XaiClient, args: argparse.Namespace) -> None:
    payload = compact({
        "model": args.model,
        "prompt": args.prompt,
        "n": args.n,
        "aspect_ratio": args.aspect_ratio,
        "resolution": args.resolution,
        "response_format": args.response_format,
    })
    handle_images(client.post("/images/generations", payload), args, "image-generate")


def cmd_image_edit(client: XaiClient, args: argparse.Namespace) -> None:
    if not 1 <= len(args.image) <= 3:
        raise CliError("Image editing supports 1 to 3 input images.")
    images = [media_object(value, "image/png", True) for value in args.image]
    payload = compact({
        "model": args.model,
        "prompt": args.prompt,
        "n": args.n,
        "aspect_ratio": args.aspect_ratio,
        "resolution": args.resolution,
        "response_format": args.response_format,
    })
    payload["image" if len(images) == 1 else "images"] = images[0] if len(images) == 1 else images
    handle_images(client.post("/images/edits", payload), args, "image-edit")


def cmd_video_generate(client: XaiClient, args: argparse.Namespace) -> None:
    if args.image and args.reference_image:
        raise CliError("Use either --image or --reference-image, not both.")
    if args.reference_image and len(args.reference_image) > 7:
        raise CliError("Reference-to-video supports at most 7 reference images.")
    payload = compact({
        "model": args.model,
        "prompt": args.prompt,
        "duration": args.duration,
        "aspect_ratio": args.aspect_ratio,
        "resolution": args.resolution,
    })
    if args.image:
        payload["image"] = media_object(args.image, "image/png")
    if args.reference_image:
        payload["reference_images"] = [media_object(value, "image/png") for value in args.reference_image]
    submit_video(client, "/videos/generations", payload, args, "video-generate")


def cmd_video_edit(client: XaiClient, args: argparse.Namespace) -> None:
    submit_video(
        client,
        "/videos/edits",
        {"model": args.model, "prompt": args.prompt, "video": media_object(args.video, "video/mp4")},
        args,
        "video-edit",
    )


def cmd_video_extend(client: XaiClient, args: argparse.Namespace) -> None:
    payload = compact({
        "model": args.model,
        "prompt": args.prompt,
        "duration": args.duration,
        "video": media_object(args.video, "video/mp4"),
    })
    submit_video(client, "/videos/extensions", payload, args, "video-extend")


def cmd_video_status(client: XaiClient, args: argparse.Namespace) -> None:
    result = (
        poll_video(client, args.request_id, args.poll_interval, args.timeout_seconds)
        if args.wait
        else client.get(f"/videos/{urllib.parse.quote(args.request_id)}")
    )
    if result.get("status") == "done":
        save_video(result, args, "video-status", args.request_id)
    else:
        metadata = write_json(output_dir(args), "video-status", result)
        data = dict(result)
        data["metadata"] = str(metadata)
        print_json(data)


def add_auth_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--api-key")
    parser.add_argument("--auth-file", default=DEFAULT_AUTH_FILE)
    parser.add_argument("--base-url", default=API_BASE)
    parser.add_argument("--http-timeout", type=float, default=120.0)


def add_image_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", default=DEFAULT_IMAGE_MODEL)
    parser.add_argument("--n", type=int)
    parser.add_argument("--aspect-ratio")
    parser.add_argument("--resolution")
    parser.add_argument("--response-format", choices=["url", "b64_json"], default="url")
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--no-download", action="store_false", dest="download")
    parser.set_defaults(download=True)


def add_video_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", default=DEFAULT_VIDEO_MODEL)
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--no-download", action="store_false", dest="download")
    parser.add_argument("--no-poll", action="store_false", dest="poll")
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.set_defaults(download=True, poll=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate/edit media with xAI Grok Imagine.")
    add_auth_options(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("image-generate")
    p.add_argument("prompt")
    add_image_options(p)
    p.set_defaults(handler=cmd_image_generate)

    p = sub.add_parser("image-edit")
    p.add_argument("prompt")
    p.add_argument("--image", action="append", required=True)
    add_image_options(p)
    p.set_defaults(handler=cmd_image_edit)

    p = sub.add_parser("video-generate")
    p.add_argument("prompt")
    p.add_argument("--image")
    p.add_argument("--reference-image", action="append")
    p.add_argument("--duration", type=int)
    p.add_argument("--aspect-ratio")
    p.add_argument("--resolution")
    add_video_options(p)
    p.set_defaults(handler=cmd_video_generate)

    p = sub.add_parser("video-edit")
    p.add_argument("prompt")
    p.add_argument("--video", required=True)
    add_video_options(p)
    p.set_defaults(handler=cmd_video_edit)

    p = sub.add_parser("video-extend")
    p.add_argument("prompt")
    p.add_argument("--video", required=True)
    p.add_argument("--duration", type=int)
    add_video_options(p)
    p.set_defaults(handler=cmd_video_extend)

    p = sub.add_parser("video-status")
    p.add_argument("request_id")
    p.add_argument("--wait", action="store_true")
    p.add_argument("--output-dir", default="outputs")
    p.add_argument("--no-download", action="store_false", dest="download")
    p.add_argument("--poll-interval", type=float, default=5.0)
    p.add_argument("--timeout-seconds", type=float, default=600.0)
    p.set_defaults(download=True, handler=cmd_video_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        refresh = None if args.api_key or os.environ.get("XAI_API_KEY") else lambda: refresh_oauth_token(args.auth_file, force=True) or load_api_key(args)
        client = XaiClient(load_api_key(args), args.base_url, args.http_timeout, refresh=refresh)
        args.handler(client, args)
    except CliError as exc:
        eprint(str(exc))
        return 1
    except KeyboardInterrupt:
        eprint("Interrupted.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
