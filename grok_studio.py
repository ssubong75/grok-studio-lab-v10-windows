#!/usr/bin/env python3
"""Grok Studio: local-only web UI for Grok Imagine media workflows."""

from __future__ import annotations

import argparse
import base64
import binascii
import concurrent.futures
import datetime as dt
import errno
import html
import json
import mimetypes
import os
import re
import select
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


APP_NAME = "Grok Studio Lab"
API_BASE = "https://api.x.ai/v1"
DEFAULT_AUTH_FILE = "~/.grok/auth.json"
DEFAULT_IMAGE_MODEL = "grok-imagine-image"
DEFAULT_VIDEO_MODEL = "grok-imagine-video"
DEFAULT_ANALYZE_MODEL = "grok-4.3"
ANALYZE_MODELS = {"grok-4.3", "grok-4.20-0309-non-reasoning"}
DEFAULT_LIBRARY_FOLDER_PATH = str(Path.home() / "Documents" / "Grok Studio Lab Library")
IMAGE_IMPORT_EXTENSIONS = {".avif", ".bmp", ".gif", ".heic", ".heif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
VIDEO_IMPORT_EXTENSIONS = {".m4v", ".mov", ".mp4", ".mpeg", ".mpg", ".webm"}
TEXT_IMPORT_EXTENSIONS = {".text", ".txt"}
ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "studio_static"
DATA_DIR = Path(os.environ.get("GROK_STUDIO_DATA_DIR") or ROOT / "grok_studio_data").expanduser().resolve()
MEDIA_DIR = DATA_DIR / "media"
META_DIR = DATA_DIR / "metadata"
TMP_DIR = DATA_DIR / "tmp"
DB_PATH = DATA_DIR / "library.json"
SETTINGS_PATH = DATA_DIR / "settings.json"
EXTERNAL_META_DIR_NAME = ".grok_studio"
ACCOUNTS_PATH = DATA_DIR / "accounts.json"
ACCOUNT_AUTH_DIR = DATA_DIR / "account_auth"
ACCOUNT_TIER_VALUES = {"free", "super", "heavy"}
USAGE_CACHE_PATH = DATA_DIR / "usage.json"
IMAGINE_SESSION_PATH = DATA_DIR / "imagine_session.json"
IMAGINE_DELETED_CONVERSATION_CACHE_PATH = DATA_DIR / "imagine_deleted_conversation_cache.json"
IMAGINE_SAVED_KEYS_CACHE_SECONDS = 300
IMAGINE_PROFILE_DIR = DATA_DIR / "imagine_chrome_profile"
IMAGINE_DEBUG_PORT = int(os.environ.get("GROK_STUDIO_IMAGINE_DEBUG_PORT", "9223"))
IMAGINE_POPUP_WINDOW_SIZE = (860, 760)
IMAGINE_BASE = "https://grok.com"
IMAGINE_WS_URL = "wss://grok.com/ws/imagine/listen"
IMAGINE_IMAGE_CONFIRM_SECONDS = float(os.environ.get("GROK_STUDIO_IMAGINE_CONFIRM_SECONDS", "75"))
IMAGINE_VIDEO_HANDOFF_SECONDS = float(os.environ.get("GROK_STUDIO_IMAGINE_VIDEO_HANDOFF_SECONDS", "240"))
IMAGINE_VIDEO_PAGE_SCAN_SECONDS = float(os.environ.get("GROK_STUDIO_IMAGINE_VIDEO_PAGE_SCAN_SECONDS", "2"))
IMAGINE_VIDEO_BASELINE_SECONDS = float(os.environ.get("GROK_STUDIO_IMAGINE_VIDEO_BASELINE_SECONDS", "6"))
IMAGINE_VIDEO_PROGRESS_GRACE_SECONDS = float(os.environ.get("GROK_STUDIO_IMAGINE_VIDEO_PROGRESS_GRACE_SECONDS", "180"))
IMAGINE_VIDEO_MAX_WAIT_SECONDS = float(os.environ.get("GROK_STUDIO_IMAGINE_VIDEO_MAX_WAIT_SECONDS", "900"))
IMAGINE_I2V_INLINE_IMAGE_BYTES = int(os.environ.get("GROK_STUDIO_IMAGINE_I2V_INLINE_IMAGE_BYTES", str(12 * 1024 * 1024)))
IMAGINE_I2V_MAX_INLINE_IMAGE_BYTES = int(os.environ.get("GROK_STUDIO_IMAGINE_I2V_MAX_INLINE_IMAGE_BYTES", str(28 * 1024 * 1024)))
MAX_BODY = 180 * 1024 * 1024
AUTH_REFRESH_SKEW = dt.timedelta(minutes=5)
USAGE_URL = os.environ.get("GROK_STUDIO_USAGE_URL", "https://grok.com/?_s=usage")
USAGE_CACHE_SECONDS = 45
_AUTH_LOCK = threading.RLock()
_IMAGINE_DELETED_CACHE_LOCK = threading.RLock()
_SYSTEM_FONT_CACHE: list[str] | None = None


class StudioError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class JobCancelled(Exception):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def log_event(message: str) -> None:
    stamp = dt.datetime.now().strftime("%H:%M:%S")
    print(f"[Grok Studio {stamp}] {message}", flush=True)


_HTTPS_CONTEXT: ssl.SSLContext | None = None


def https_context() -> ssl.SSLContext:
    """Return an HTTPS context that works with python.org Python on macOS."""
    global _HTTPS_CONTEXT
    if _HTTPS_CONTEXT is not None:
        return _HTTPS_CONTEXT

    if os.environ.get("GROK_STUDIO_INSECURE_TLS") == "1":
        log_event("warning: TLS certificate verification is disabled by GROK_STUDIO_INSECURE_TLS=1")
        _HTTPS_CONTEXT = ssl._create_unverified_context()
        return _HTTPS_CONTEXT

    macos_pem = load_macos_certificates()
    if macos_pem:
        _HTTPS_CONTEXT = ssl.create_default_context(cadata=macos_pem)
        log_event("using macOS SystemRootCertificates keychain for HTTPS")
    else:
        _HTTPS_CONTEXT = ssl.create_default_context()
    return _HTTPS_CONTEXT


def load_macos_certificates() -> str | None:
    security = Path("/usr/bin/security")
    if not security.exists():
        return None
    keychains = [
        "/System/Library/Keychains/SystemRootCertificates.keychain",
        "/Library/Keychains/System.keychain",
    ]
    try:
        result = subprocess.run(
            [str(security), "find-certificate", "-a", "-p", *keychains],
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
            "\nTLS certificate verification failed. Grok Studio tried the macOS "
            "system certificate keychain fallback. If it still fails, run the "
            "Python Install Certificates.command for your Python version, then "
            "restart Grok Studio."
        )
    return message


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


def safe_name(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return cleaned[:80] or fallback


def safe_file_stem(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", " ", value.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned[:90] or fallback


def safe_account_folder_name(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned[:80] or fallback


def normalize_media_api_url(url: str | None) -> str | None:
    if not isinstance(url, str) or not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return IMAGINE_BASE + url
    return url


def canonical_media_key(value: Any) -> str:
    url = normalize_media_api_url(value if isinstance(value, str) else None)
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(parsed.path)
    return urllib.parse.urlunparse(parsed._replace(path=path, query="", fragment=""))


def imagine_post_text(post: dict[str, Any]) -> str:
    keys = ("prompt", "text", "caption", "description", "title", "altText", "alt")
    for key in keys:
        value = post.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for holder_key in ("message", "input", "metadata", "properties"):
        holder = post.get(holder_key)
        if not isinstance(holder, dict):
            continue
        for key in keys:
            value = holder.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def is_numeric_date_like_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if len(text) < 6 or len(text) > 96:
        return False
    if re.search(r"[A-Za-z가-힣]", text):
        return False
    digits = re.sub(r"\D+", "", text)
    if len(digits) < 6:
        return False
    if not re.fullmatch(r"[\d\s:._,/-]+", text):
        return False
    return bool(re.search(r"(?:19|20)\d{2}", digits))


def prompt_surrogate_from_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if is_numeric_date_like_text(text):
        return text
    patterns = (
        r"prompt\s*:\s*['\"]([^'\"]{6,96})['\"]",
        r"prompt\s*:\s*([^.\n\r]{6,96})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = match.group(1).strip(" \t\r\n'\".。")
        if is_numeric_date_like_text(candidate):
            return candidate
    return ""


def prompt_like_text_values(value: Any, max_depth: int = 5, max_hits: int = 80) -> list[tuple[str, str]]:
    prompt_key = re.compile(r"(prompt|caption|description|summary|title|text|message|query|input|content)", re.IGNORECASE)
    hits: list[tuple[str, str]] = []
    stack: list[tuple[Any, str, int]] = [(value, "", 0)]
    seen: set[int] = set()
    while stack and len(hits) < max_hits:
        current, path, depth = stack.pop()
        if depth > max_depth:
            continue
        if isinstance(current, dict):
            current_id = id(current)
            if current_id in seen:
                continue
            seen.add(current_id)
            for key, child in current.items():
                key_text = str(key or "")
                child_path = f"{path}.{key_text}" if path else key_text
                if isinstance(child, str):
                    if prompt_key.search(key_text):
                        hits.append((child_path, child))
                        if len(hits) >= max_hits:
                            break
                elif isinstance(child, (dict, list)):
                    stack.append((child, child_path, depth + 1))
        elif isinstance(current, list):
            current_id = id(current)
            if current_id in seen:
                continue
            seen.add(current_id)
            for index, child in enumerate(current[:200]):
                if isinstance(child, (dict, list)):
                    stack.append((child, f"{path}[{index}]", depth + 1))
    return hits


def imagine_post_created_at(post: dict[str, Any]) -> str:
    for key in ("createTime", "createdAt", "created_at", "updatedAt", "updateTime"):
        parsed = parse_time(post.get(key))
        if parsed:
            return parsed.isoformat().replace("+00:00", "Z")
    return utc_now()


def imagine_post_group_id(post: dict[str, Any]) -> str:
    value = post.get("_grokImportGroupId")
    if isinstance(value, str) and value.strip():
        return value.strip()
    for key in ("parentPostId", "originalPostId", "rootPostId", "conversationId", "id"):
        value = post.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return uuid.uuid4().hex


def imagine_post_parent_id(post: dict[str, Any]) -> str | None:
    value = post.get("_grokImportParentId")
    if isinstance(value, str) and value.strip():
        return value.strip()
    for key in ("parentPostId", "originalPostId", "rootPostId"):
        value = post.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def imagine_related_post_ids(post: dict[str, Any]) -> list[str]:
    related: list[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and value.strip() and value.strip() not in related:
            related.append(value.strip())

    for key in (
        "id",
        "parentPostId",
        "originalPostId",
        "rootPostId",
        "conversationId",
        "sourcePostId",
        "mediaPostId",
        "videoPostId",
        "imagePostId",
    ):
        add(post.get(key))
    stack = [post]
    seen = 0
    while stack and seen < 400:
        seen += 1
        item = stack.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                key_text = str(key).lower()
                if (("post" in key_text and key_text.endswith("id")) or key_text in {"id", "parentid", "conversationid"}):
                    add(value)
                elif isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(item, list):
            stack.extend(value for value in item if isinstance(value, (dict, list)))
    return related[:30]


def imagine_import_source_post_ids(post: dict[str, Any]) -> list[str]:
    related: list[str] = []
    current_id = str(post.get("id") or "").strip()
    for key in ("parentPostId", "originalPostId", "rootPostId", "sourcePostId", "imagePostId"):
        value = post.get(key)
        if isinstance(value, str):
            value = value.strip()
            if value and value != current_id and value not in related:
                related.append(value)
    return related


def normalize_identity_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def imagine_post_identity_values(post: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    identity_tokens = ("email", "user", "owner", "author", "creator", "account", "profile", "handle", "username")
    stack: list[Any] = [post]
    seen = 0
    while stack and seen < 800:
        seen += 1
        item = stack.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                key_text = str(key).lower()
                if isinstance(value, str) and any(token in key_text for token in identity_tokens):
                    normalized = normalize_identity_text(value)
                    if normalized:
                        values.add(normalized)
                elif isinstance(value, (int, float)) and any(token in key_text for token in identity_tokens):
                    normalized = normalize_identity_text(value)
                    if normalized:
                        values.add(normalized)
                elif isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(item, list):
            stack.extend(value for value in item if isinstance(value, (dict, list)))
    return values


def imagine_post_has_positive_ownership_hint(post: dict[str, Any]) -> bool:
    stack: list[Any] = [post]
    seen = 0
    positive_keys = {"isMine", "isOwner", "isOwned", "ownedByMe", "createdByMe", "isSelf", "isCurrentUser"}
    while stack and seen < 800:
        seen += 1
        item = stack.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                if str(key) in positive_keys and bool(value):
                    return True
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(item, list):
            stack.extend(value for value in item if isinstance(value, (dict, list)))
    return False


def imagine_post_has_negative_import_hint(post: dict[str, Any]) -> bool:
    stack: list[Any] = [post]
    seen = 0
    negative_keys = {"isPublic", "public", "isFeatured", "featured", "isSample", "sample", "recommended", "isRecommended", "isTemplate", "template"}
    while stack and seen < 800:
        seen += 1
        item = stack.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                if str(key) in negative_keys and bool(value):
                    return True
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(item, list):
            stack.extend(value for value in item if isinstance(value, (dict, list)))
    return False


def imagine_post_has_media_shape(post: dict[str, Any]) -> bool:
    return bool(
        post.get("mediaType")
        or post.get("mediaUrl")
        or post.get("hdMediaUrl")
        or post.get("hd1080MediaUrl")
    )


def imagine_post_has_deleted_hint(post: dict[str, Any]) -> bool:
    stack: list[Any] = [post]
    seen = 0
    deleted_keys = {
        "deleted",
        "isDeleted",
        "is_deleted",
        "trashed",
        "isTrashed",
        "is_trashed",
        "inTrash",
        "isInTrash",
        "archived",
        "isArchived",
    }
    deleted_tokens = ("deleted", "trash", "trashed", "recycle")
    while stack and seen < 900:
        seen += 1
        item = stack.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                key_text = str(key)
                key_lower = key_text.lower()
                if key_text in deleted_keys and bool(value):
                    return True
                if any(token in key_lower for token in deleted_tokens) and bool(value):
                    return True
                if isinstance(value, str):
                    value_lower = value.strip().lower()
                    negative_deleted_text = value_lower.startswith(("not_", "un")) or value_lower in {"false", "0", "active"}
                    deleted_value = (
                        value_lower in {"deleted", "trashed", "trash", "media_post_state_deleted", "state_deleted"}
                        or value_lower.endswith(("_deleted", "_trashed"))
                    )
                    if deleted_value and not negative_deleted_text:
                        return True
                elif isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(item, list):
            stack.extend(value for value in item if isinstance(value, (dict, list)))
    return False


def walk_asset_identity_values(value: Any, max_depth: int = 8, max_hits: int = 300) -> list[str]:
    identity_key = re.compile(r"(asset|media|file|image|video).*(id|key|url)|^(id|assetId|key|url)$", re.IGNORECASE)
    values: list[str] = []
    stack: list[tuple[Any, str, int]] = [(value, "", 0)]
    seen: set[int] = set()
    while stack and len(values) < max_hits:
        current, path, depth = stack.pop()
        if depth > max_depth:
            continue
        if isinstance(current, dict):
            current_id = id(current)
            if current_id in seen:
                continue
            seen.add(current_id)
            for key, child in current.items():
                key_text = str(key or "")
                child_path = f"{path}.{key_text}" if path else key_text
                if isinstance(child, str):
                    if identity_key.search(child_path) and child.strip() and child.strip() not in values:
                        values.append(child.strip())
                elif isinstance(child, (int, float)):
                    if identity_key.search(child_path):
                        text = str(child).strip()
                        if text and text not in values:
                            values.append(text)
                elif isinstance(child, (dict, list)):
                    stack.append((child, child_path, depth + 1))
        elif isinstance(current, list):
            current_id = id(current)
            if current_id in seen:
                continue
            seen.add(current_id)
            for index, child in enumerate(current[:300]):
                if isinstance(child, (dict, list)):
                    stack.append((child, f"{path}[{index}]", depth + 1))
    return values


def walk_strings(value: Any) -> list[str]:
    found: list[str] = []
    stack = [value]
    seen = 0
    while stack and seen < 2000:
        seen += 1
        item = stack.pop()
        if isinstance(item, str):
            found.append(item)
        elif isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return found


def media_extensions(kind: str) -> tuple[str, ...]:
    return (".mp4", ".mov", ".webm", ".m4v") if kind == "video" else (".jpg", ".jpeg", ".png", ".webp", ".gif")


def is_grok_user_content_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = urllib.parse.unquote(parsed.path).lower().rstrip("/")
    return (
        host == "assets.grok.com"
        and re.search(r"/users/[0-9a-f-]{24,}/[0-9a-f-]{24,}/content$", path) is not None
    )


def media_url_matches_account(url: str, account: dict[str, Any]) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    if host != "assets.grok.com":
        return False
    text = normalize_identity_text(f"{parsed.netloc}{urllib.parse.unquote(parsed.path)}")
    values = {
        normalize_identity_text(account.get("id")),
        normalize_identity_text(account.get("email")),
        normalize_identity_text(account.get("label")),
    }
    for value in account.get("identity_values") or []:
        values.add(normalize_identity_text(value))
    return any(value and len(value) >= 12 and value in text for value in values)


def normalize_media_url_candidate(text: str) -> str | None:
    if not isinstance(text, str) or "http" not in text:
        return None
    start = text.find("http")
    clean = html.unescape(text[start:])
    clean = clean.replace("\\u0026", "&").replace("\\/", "/")
    clean = clean.split("\\", 1)[0].split('"', 1)[0].split("'", 1)[0]
    clean = clean.rstrip("),].} \n\r\t")
    parsed = urllib.parse.urlparse(clean)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return clean


def media_url_score(url: str, kind: str) -> int:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = urllib.parse.unquote(parsed.path).lower()
    query = urllib.parse.unquote(parsed.query).lower()
    text = f"{host}{path}?{query}"
    extensions = media_extensions(kind)
    has_extension = path.endswith(extensions)
    score = 0
    if kind == "video" and "imagine-public.x.ai" in host and "/share-videos/" in path and has_extension:
        score += 180
    if "assets.grok.com" in host:
        score += 90
    if is_grok_user_content_url(url):
        score += 55
    if any(token in host for token in ("x.ai", "grok.com")):
        score += 12
    if "generated" in text:
        score += 45
    if "/users/" in path:
        score += 20
    if has_extension:
        score += 35
    if kind == "video" and any(token in text for token in ("video", "mp4", "mov", "webm")):
        score += 25
    if kind == "image" and any(token in text for token in ("image", "img", "jpg", "jpeg", "png", "webp")):
        score += 18
    if any(token in text for token in ("thumbnail", "thumb", "preview", "poster", "blur", "small", "avatar", "profile", "icon", "favicon")):
        score -= 60
    if kind == "video" and (
        not has_extension
        or path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".webmanifest"))
        or any(token in text for token in ("preview_image", "thumbnail", "_thumbnail", "share-images", "manifest.webmanifest"))
        or ("data.x.ai" in host and "/releases/imagine/" in path)
    ):
        score -= 250
    if "/api/" in path or "/rest/" in path:
        score -= 80
    return score


def is_supported_video_url_candidate(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = urllib.parse.unquote(parsed.path).lower()
    query = urllib.parse.unquote(parsed.query).lower()
    text = f"{host}{path}?{query}"
    if not path.endswith(media_extensions("video")):
        return False
    if path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".webmanifest")):
        return False
    if any(token in text for token in ("preview_image", "thumbnail", "_thumbnail", "share-images", "manifest.webmanifest", "favicon")):
        return False
    if "data.x.ai" in host and "/releases/imagine/" in path:
        return False
    return True


def is_possible_video_url_candidate(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = urllib.parse.unquote(parsed.path).lower()
    query = urllib.parse.unquote(parsed.query).lower()
    text = f"{host}{path}?{query}"
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    if path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".webmanifest")):
        return False
    if any(token in text for token in ("preview_image", "thumbnail", "_thumbnail", "share-images", "manifest.webmanifest", "favicon")):
        return False
    if is_supported_video_url_candidate(url):
        return True
    return any(token in text for token in ("generated_video", "share-videos", "/video", "video_", "-video", "mp4", "mov", "webm"))


def is_possible_image_url_candidate(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = urllib.parse.unquote(parsed.path).lower()
    query = urllib.parse.unquote(parsed.query).lower()
    text = f"{host}{path}?{query}"
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    if is_possible_video_url_candidate(url):
        return False
    if path.endswith((".svg", ".webmanifest")):
        return False
    if any(token in text for token in ("favicon", "avatar", "icon", "logo", "sprite")):
        return False
    if path.endswith(tuple(IMAGE_IMPORT_EXTENSIONS)):
        return True
    if is_grok_user_content_url(url):
        return True
    return any(token in text for token in ("share-images", "preview_image", "thumbnailimage", "image", "/img", "jpg", "jpeg", "png", "webp"))


def remote_display_url_score(url: str, kind: str) -> int:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = urllib.parse.unquote(parsed.path).lower()
    score = media_url_score(url, kind)
    if kind == "image" and "imagine-public.x.ai" in host and "/share-images/" in path:
        score += 180
    if kind == "video" and "imagine-public.x.ai" in host and "/share-videos/" in path:
        score += 180
    if path.endswith(media_extensions(kind)):
        score += 80
    if "assets.grok.com" in host and "/users/" in path:
        score += 30
    return score


def imagine_remote_media_proxy_url(url: str, kind: str) -> str:
    return "/api/imagine/remote/media?" + urllib.parse.urlencode({"kind": kind, "url": url})


def predicted_imagine_video_url(media_url: str | None, post_id: str | None) -> str | None:
    url = normalize_media_api_url(media_url)
    if not url:
        return None
    parsed = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(parsed.path)
    if "/generated/" in path and path.endswith("/preview_image.jpg"):
        return urllib.parse.urlunparse(parsed._replace(path=path.rsplit("/", 1)[0] + "/generated_video.mp4"))
    if post_id and "/generated/" in path:
        prefix = path.split("/generated/", 1)[0]
        return urllib.parse.urlunparse(parsed._replace(path=f"{prefix}/generated/{post_id}/generated_video.mp4", query="cache=1"))
    return None


def extract_media_urls(value: Any, kind: str) -> list[str]:
    extensions = media_extensions(kind)
    candidates: list[str] = []
    for text in walk_strings(value):
        expanded = text.replace("\\u0026", "&").replace("\\/", "/")
        fragments = [text]
        fragments.extend(match.group(0) for match in re.finditer(r"https?://[^\s\"'<>]+", expanded))
        for fragment in fragments:
            url = normalize_media_url_candidate(fragment)
            if not url:
                continue
            parsed = urllib.parse.urlparse(url)
            host = parsed.netloc.lower()
            path = urllib.parse.unquote(parsed.path).lower()
            full = f"{host}{path}?{urllib.parse.unquote(parsed.query).lower()}"
            has_extension = path.endswith(extensions)
            if kind == "video":
                looks_like_media = is_possible_video_url_candidate(url)
            else:
                looks_like_media = (
                    has_extension
                    or ("assets.grok.com" in host and any(token in full for token in ("generated", "image", "video", "media")))
                    or any(token in full for token in ("generated_image", "generated_video", "image_asset", "video_asset"))
                )
            if looks_like_media and url not in candidates:
                candidates.append(url)
    return sorted(candidates, key=lambda candidate: media_url_score(candidate, kind), reverse=True)


def extract_media_url(value: Any, kind: str) -> str | None:
    urls = extract_media_urls(value, kind)
    return urls[0] if urls else None


def parse_json_or_sse_body(body: str) -> dict[str, Any]:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    if parsed is not None:
        return {"response": parsed}

    events: list[Any] = []
    current_event = ""
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("event:"):
            current_event = line[6:].strip()
            continue
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            event_value: Any = json.loads(data)
        except json.JSONDecodeError:
            event_value = {"text": data}
        if isinstance(event_value, dict) and current_event:
            event_value = {"event": current_event, **event_value}
        events.append(event_value)
        current_event = ""
    if events:
        return {"events": events, "response": events[-1]}
    raise StudioError(f"Imagine returned non-JSON response: {body[:500]}", 502)


def debug_media_url(url: str) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(url)
    query_keys = sorted(urllib.parse.parse_qs(parsed.query, keep_blank_values=True).keys())
    safe_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    return {
        "url": safe_url,
        "host": parsed.netloc,
        "path": parsed.path,
        "query_keys": query_keys,
        "score_image": media_url_score(url, "image"),
        "score_video": media_url_score(url, "video"),
    }


def sniff_image_mime(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:6] in {b"GIF87a", b"GIF89a"}:
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"\x00\x00\x00") and data[4:8] in {b"avif", b"heic", b"heix", b"hevc", b"mif1"}:
        return "image/avif"
    return None


def decode_image_blob_string(text: str) -> dict[str, str] | None:
    if not isinstance(text, str) or len(text) < 40:
        return None
    data_uri = re.match(r"^data:(image/[A-Za-z0-9.+-]+);base64,(.+)$", text, re.DOTALL)
    if data_uri:
        mime = data_uri.group(1).lower()
        encoded = re.sub(r"\s+", "", data_uri.group(2))
    else:
        if "http" in text[:20] or not re.fullmatch(r"[A-Za-z0-9+/=\s_-]+", text):
            return None
        encoded = re.sub(r"\s+", "", text).replace("-", "+").replace("_", "/")
        mime = "image/png"
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return None
    detected = sniff_image_mime(data)
    if not detected:
        return None
    return {"b64_json": base64.b64encode(data).decode("ascii"), "mime_type": detected or mime}


def extract_image_blob_payload(value: Any) -> dict[str, str] | None:
    stack = [value]
    seen = 0
    while stack and seen < 2000:
        seen += 1
        item = stack.pop()
        if isinstance(item, str):
            payload = decode_image_blob_string(item)
            if payload:
                return payload
        elif isinstance(item, dict):
            for key in ("blob", "data", "b64_json", "base64", "image", "content"):
                child = item.get(key)
                if isinstance(child, str):
                    payload = decode_image_blob_string(child)
                    if payload:
                        return payload
            stack.extend(child for child in item.values() if isinstance(child, (dict, list)))
        elif isinstance(item, list):
            stack.extend(item)
    return None


def extract_values_for_keys(value: Any, keys: set[str]) -> list[str]:
    found: list[str] = []
    stack = [value]
    seen = 0
    while stack and seen < 2000:
        seen += 1
        item = stack.pop()
        if isinstance(item, dict):
            for key, child in item.items():
                if str(key) in keys and isinstance(child, str) and child and child not in found:
                    found.append(child)
                if isinstance(child, (dict, list)):
                    stack.append(child)
        elif isinstance(item, list):
            stack.extend(item)
    return found


def imagine_public_image_candidates_from_ids(ids: list[str]) -> list[str]:
    candidates: list[str] = []
    for value in ids:
        if not re.fullmatch(r"[0-9a-fA-F-]{24,64}", value):
            continue
        for ext in (".png", ".jpg", ".webp"):
            url = f"https://imagine-public.x.ai/imagine-public/images/{value}{ext}"
            if url not in candidates:
                candidates.append(url)
    return candidates


def debug_json_value(value: Any) -> Any:
    if isinstance(value, str):
        if value.startswith("http"):
            return debug_media_url(value)
        return {"type": "str", "length": len(value), "prefix": value[:120]}
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return {"type": "list", "length": len(value)}
    if isinstance(value, dict):
        return {"type": "dict", "keys": sorted(str(key) for key in value.keys())[:40]}
    return {"type": type(value).__name__}


def debug_event_fields(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    fields: dict[str, Any] = {}
    for key in (
        "type",
        "id",
        "image_id",
        "job_id",
        "request_id",
        "url",
        "blob",
        "percentage_complete",
        "current_status",
        "status",
        "moderated",
        "confirmation",
    ):
        if key in value:
            fields[key] = debug_json_value(value[key])
    return fields


def event_progress(value: Any) -> float | None:
    if not isinstance(value, dict):
        return None
    progress = value.get("percentage_complete")
    if isinstance(progress, (int, float)):
        return float(progress)
    if isinstance(progress, str):
        try:
            return float(progress.strip().rstrip("%"))
        except ValueError:
            return None
    return None


def event_status_text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    parts = []
    for key in ("current_status", "status", "type", "confirmation"):
        child = value.get(key)
        if isinstance(child, str):
            parts.append(child.lower())
    return " ".join(parts)


def is_final_image_event(value: Any) -> bool:
    progress = event_progress(value)
    if progress is not None and progress >= 99:
        return True
    status = event_status_text(value)
    return any(token in status for token in ("complete", "completed", "done", "success", "final"))


def debug_event_shape(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        keys = sorted(str(key) for key in value.keys())[:40]
        return {
            "type": value.get("type") or value.get("event") or value.get("messageType"),
            "status": value.get("status"),
            "keys": keys,
        }
    if isinstance(value, list):
        return {"type": "list", "length": len(value)}
    return {"type": type(value).__name__}


def extract_first_key(value: Any, keys: set[str]) -> str | None:
    stack = [value]
    seen = 0
    while stack and seen < 2000:
        seen += 1
        item = stack.pop()
        if isinstance(item, dict):
            for key, child in item.items():
                if str(key) in keys and isinstance(child, str) and child:
                    return child
                if isinstance(child, (dict, list)):
                    stack.append(child)
        elif isinstance(item, list):
            stack.extend(item)
    return None


def extract_uuid_from_text(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    match = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", value)
    return match.group(0) if match else None


def extract_imagine_post_id_from_url(url: str | None) -> str | None:
    if not isinstance(url, str):
        return None
    path = urllib.parse.unquote(urllib.parse.urlparse(url).path)
    uuid_pattern = r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
    for pattern in (
        rf"/users/{uuid_pattern}/{uuid_pattern}/content",
        rf"/generated/{uuid_pattern}/",
        rf"/imagine/post/{uuid_pattern}",
    ):
        match = re.search(pattern, path)
        if match:
            return match.group(match.lastindex or 1)
    return extract_uuid_from_text(url)


def scrub_inline_media_for_metadata(value: Any, depth: int = 0) -> Any:
    if depth > 8:
        return "[depth-limit]"
    if isinstance(value, str):
        if value.startswith("data:") or len(value) > 2000:
            return f"[string:{len(value)}]"
        return value
    if isinstance(value, list):
        return [scrub_inline_media_for_metadata(item, depth + 1) for item in value[:200]]
    if isinstance(value, dict):
        scrubbed: dict[str, Any] = {}
        for key, child in list(value.items())[:300]:
            key_text = str(key).lower()
            if key_text in {"blob", "b64_json", "base64", "bytes", "data"}:
                scrubbed[key] = f"[omitted:{len(str(child))}]"
            else:
                scrubbed[key] = scrub_inline_media_for_metadata(child, depth + 1)
        return scrubbed
    return value


def imagine_model_name(kind: str) -> str:
    return "imagine-x-1" if kind == "image" else "imagine-video-gen"


def compact(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None and value != ""}


def ensure_dirs() -> None:
    STATIC_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)
    MEDIA_DIR.mkdir(exist_ok=True)
    META_DIR.mkdir(exist_ok=True)
    TMP_DIR.mkdir(exist_ok=True)
    ACCOUNT_AUTH_DIR.mkdir(exist_ok=True)
    IMAGINE_PROFILE_DIR.mkdir(exist_ok=True)


def read_settings() -> dict[str, Any]:
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def write_settings(settings: dict[str, Any]) -> None:
    ensure_dirs()
    temp = SETTINGS_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(SETTINGS_PATH)


def external_library_root() -> Path | None:
    root = read_settings().get("library_root")
    if not isinstance(root, str) or not root.strip():
        return None
    try:
        return Path(root).expanduser().resolve()
    except OSError:
        return None


def library_paths(root: Path | None = None) -> dict[str, Path]:
    if root is None:
        root = external_library_root()
    if root is None:
        return {
            "root": DATA_DIR,
            "db": DB_PATH,
            "image": MEDIA_DIR,
            "video": MEDIA_DIR,
            "upload": DATA_DIR / "Upload Image",
            "prompt": DATA_DIR / "prompts",
            "gallery": DATA_DIR / "Gallery",
            "metadata": META_DIR,
            "legacy": DATA_DIR,
        }
    meta = root / EXTERNAL_META_DIR_NAME
    return {
        "root": root,
        "db": meta / "library.json",
        "image": root / "Image",
        "video": root / "Video",
        "upload": root / "Upload Image",
        "prompt": root / "Prompt",
        "gallery": root / "Gallery",
        "metadata": meta / "metadata",
        "legacy": DATA_DIR,
    }


def ensure_library_paths(paths: dict[str, Path]) -> None:
    paths["root"].mkdir(parents=True, exist_ok=True)
    paths["image"].mkdir(parents=True, exist_ok=True)
    paths["video"].mkdir(parents=True, exist_ok=True)
    paths["upload"].mkdir(parents=True, exist_ok=True)
    paths["prompt"].mkdir(parents=True, exist_ok=True)
    paths["gallery"].mkdir(parents=True, exist_ok=True)
    paths["metadata"].mkdir(parents=True, exist_ok=True)
    paths["db"].parent.mkdir(parents=True, exist_ok=True)


def account_store_dir() -> Path:
    root = external_library_root()
    return root / EXTERNAL_META_DIR_NAME if root is not None else DATA_DIR


def accounts_store_path() -> Path:
    return account_store_dir() / "accounts.json"


def account_auth_store_dir() -> Path:
    return account_store_dir() / "account_auth"


def imagine_session_store_path() -> Path:
    return account_store_dir() / "imagine_session.json"


def ensure_account_store_paths() -> None:
    ensure_dirs()
    account_store_dir().mkdir(parents=True, exist_ok=True)
    account_auth_store_dir().mkdir(parents=True, exist_ok=True)


def account_read_paths() -> list[Path]:
    primary = accounts_store_path()
    paths = [primary]
    if primary != ACCOUNTS_PATH:
        paths.append(ACCOUNTS_PATH)
    return paths


def imagine_session_read_paths() -> list[Path]:
    primary = imagine_session_store_path()
    paths = [primary]
    if primary != IMAGINE_SESSION_PATH:
        paths.append(IMAGINE_SESSION_PATH)
    return paths


def is_saved_account_auth_copy(path: Path) -> bool:
    for directory in (account_auth_store_dir(), ACCOUNT_AUTH_DIR):
        try:
            if directory.resolve() in path.parents:
                return True
        except OSError:
            continue
    return False


def guess_ext(mime: str | None, fallback: str) -> str:
    if mime:
        ext = mimetypes.guess_extension(mime.split(";")[0].strip())
        if ext:
            return ".jpg" if ext == ".jpe" else ext
    return fallback


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise StudioError(f"Could not find a free filename near {path}", 500)


def next_image_edit_path(directory: Path, source_stem: str, ext: str) -> Path:
    base = re.sub(r"_edit\d+$", "", safe_file_stem(source_stem, "Image"), flags=re.IGNORECASE)
    for index in range(1, 1000):
        candidate = directory / f"{base}_edit{index:02d}{ext}"
        if not candidate.exists():
            return candidate
    raise StudioError(f"Could not find a free edit filename for {base}", 500)


def data_uri_to_bytes(value: str) -> tuple[bytes, str]:
    if not value.startswith("data:") or ";base64," not in value:
        raise StudioError("Expected a base64 data URI.")
    header, encoded = value.split(",", 1)
    mime = header[5:].split(";", 1)[0] or "application/octet-stream"
    try:
        return base64.b64decode(encoded), mime
    except ValueError as exc:
        raise StudioError("Invalid base64 data URI.") from exc


def system_font_families() -> list[str]:
    global _SYSTEM_FONT_CACHE
    if _SYSTEM_FONT_CACHE is not None:
        return list(_SYSTEM_FONT_CACHE)

    fonts: set[str] = {
        "Arial",
        "Apple SD Gothic Neo",
        "Helvetica",
        "Menlo",
        "Times New Roman",
    }
    if sys.platform == "darwin":
        script = (
            'ObjC.import("AppKit");'
            "JSON.stringify(ObjC.deepUnwrap($.NSFontManager.sharedFontManager.availableFontFamilies))"
        )
        try:
            result = subprocess.run(
                ["/usr/bin/osascript", "-l", "JavaScript", "-e", script],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=8,
            )
            values = json.loads(result.stdout) if result.returncode == 0 else []
            if isinstance(values, list):
                fonts.update(str(value).strip() for value in values if str(value).strip())
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass

    _SYSTEM_FONT_CACHE = sorted(fonts, key=str.casefold)
    return list(_SYSTEM_FONT_CACHE)


def file_to_data_uri(path: Path, default_mime: str) -> str:
    if not path.is_file():
        raise StudioError(f"Local file is missing: {path}", 404)
    mime = mimetypes.guess_type(path.name)[0] or default_mime
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def find_auth_email(raw: Any) -> str | None:
    stack = [raw]
    seen = 0
    while stack and seen < 200:
        item = stack.pop()
        seen += 1
        if isinstance(item, dict):
            for key, value in item.items():
                key_text = str(key).lower()
                if "email" in key_text and isinstance(value, str) and "@" in value:
                    return value
                if isinstance(value, (dict, list)):
                    stack.append(value)
                elif isinstance(value, str) and "@" in value and re.search(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
                    return value
        elif isinstance(item, list):
            stack.extend(value for value in item if isinstance(value, (dict, list, str)))
        elif isinstance(item, str) and "@" in item and re.search(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", item):
            return item
    return None


def load_auth_summary(auth_file: str) -> dict[str, Any]:
    auth_path = Path(auth_file).expanduser()
    summary = {
        "auth_file": str(auth_path),
        "mode": "missing",
        "email": None,
        "expires_at": None,
        "active": False,
    }
    if not auth_path.exists():
        return summary
    try:
        raw = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        summary["mode"] = "unreadable"
        return summary

    fallback_email = find_auth_email(raw)
    values = raw.values() if isinstance(raw, dict) else []
    for value in values:
        if isinstance(value, dict) and isinstance(value.get("key"), str):
            expires = parse_time(value.get("expires_at"))
            summary.update(
                {
                    "mode": value.get("auth_mode") or "oauth",
                    "email": value.get("email") or fallback_email,
                    "expires_at": value.get("expires_at"),
                    "active": expires is None
                    or expires > dt.datetime.now(dt.timezone.utc),
                }
            )
            return summary
    summary["email"] = fallback_email
    return summary


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


def refresh_oauth_token(auth_file: str, force: bool = False) -> str | None:
    auth_path = Path(auth_file).expanduser()
    if not auth_path.exists() or os.environ.get("XAI_API_KEY"):
        return None

    with _AUTH_LOCK:
        try:
            raw = json.loads(auth_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StudioError(f"Could not read auth file: {exc}", 401) from exc

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
                raise StudioError("OAuth token was rejected and cannot be refreshed. Run `grok login` again.", 401)
            return None

        token_endpoint = discover_oidc_token_endpoint(str(issuer))
        form = urllib.parse.urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            token_endpoint,
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30, context=https_context()) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise StudioError(
                f"OAuth refresh failed HTTP {exc.code}. Run `grok login` again.\n{body[:500]}",
                401,
            ) from exc
        except urllib.error.URLError as exc:
            raise StudioError(f"OAuth refresh network error: {format_network_error(exc)}", 502) from exc

        try:
            refreshed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise StudioError(f"OAuth refresh returned non-JSON response: {body[:500]}", 502) from exc

        access_token = refreshed.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise StudioError("OAuth refresh did not return an access token. Run `grok login` again.", 401)

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
            raise StudioError(f"Could not update refreshed OAuth token: {exc}", 500) from exc

        log_event("OAuth token refreshed from auth.json refresh_token")
        return access_token


def discover_oidc_token_endpoint(issuer: str) -> str:
    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=https_context()) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise StudioError(f"OAuth discovery failed: {format_network_error(exc)}", 502) from exc
    try:
        config = json.loads(body)
    except json.JSONDecodeError as exc:
        raise StudioError(f"OAuth discovery returned non-JSON response: {body[:500]}", 502) from exc
    token_endpoint = config.get("token_endpoint")
    if not isinstance(token_endpoint, str):
        raise StudioError("OAuth discovery did not include a token endpoint.", 502)
    return token_endpoint


def load_api_key(auth_file: str) -> str:
    env_key = os.environ.get("XAI_API_KEY")
    if env_key:
        return env_key

    auth_path = Path(auth_file).expanduser()
    if not auth_path.exists():
        raise StudioError(
            f"No OAuth auth file found at {auth_path}. Run the Grok Build CLI login first.",
            401,
        )

    try:
        raw = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StudioError(f"Could not read auth file: {exc}", 401) from exc

    candidates = auth_candidates(raw)

    if not candidates:
        raise StudioError("No OAuth bearer key found in auth.json.", 401)

    refreshed = refresh_oauth_token(auth_file)
    if refreshed:
        return refreshed
    chosen = choose_auth_candidate(candidates)
    return chosen["key"]


def text_from_usage_body(body: str, content_type: str) -> str:
    if "json" in content_type.lower():
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = None
        if parsed is not None:
            body = json.dumps(parsed, ensure_ascii=False)
    body = re.sub(r"<script\b[^>]*>(.*?)</script>", r" \1 ", body, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"<style\b[^>]*>.*?</style>", " ", body, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"<[^>]+>", " ", body)
    body = html.unescape(body)
    return re.sub(r"\s+", " ", body).strip()


def parse_usage_number(value: str) -> float | None:
    cleaned = re.sub(r"[^0-9.]+", "", value)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def unescape_usage_tier_text(value: str) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda match: chr(int(match.group(1), 16)), text)
    text = re.sub(r"\\x([0-9a-fA-F]{2})", lambda match: chr(int(match.group(1), 16)), text)
    return (
        text.replace("\\/", "/")
        .replace('\\"', '"')
        .replace("\\'", "'")
        .replace("\\n", " ")
        .replace("\\r", " ")
        .replace("\\t", " ")
    )


def parse_usage_tier_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", unescape_usage_tier_text(text)).strip().lower()
    compact = re.sub(r"\s+", "", normalized)
    if (
        re.search(r'"issupergrokprouser"\s*:\s*true', normalized)
        or re.search(r'"bestsubscription"\s*:\s*"subscription_tier_super_grok_pro"', normalized)
        or re.search(r'"activesubscriptions"\s*:\s*\[[^\]]{0,4000}"tier"\s*:\s*"subscription_tier_super_grok_pro"', normalized)
    ):
        return "heavy"
    if (
        re.search(r'"issupergrokuser"\s*:\s*true', normalized)
        or re.search(r'"bestsubscription"\s*:\s*"subscription_tier_grok_pro"', normalized)
        or re.search(r'"activesubscriptions"\s*:\s*\[[^\]]{0,4000}"tier"\s*:\s*"subscription_tier_grok_pro"', normalized)
    ):
        return "super"
    heavy_phrases = [
        "free credits with supergrok heavy",
        "supergrok heavy 포함 무료 크레딧",
    ]
    super_phrases = [
        "free credits with supergrok",
        "supergrok 포함 무료 크레딧",
    ]
    if (
        any(phrase in normalized for phrase in heavy_phrases)
        or "freecreditswithsupergrokheavy" in compact
        or "supergrokheavy포함무료크레딧" in compact
    ):
        return "heavy"
    if (
        any(phrase in normalized for phrase in super_phrases)
        or "freecreditswithsupergrok" in compact
        or "supergrok포함무료크레딧" in compact
    ):
        return "super"
    return "free"


def parse_usage_text(text: str) -> dict[str, Any]:
    used_percent: float | None = None
    fraction_label: str | None = None
    reset_label: str | None = None

    percent_patterns = [
        r"(\d{1,3}(?:\.\d+)?)\s*%\s*(?:사용|used)",
        r"(?:사용|used)[^0-9]{0,24}(\d{1,3}(?:\.\d+)?)\s*%",
        r"(?:credit|credits|usage|사용량|크레딧)[^%]{0,120}?(\d{1,3}(?:\.\d+)?)\s*%",
    ]
    for pattern in percent_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = parse_usage_number(match.group(1))
            if value is not None:
                used_percent = max(0.0, min(100.0, value))
                break

    fraction_match = re.search(r"([0-9][0-9,\s]{0,15})\s*/\s*([0-9][0-9,\s]{0,15})", text)
    if fraction_match:
        current = parse_usage_number(fraction_match.group(1))
        total = parse_usage_number(fraction_match.group(2))
        if current is not None and total and total > 0:
            fraction_label = f"{int(current):,} / {int(total):,}"
            if used_percent is None:
                start = max(0, fraction_match.start() - 80)
                end = min(len(text), fraction_match.end() + 80)
                nearby = text[start:end].lower()
                ratio = max(0.0, min(100.0, (current / total) * 100))
                if any(word in nearby for word in ["remaining", "left", "남은", "잔량"]):
                    used_percent = 100.0 - ratio
                else:
                    used_percent = ratio

    reset_patterns = [
        r"(\d{1,2}\s*월\s*\d{1,2}\s*일(?:에)?\s*재설정)",
        r"((?:resets?|reset)[^.!?<>{}]{0,60})",
    ]
    for pattern in reset_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            reset_label = match.group(1).strip(" ·,")
            break

    if used_percent is None:
        return {
            "ok": False,
            "used_percent": None,
            "remaining_percent": None,
            "fraction": fraction_label,
            "reset": reset_label,
            "message": "Usage not found",
        }

    used = int(round(used_percent))
    remaining = max(0, min(100, 100 - used))
    detail_parts = [f"{used}% used"]
    if fraction_label:
        detail_parts.append(fraction_label)
    if reset_label:
        detail_parts.append(reset_label)
    return {
        "ok": True,
        "used_percent": used,
        "remaining_percent": remaining,
        "fraction": fraction_label,
        "reset": reset_label,
        "message": " · ".join(detail_parts),
    }


def read_usage_snapshot(email: str | None = None) -> dict[str, Any] | None:
    if not USAGE_CACHE_PATH.exists():
        return None
    try:
        raw = json.loads(USAGE_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict) or not raw.get("ok"):
        return None
    if email and raw.get("email") and str(raw.get("email")).lower() != email.lower():
        return None
    raw["cached"] = True
    raw["manual"] = bool(raw.get("manual"))
    return raw


def write_usage_snapshot(usage: dict[str, Any]) -> None:
    if not usage.get("ok"):
        return
    ensure_dirs()
    temp = USAGE_CACHE_PATH.with_suffix(".json.tmp")
    payload = dict(usage)
    payload.pop("cached", None)
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(temp, 0o600)
        temp.replace(USAGE_CACHE_PATH)
    except OSError as exc:
        log_event(f"could not save usage snapshot: {exc}")


def usage_from_text(text: str, email: str | None = None, source: str = "manual") -> dict[str, Any]:
    parsed = parse_usage_text(text)
    if not parsed.get("ok"):
        raise StudioError("Could not find usage percent in the provided text.", 400)
    parsed.update(
        {
            "email": email,
            "checked_at": utc_now(),
            "source": source,
            "manual": source == "manual",
        }
    )
    return parsed


def fetch_account_usage(auth_file: str, timeout: float) -> dict[str, Any]:
    auth = load_auth_summary(auth_file)
    result: dict[str, Any] = {
        "ok": False,
        "email": auth.get("email"),
        "checked_at": utc_now(),
        "source": USAGE_URL,
        "used_percent": None,
        "remaining_percent": None,
        "fraction": None,
        "reset": None,
        "message": "Usage unavailable",
    }
    try:
        token = load_api_key(auth_file)
    except StudioError as exc:
        result["message"] = exc.message
        return result

    req = urllib.request.Request(
        USAGE_URL,
        headers={
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            "Authorization": f"Bearer {token}",
            "User-Agent": "Grok Studio Lab local usage checker",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=min(max(5, timeout), 12), context=https_context()) as response:
            body = response.read(3_000_000).decode("utf-8", errors="replace")
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        body = exc.read(2000).decode("utf-8", errors="replace")
        result["message"] = f"Usage request HTTP {exc.code}"
        if body:
            parsed = parse_usage_text(text_from_usage_body(body, exc.headers.get("Content-Type", "")))
            result.update(parsed)
        return result
    except urllib.error.URLError as exc:
        result["message"] = f"Usage network error: {format_network_error(exc)}"
        return result

    parsed = parse_usage_text(text_from_usage_body(body, content_type))
    result.update(parsed)
    if result["ok"]:
        result["source"] = USAGE_URL
        result["manual"] = False
    if not result["ok"] and "login" in body[:5000].lower():
        result["message"] = "Usage page needs a Grok web login"
    return result


def fetch_imagine_usage_tier(session: dict[str, Any], timeout: float) -> dict[str, Any]:
    cookies = valid_imagine_cookies(session)
    result: dict[str, Any] = {
        "tier": "free",
        "ok": False,
        "source": USAGE_URL,
        "message": "Usage tier unavailable",
    }
    if not cookies:
        result["message"] = "Imagine login session is unavailable"
        return result
    req = urllib.request.Request(
        USAGE_URL,
        headers={
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cookie": cookie_header_from_cookies(cookies),
            "Referer": IMAGINE_BASE + "/",
            "User-Agent": imagine_user_agent(),
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=min(max(5, timeout), 12), context=https_context()) as response:
            body = response.read(5_000_000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        result["message"] = f"Usage tier request HTTP {exc.code}"
        return result
    except urllib.error.URLError as exc:
        result["message"] = f"Usage tier network error: {format_network_error(exc)}"
        return result
    if "login" in body[:5000].lower():
        result["message"] = "Usage page needs a Grok web login"
        return result
    tier = parse_usage_tier_text(body)
    result.update(
        {
            "tier": tier,
            "ok": True,
            "message": f"Usage tier detected: {tier}",
        }
    )
    return result


def account_id_for_identity(email: str | None, auth_file: str) -> str:
    key = (email or str(Path(auth_file).expanduser())).strip().lower()
    return uuid.uuid5(uuid.NAMESPACE_URL, f"grok-studio-account:{key}").hex


def normalize_account_tier(value: Any) -> str:
    tier = str(value or "").strip().lower()
    return tier if tier in ACCOUNT_TIER_VALUES else "free"


def empty_accounts_file() -> dict[str, Any]:
    return {"active_id": "", "accounts": [], "imagine_active_id": "", "imagine_accounts": []}


def normalize_accounts_file(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    accounts = raw.get("accounts")
    if not isinstance(accounts, list):
        accounts = []
    imagine_accounts = raw.get("imagine_accounts")
    if not isinstance(imagine_accounts, list):
        imagine_accounts = []
    return {
        "active_id": str(raw.get("active_id") or ""),
        "accounts": [item for item in accounts if isinstance(item, dict)],
        "imagine_active_id": str(raw.get("imagine_active_id") or ""),
        "imagine_accounts": [item for item in imagine_accounts if isinstance(item, dict)],
    }


def read_accounts_path(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return normalize_accounts_file(raw)


def read_accounts_file() -> dict[str, Any]:
    for path in account_read_paths():
        data = read_accounts_path(path)
        if data is not None:
            return data
    return empty_accounts_file()


def write_accounts_file(data: dict[str, Any]) -> None:
    ensure_account_store_paths()
    path = accounts_store_path()
    existing = read_accounts_path(path)
    if existing is None and path != ACCOUNTS_PATH:
        existing = read_accounts_path(ACCOUNTS_PATH)
    payload = normalize_accounts_file({**(existing or empty_accounts_file()), **data}) or empty_accounts_file()
    if not isinstance(payload.get("accounts"), list):
        payload["accounts"] = []
    if not isinstance(payload.get("imagine_accounts"), list):
        payload["imagine_accounts"] = []
    for item in payload["accounts"]:
        if isinstance(item, dict):
            item["tier"] = normalize_account_tier(item.get("tier"))
    for item in payload["imagine_accounts"]:
        if isinstance(item, dict):
            item["tier"] = normalize_account_tier(item.get("tier"))
    payload["active_id"] = str(payload.get("active_id") or "")
    payload["imagine_active_id"] = str(payload.get("imagine_active_id") or "")
    temp = path.with_suffix(".json.tmp")
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(temp, 0o600)
        temp.replace(path)
    except OSError as exc:
        raise StudioError(f"Could not save accounts: {exc}", 500) from exc


def snapshot_auth_file(auth_file: str, label: str | None = None) -> dict[str, Any]:
    source = Path(auth_file).expanduser()
    if not source.exists():
        raise StudioError(f"Auth file not found: {source}", 404)
    summary = load_auth_summary(str(source))
    email = summary.get("email") if isinstance(summary.get("email"), str) else None
    account_id = account_id_for_identity(email, str(source))
    stem = safe_name(email or label or source.stem or account_id[:8], f"account-{account_id[:8]}")
    ensure_account_store_paths()
    target = account_auth_store_dir() / f"{stem}-{account_id[:8]}.json"
    try:
        shutil.copyfile(source, target)
        os.chmod(target, 0o600)
    except OSError as exc:
        raise StudioError(f"Could not save account auth copy: {exc}", 500) from exc
    return account_record(str(target), label, source_auth_file=str(source), account_id=account_id)


def install_account_auth(saved_auth_file: str, cli_auth_file: str) -> str:
    source = Path(saved_auth_file).expanduser()
    target = Path(cli_auth_file).expanduser()
    if not source.exists():
        raise StudioError(f"Saved account auth file not found: {source}", 404)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != target.resolve():
            temp = target.with_suffix(".json.tmp")
            shutil.copyfile(source, temp)
            os.chmod(temp, 0o600)
            temp.replace(target)
        else:
            os.chmod(target, 0o600)
    except OSError as exc:
        raise StudioError(f"Could not update Grok CLI auth file: {exc}", 500) from exc
    return str(target)


def account_record(auth_file: str, label: str | None = None, source_auth_file: str | None = None, account_id: str | None = None) -> dict[str, Any]:
    path = str(Path(auth_file).expanduser())
    summary = load_auth_summary(path)
    email = summary.get("email")
    display = email if isinstance(email, str) and email else (label or Path(path).parent.name or "Grok account")
    return {
        "id": account_id or account_id_for_identity(email if isinstance(email, str) else None, path),
        "label": display,
        "email": email,
        "auth_file": path,
        "source_auth_file": source_auth_file or path,
        "exists": Path(path).exists(),
        "mode": summary.get("mode"),
        "active": bool(summary.get("active")),
        "tier": "free",
    }


def merge_account_records(saved: list[dict[str, Any]], current_auth_file: str) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    def remember(record: dict[str, Any]) -> None:
        account_id = str(record.get("id") or "")
        if not account_id:
            return
        if account_id not in records:
            order.append(account_id)
        records[account_id] = record

    for item in saved:
        auth_file = item.get("auth_file")
        if not isinstance(auth_file, str) or not auth_file:
            continue
        source_auth_file = item.get("source_auth_file") if isinstance(item.get("source_auth_file"), str) else auth_file
        account_id = str(item.get("id") or "") or None
        record = account_record(
            auth_file,
            str(item.get("label") or "") or None,
            source_auth_file=source_auth_file,
            account_id=account_id,
        )
        record["tier"] = normalize_account_tier(item.get("tier"))
        remember(record)
    current = account_record(current_auth_file)
    current_email = current.get("email")
    current_is_usable = bool(current.get("exists") and isinstance(current_email, str) and current_email)
    if current_is_usable and current["id"] not in records:
        remember(current)
    return [records[account_id] for account_id in order if account_id in records]


def saved_account_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "label": record.get("label") or record.get("email") or "Grok account",
        "email": record.get("email"),
        "auth_file": record["auth_file"],
        "source_auth_file": record.get("source_auth_file") or record["auth_file"],
        "tier": normalize_account_tier(record.get("tier")),
        "created_at": utc_now(),
    }


def upsert_saved_account(saved: list[dict[str, Any]], record: dict[str, Any], *, preserve_existing_tier: bool = False) -> list[dict[str, Any]]:
    payload = saved_account_payload(record)
    existing = next((
        item for item in saved
        if isinstance(item, dict)
        and (item.get("id") == payload["id"] or item.get("auth_file") == payload["auth_file"])
    ), None)
    if preserve_existing_tier and isinstance(existing, dict):
        payload["tier"] = normalize_account_tier(existing.get("tier"))
    kept = [
        item for item in saved
        if isinstance(item, dict)
        and item.get("id") != payload["id"]
        and item.get("auth_file") != payload["auth_file"]
    ]
    kept.append(payload)
    return kept


def upsert_saved_account_preserving_order(
    saved: list[dict[str, Any]],
    record: dict[str, Any],
    *,
    preserve_existing_tier: bool = False,
) -> list[dict[str, Any]]:
    payload = saved_account_payload(record)
    reordered: list[dict[str, Any]] = []
    replaced = False
    for item in saved:
        if not isinstance(item, dict):
            continue
        same_record = item.get("id") == payload["id"] or item.get("auth_file") == payload["auth_file"]
        if same_record and not replaced:
            if preserve_existing_tier:
                payload["tier"] = normalize_account_tier(item.get("tier"))
            if isinstance(item.get("created_at"), str) and item.get("created_at"):
                payload["created_at"] = item["created_at"]
            reordered.append(payload)
            replaced = True
        elif not same_record:
            reordered.append(item)
    if not replaced:
        reordered.append(payload)
    return reordered


def reorder_records_by_ids(records: list[dict[str, Any]], ordered_ids: list[str]) -> list[dict[str, Any]]:
    order = [str(value) for value in ordered_ids if str(value)]
    by_id = {str(record.get("id") or ""): record for record in records if isinstance(record, dict)}
    seen: set[str] = set()
    reordered: list[dict[str, Any]] = []
    for account_id in order:
        record = by_id.get(account_id)
        if record is None or account_id in seen:
            continue
        reordered.append(record)
        seen.add(account_id)
    for record in records:
        account_id = str(record.get("id") or "")
        if account_id and account_id not in seen:
            reordered.append(record)
            seen.add(account_id)
    return reordered


GENERIC_ACCOUNT_IDENTITY_KEYS = {
    normalize_identity_text("Imagine"),
    normalize_identity_text("Grok account"),
    normalize_identity_text("Grok"),
    normalize_identity_text("Build"),
}


def account_pair_identity_keys(record: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for key in ("email", "label"):
        normalized = normalize_identity_text(record.get(key))
        if normalized and normalized not in GENERIC_ACCOUNT_IDENTITY_KEYS:
            keys.add(normalized)
    values = record.get("identity_values")
    if isinstance(values, list):
        for value in values:
            normalized = normalize_identity_text(value)
            if normalized and normalized not in GENERIC_ACCOUNT_IDENTITY_KEYS:
                keys.add(normalized)
    return keys


def matching_account_ids(records: list[dict[str, Any]], source: dict[str, Any]) -> list[str]:
    source_keys = account_pair_identity_keys(source)
    if not source_keys:
        return []
    matched: list[str] = []
    for record in records:
        account_id = str(record.get("id") or "")
        if account_id and account_pair_identity_keys(record) & source_keys:
            matched.append(account_id)
    return matched


def move_records_to_front(records: list[dict[str, Any]], account_ids: list[str]) -> list[dict[str, Any]]:
    order = [str(value) for value in account_ids if str(value)]
    if not order:
        return records
    wanted = set(order)
    front_by_id = {str(record.get("id") or ""): record for record in records if isinstance(record, dict)}
    front: list[dict[str, Any]] = []
    seen: set[str] = set()
    for account_id in order:
        record = front_by_id.get(account_id)
        if record is not None and account_id not in seen:
            front.append(record)
            seen.add(account_id)
    return front + [
        record for record in records
        if str(record.get("id") or "") not in wanted
    ]


def prioritize_linked_accounts(data: dict[str, Any], provider: str, account: dict[str, Any]) -> dict[str, Any]:
    saved = [item for item in data.get("accounts", []) if isinstance(item, dict)]
    imagine = stored_imagine_accounts(data)
    account_id = str(account.get("id") or "")
    if provider == "imagine":
        imagine_ids = ([account_id] if account_id else []) + matching_account_ids(imagine, account)
        build_ids = matching_account_ids(saved, account)
        data["imagine_accounts"] = move_records_to_front(imagine, imagine_ids)
        data["accounts"] = move_records_to_front(saved, build_ids)
        return data
    build_ids = ([account_id] if account_id else []) + matching_account_ids(saved, account)
    imagine_ids = matching_account_ids(imagine, account)
    data["accounts"] = move_records_to_front(saved, build_ids)
    data["imagine_accounts"] = move_records_to_front(imagine, imagine_ids)
    return data


def sync_matching_build_account_tier(data: dict[str, Any], source: dict[str, Any], tier: str) -> dict[str, Any]:
    normalized_tier = normalize_account_tier(tier)
    source_keys = account_pair_identity_keys(source)
    if not source_keys:
        return data
    accounts: list[dict[str, Any]] = []
    for item in data.get("accounts", []):
        if not isinstance(item, dict):
            continue
        record = dict(item)
        if account_pair_identity_keys(record) & source_keys:
            record["tier"] = normalized_tier
        accounts.append(record)
    data["accounts"] = accounts
    return data


def hidden_account_ids() -> set[str]:
    raw = read_settings().get("hidden_account_ids")
    if not isinstance(raw, list):
        return set()
    return {str(value) for value in raw if str(value)}


def remember_hidden_account(account_id: str) -> None:
    settings = read_settings()
    hidden = hidden_account_ids()
    hidden.add(account_id)
    settings["hidden_account_ids"] = sorted(hidden)
    write_settings(settings)


def forget_hidden_account(account_id: str) -> None:
    settings = read_settings()
    hidden = hidden_account_ids()
    if account_id not in hidden:
        return
    hidden.remove(account_id)
    if hidden:
        settings["hidden_account_ids"] = sorted(hidden)
    else:
        settings.pop("hidden_account_ids", None)
    write_settings(settings)


def cookie_header_from_cookies(cookies: list[dict[str, Any]]) -> str:
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for cookie in cookies:
        name = str(cookie.get("name") or "")
        value = str(cookie.get("value") or "")
        if not name or not value:
            continue
        pairs.append((name, value))
        seen.add(name)
    sso = next((value for name, value in pairs if name == "sso"), "")
    if sso and "sso-rw" not in seen:
        pairs.append(("sso-rw", sso))
    return "; ".join(f"{name}={value}" for name, value in pairs)


def imagine_user_agent() -> str:
    return (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    )


def imagine_client_hint_headers() -> dict[str, str]:
    return {
        "Sec-Ch-Ua": '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
    }


def imagine_statsig_id() -> str:
    return (
        "ZTpUeXBlRXJyb3I6IENhbm5vdCByZWFkIHByb3BlcnRpZXMgb2YgdW5kZWZpbmVkIChyZWFkaW5nICdjaGls"
        "ZE5vZGVzJyk="
    )


def imagine_cookie_presence(cookies: list[dict[str, Any]]) -> dict[str, Any]:
    names = {str(cookie.get("name") or "") for cookie in cookies if isinstance(cookie, dict)}
    sso_present = "sso" in names
    return {
        "cookie_count": len(cookies),
        "has_sso": sso_present,
        "has_sso_rw": "sso-rw" in names or sso_present,
        "has_cf_clearance": "cf_clearance" in names,
        "names": sorted(name for name in names if name)[:80],
    }


def normalize_imagine_cookies(cookies: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for cookie in cookies:
        if not isinstance(cookie, dict):
            continue
        domain = str(cookie.get("domain") or "")
        name = str(cookie.get("name") or "")
        value = str(cookie.get("value") or "")
        if not name or not value or "grok.com" not in domain:
            continue
        normalized.append(
            {
                "name": name,
                "value": value,
                "domain": domain,
                "path": str(cookie.get("path") or "/"),
                "expires": cookie.get("expires"),
                "secure": bool(cookie.get("secure")),
                "httpOnly": bool(cookie.get("httpOnly")),
                "sameSite": cookie.get("sameSite"),
            }
        )
    return normalized


def fetch_imagine_identity(cookies: list[dict[str, Any]]) -> dict[str, Any]:
    cookie_header = cookie_header_from_cookies(cookies)
    if not cookie_header:
        return {}
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Cookie": cookie_header,
        "Referer": IMAGINE_BASE + "/imagine",
        "User-Agent": imagine_user_agent(),
    }
    paths = [
        "/rest/app-chat/user",
        "/rest/app-chat/users/me",
        "/rest/app-chat/session",
        "/rest/app-chat/bootstrap",
        "/rest/app-chat/settings",
        "/api/auth/session",
    ]
    for path in paths:
        request = urllib.request.Request(IMAGINE_BASE + path, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=4, context=https_context()) as response:
                body = response.read(1_000_000).decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError):
            continue
        try:
            parsed: Any = json.loads(body)
        except json.JSONDecodeError:
            parsed = body
        email = find_auth_email(parsed)
        if not email and isinstance(body, str):
            match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", body)
            email = match.group(0) if match else None
        identity_values: set[str] = set()
        if isinstance(parsed, dict):
            identity_values = imagine_post_identity_values(parsed)
        elif isinstance(parsed, list):
            identity_values = imagine_post_identity_values({"items": parsed})
        if email:
            identity_values.add(normalize_identity_text(email))
        if email:
            return {"email": email, "label": email, "identity_values": sorted(identity_values)}
        if identity_values:
            return {"identity_values": sorted(identity_values)}
    return {}


def imagine_account_id_for_session(session: dict[str, Any]) -> str:
    email = session.get("email") if isinstance(session.get("email"), str) else ""
    cookies = session.get("cookies") if isinstance(session.get("cookies"), list) else []
    key = email.strip().lower() or cookie_header_from_cookies([cookie for cookie in cookies if isinstance(cookie, dict)])
    if not key:
        key = str(session.get("captured_at") or session.get("source_url") or uuid.uuid4().hex)
    return uuid.uuid5(uuid.NAMESPACE_URL, f"grok-studio-imagine-account:{key}").hex


def normalize_imagine_account_session(session: dict[str, Any]) -> dict[str, Any]:
    cookies = session.get("cookies") if isinstance(session.get("cookies"), list) else []
    payload: dict[str, Any] = {
        "version": int(session.get("version") or 1),
        "provider": "imagine",
        "captured_at": str(session.get("captured_at") or utc_now()),
        "source_url": str(session.get("source_url") or ""),
        "cookies": [cookie for cookie in cookies if isinstance(cookie, dict)],
    }
    for key in ("email", "label"):
        value = session.get(key)
        if isinstance(value, str) and value.strip():
            payload[key] = value.strip()
    identity_values = session.get("identity_values")
    if isinstance(identity_values, list):
        cleaned = sorted({
            normalize_identity_text(value)
            for value in identity_values
            if normalize_identity_text(value)
        })
        if cleaned:
            payload["identity_values"] = cleaned
    payload["id"] = str(session.get("id") or imagine_account_id_for_session(payload))
    if "label" not in payload:
        payload["label"] = payload.get("email") or "Imagine"
    payload["tier"] = normalize_account_tier(session.get("tier"))
    return payload


def valid_imagine_cookies(session: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    session = session or read_imagine_session()
    if not session:
        return []
    now = time.time()
    cookies: list[dict[str, Any]] = []
    for cookie in session.get("cookies", []):
        if not isinstance(cookie, dict):
            continue
        expires = cookie.get("expires")
        if isinstance(expires, (int, float)) and expires > 0 and expires < now:
            continue
        name = str(cookie.get("name") or "")
        value = str(cookie.get("value") or "")
        domain = str(cookie.get("domain") or "")
        if name and value and "grok.com" in domain:
            cookies.append(cookie)
    return cookies


def write_active_imagine_session_file(session: dict[str, Any]) -> None:
    ensure_account_store_paths()
    payload = normalize_imagine_account_session(session)
    path = imagine_session_store_path()
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(temp, 0o600)
    temp.replace(path)


def stored_imagine_accounts(data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = data or read_accounts_file()
    accounts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in data.get("imagine_accounts", []):
        if not isinstance(item, dict):
            continue
        normalized = normalize_imagine_account_session(item)
        account_id = str(normalized.get("id") or "")
        if not account_id or account_id in seen:
            continue
        accounts.append(normalized)
        seen.add(account_id)
    return accounts


def saved_imagine_accounts(data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return [account for account in stored_imagine_accounts(data) if valid_imagine_cookies(account)]


def upsert_imagine_account(accounts: list[dict[str, Any]], session: dict[str, Any]) -> list[dict[str, Any]]:
    payload = normalize_imagine_account_session(session)
    existing = next((account for account in accounts if str(account.get("id") or "") == payload["id"]), None)
    if isinstance(existing, dict) and "tier" not in session:
        payload["tier"] = normalize_account_tier(existing.get("tier"))
    if isinstance(existing, dict) and "identity_values" not in payload and isinstance(existing.get("identity_values"), list):
        payload["identity_values"] = existing["identity_values"]
    kept = [account for account in accounts if str(account.get("id") or "") != payload["id"]]
    kept.append(payload)
    return kept


def enrich_imagine_session_identity(session: dict[str, Any]) -> dict[str, Any]:
    payload = normalize_imagine_account_session(session)
    existing_values = payload.get("identity_values") if isinstance(payload.get("identity_values"), list) else []
    if existing_values:
        return payload
    cookies = valid_imagine_cookies(payload)
    if not cookies:
        return payload
    try:
        identity = fetch_imagine_identity(cookies)
    except Exception as exc:
        log_event(f"Imagine identity enrichment skipped: {exc}")
        return payload
    merged = {**payload}
    for key in ("email", "label"):
        value = identity.get(key)
        if isinstance(value, str) and value.strip() and not merged.get(key):
            merged[key] = value.strip()
    values = set()
    for value in existing_values:
        normalized = normalize_identity_text(value)
        if normalized:
            values.add(normalized)
    for value in identity.get("identity_values", []) if isinstance(identity.get("identity_values"), list) else []:
        normalized = normalize_identity_text(value)
        if normalized:
            values.add(normalized)
    for value in (merged.get("id"), merged.get("email"), merged.get("label")):
        normalized = normalize_identity_text(value)
        if normalized:
            values.add(normalized)
    if values:
        merged["identity_values"] = sorted(values)
    return normalize_imagine_account_session(merged)


def persist_imagine_session_identity(session: dict[str, Any]) -> dict[str, Any]:
    enriched = enrich_imagine_session_identity(session)
    if enriched == normalize_imagine_account_session(session):
        return enriched
    write_active_imagine_session_file(enriched)
    data = read_accounts_file()
    data["imagine_accounts"] = upsert_imagine_account(stored_imagine_accounts(data), enriched)
    if str(data.get("imagine_active_id") or "") == str(session.get("id") or "") or not data.get("imagine_active_id"):
        data["imagine_active_id"] = str(enriched.get("id") or "")
    write_accounts_file(data)
    return enriched


def read_imagine_session() -> dict[str, Any] | None:
    for path in imagine_session_read_paths():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = None
        if isinstance(raw, dict) and isinstance(raw.get("cookies"), list):
            return normalize_imagine_account_session(raw)
    data = read_accounts_file()
    active_id = str(data.get("imagine_active_id") or "")
    if not active_id:
        return None
    return next((account for account in saved_imagine_accounts(data) if str(account.get("id") or "") == active_id), None)


def imagine_session_summary(session: dict[str, Any] | None = None) -> dict[str, Any]:
    session = session if isinstance(session, dict) else read_imagine_session()
    cookies = valid_imagine_cookies(session)
    return {
        "id": session.get("id") if isinstance(session, dict) else None,
        "connected": bool(cookies),
        "cookie_count": len(cookies),
        "captured_at": session.get("captured_at") if isinstance(session, dict) else None,
        "source_url": session.get("source_url") if isinstance(session, dict) else "",
        "email": session.get("email") if isinstance(session, dict) else None,
        "label": session.get("label") if isinstance(session, dict) else None,
        "tier": normalize_account_tier(session.get("tier") if isinstance(session, dict) else None),
        "profile_dir": str(IMAGINE_PROFILE_DIR),
        "debug_port": IMAGINE_DEBUG_PORT,
    }


def imagine_accounts_summary(data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = data or read_accounts_file()
    active_id = str(data.get("imagine_active_id") or "")
    summaries: list[dict[str, Any]] = []
    for account in stored_imagine_accounts(data):
        summary = imagine_session_summary(account)
        account_id = str(account.get("id") or summary.get("id") or "")
        summary["id"] = account_id
        summary["selected"] = bool(account_id and account_id == active_id)
        summaries.append(summary)
    return summaries


def write_imagine_session(cookies: list[dict[str, Any]], source_url: str = "", timeout: float = 30.0) -> dict[str, Any]:
    if not cookies:
        raise StudioError("No grok.com cookies were captured. Finish the Imagine login, then capture again.", 401)
    payload = normalize_imagine_account_session(
        {
            "version": 1,
            "provider": "imagine",
            "captured_at": utc_now(),
            "source_url": source_url,
            "cookies": cookies,
            **fetch_imagine_identity(cookies),
        }
    )
    tier_result = fetch_imagine_usage_tier(payload, timeout)
    payload["tier"] = normalize_account_tier(tier_result.get("tier"))
    log_event(
        "Imagine usage tier "
        f"{payload['tier']} for {payload.get('email') or payload.get('label') or payload.get('id')}: "
        f"{tier_result.get('message') or ''}"
    )
    write_active_imagine_session_file(payload)
    data = read_accounts_file()
    data["imagine_accounts"] = upsert_imagine_account(stored_imagine_accounts(data), payload)
    data["imagine_active_id"] = payload["id"]
    data = sync_matching_build_account_tier(data, payload, payload["tier"])
    data = prioritize_linked_accounts(data, "imagine", payload)
    write_accounts_file(data)
    return imagine_session_summary(payload)


def imagine_account_status(account: dict[str, Any]) -> dict[str, Any]:
    account_id = str(account.get("id") or "")
    cookies = valid_imagine_cookies(account)
    if not cookies:
        return {"id": account_id, "status": "expired"}
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Cookie": cookie_header_from_cookies(cookies),
        "Referer": IMAGINE_BASE + "/imagine",
        "User-Agent": imagine_user_agent(),
    }
    for path in ("/rest/app-chat/user", "/rest/app-chat/users/me", "/rest/app-chat/session", "/api/auth/session"):
        request = urllib.request.Request(IMAGINE_BASE + path, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=5, context=https_context()) as response:
                body = response.read(1_000_000).decode("utf-8", errors="replace")
                status = int(getattr(response, "status", 200) or 200)
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                return {"id": account_id, "status": "expired"}
            continue
        except (urllib.error.URLError, OSError, TimeoutError):
            continue
        if status in {401, 403}:
            return {"id": account_id, "status": "expired"}
        if "login" in body[:5000].lower() or "sign in" in body[:5000].lower():
            continue
        return {"id": account_id, "status": "ok"}
    return {"id": account_id, "status": "unknown"}


def _read_exact(stream: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = stream.recv(remaining)
        if not chunk:
            raise StudioError("WebSocket connection closed unexpectedly.", 502)
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


class RawWebSocket:
    def __init__(self, url: str, headers: dict[str, str] | None = None, timeout: float = 30) -> None:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"ws", "wss"}:
            raise StudioError(f"Unsupported WebSocket URL: {url}", 500)
        self.url = url
        self.host = parsed.hostname or ""
        self.port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        self.path = parsed.path or "/"
        if parsed.query:
            self.path += "?" + parsed.query
        self.timeout = timeout
        self.socket = socket.create_connection((self.host, self.port), timeout=timeout)
        if parsed.scheme == "wss":
            self.socket = https_context().wrap_socket(self.socket, server_hostname=self.host)
        self.socket.settimeout(timeout)
        self._handshake(headers or {})

    def _handshake(self, headers: dict[str, str]) -> None:
        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        request_headers = {
            "Host": self.host if self.port in {80, 443} else f"{self.host}:{self.port}",
            "Upgrade": "websocket",
            "Connection": "Upgrade",
            "Sec-WebSocket-Key": key,
            "Sec-WebSocket-Version": "13",
            **headers,
        }
        lines = [f"GET {self.path} HTTP/1.1"]
        lines.extend(f"{name}: {value}" for name, value in request_headers.items() if value)
        self.socket.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("utf-8"))
        response = b""
        while b"\r\n\r\n" not in response:
            response += self.socket.recv(4096)
            if len(response) > 65536:
                break
        status_line = response.split(b"\r\n", 1)[0].decode("iso-8859-1", errors="replace")
        if " 101 " not in status_line:
            raise StudioError(f"WebSocket handshake failed: {status_line}", 502)

    def send_json(self, payload: dict[str, Any]) -> None:
        self.send_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

    def send_text(self, text: str) -> None:
        self._send_frame(text.encode("utf-8"), opcode=1)

    def _send_frame(self, payload: bytes, opcode: int) -> None:
        head = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            head.append(0x80 | length)
        elif length < 65536:
            head.extend([0x80 | 126, (length >> 8) & 0xFF, length & 0xFF])
        else:
            head.extend([0x80 | 127])
            head.extend(length.to_bytes(8, "big"))
        mask = secrets.token_bytes(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.socket.sendall(bytes(head) + mask + masked)

    def recv_text(self) -> str | None:
        fragments: list[bytes] = []
        while True:
            first, second = _read_exact(self.socket, 2)
            fin = bool(first & 0x80)
            opcode = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = int.from_bytes(_read_exact(self.socket, 2), "big")
            elif length == 127:
                length = int.from_bytes(_read_exact(self.socket, 8), "big")
            mask = _read_exact(self.socket, 4) if masked else b""
            payload = _read_exact(self.socket, length) if length else b""
            if masked:
                payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
            if opcode == 8:
                return None
            if opcode == 9:
                self._send_frame(payload, opcode=10)
                continue
            if opcode in {1, 0}:
                fragments.append(payload)
                if fin:
                    return b"".join(fragments).decode("utf-8", errors="replace")

    def close(self) -> None:
        try:
            self._send_frame(b"", opcode=8)
        except Exception:
            pass
        try:
            self.socket.close()
        except Exception:
            pass


def cdp_targets(port: int) -> list[dict[str, Any]]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise StudioError("Chrome login window is not reachable yet. Open Imagine Login first.", 503) from exc
    return raw if isinstance(raw, list) else []


def cdp_call(
    ws_url: str,
    method: str,
    params: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    ws = RawWebSocket(ws_url, timeout=max(1.0, min(timeout, 60.0)))
    try:
        sequence = 1
        ws.send_json({"id": sequence, "method": method, "params": params or {}})
        deadline = time.monotonic() + max(1.0, timeout)
        while time.monotonic() < deadline:
            message = ws.recv_text()
            if message is None:
                break
            try:
                parsed = json.loads(message)
            except json.JSONDecodeError:
                continue
            if parsed.get("id") == sequence:
                if parsed.get("error"):
                    raise StudioError(f"Chrome DevTools error: {parsed['error']}", 502)
                result = parsed.get("result")
                return result if isinstance(result, dict) else {}
    finally:
        ws.close()
    raise StudioError("Chrome DevTools did not return a response.", 502)


def cdp_evaluate(expression: str, timeout: float = 30, target: dict[str, Any] | None = None) -> Any:
    if target is None:
        target = find_imagine_cdp_target(IMAGINE_DEBUG_PORT)
    ws_url = str(target.get("webSocketDebuggerUrl") or "")
    ws = RawWebSocket(ws_url, timeout=min(max(10, timeout), 60))
    try:
        sequence = 1
        ws.send_json({"id": sequence, "method": "Runtime.enable"})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            message = ws.recv_text()
            if message is None:
                break
            try:
                parsed = json.loads(message)
            except json.JSONDecodeError:
                continue
            if parsed.get("id") == sequence:
                break
        sequence += 1
        ws.send_json(
            {
                "id": sequence,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": expression,
                    "awaitPromise": True,
                    "returnByValue": True,
                    "timeout": int(timeout * 1000),
                },
            }
        )
        while time.monotonic() < deadline:
            message = ws.recv_text()
            if message is None:
                break
            try:
                parsed = json.loads(message)
            except json.JSONDecodeError:
                continue
            if parsed.get("id") != sequence:
                continue
            if parsed.get("error"):
                raise StudioError(f"Chrome DevTools error: {parsed['error']}", 502)
            result = parsed.get("result") if isinstance(parsed.get("result"), dict) else {}
            if result.get("exceptionDetails"):
                raise StudioError(f"Chrome page script error: {result['exceptionDetails']}", 502)
            remote = result.get("result") if isinstance(result.get("result"), dict) else {}
            return remote.get("value")
    finally:
        ws.close()
    raise StudioError("Chrome DevTools did not return a page script result.", 502)


def cdp_click_point(x: float, y: float, timeout: float = 8) -> None:
    target = find_imagine_cdp_target(IMAGINE_DEBUG_PORT)
    ws_url = str(target.get("webSocketDebuggerUrl") or "")
    ws = RawWebSocket(ws_url, timeout=min(max(5, timeout), 20))
    try:
        sequence = 1
        for event_type, button, buttons in (
            ("mouseMoved", "none", 0),
            ("mousePressed", "left", 1),
            ("mouseReleased", "left", 0),
        ):
            ws.send_json(
                {
                    "id": sequence,
                    "method": "Input.dispatchMouseEvent",
                    "params": {
                        "type": event_type,
                        "x": x,
                        "y": y,
                        "button": button,
                        "buttons": buttons,
                        "clickCount": 1,
                    },
                }
            )
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                message = ws.recv_text()
                if message is None:
                    break
                try:
                    parsed = json.loads(message)
                except json.JSONDecodeError:
                    continue
                if parsed.get("id") != sequence:
                    continue
                if parsed.get("error"):
                    raise StudioError(f"Chrome DevTools click error: {parsed['error']}", 502)
                break
            sequence += 1
            time.sleep(0.05)
    finally:
        ws.close()


def cdp_hide_target_window(target: dict[str, Any]) -> None:
    ws_url = str(target.get("webSocketDebuggerUrl") or "")
    target_id = str(target.get("id") or "")
    if not ws_url or not target_id:
        return
    try:
        result = cdp_call(ws_url, "Browser.getWindowForTarget", {"targetId": target_id}, timeout=4)
        window_id = result.get("windowId")
        if not isinstance(window_id, int):
            return
        cdp_call(ws_url, "Browser.setWindowBounds", {"windowId": window_id, "bounds": {"windowState": "normal"}}, timeout=4)
        cdp_call(
            ws_url,
            "Browser.setWindowBounds",
            {
                "windowId": window_id,
                "bounds": {"left": -20000, "top": 80, "width": 520, "height": 320},
            },
            timeout=4,
        )
    except StudioError:
        pass


def find_imagine_cdp_target(port: int) -> dict[str, Any]:
    targets = cdp_targets(port)
    candidates = [
        target for target in targets
        if isinstance(target, dict)
        and isinstance(target.get("webSocketDebuggerUrl"), str)
        and "grok.com" in str(target.get("url") or "")
    ]
    candidates.sort(key=lambda target: (0 if "/imagine" in str(target.get("url") or "") else 1, str(target.get("url") or "")))
    if not candidates:
        raise StudioError("Could not find a Chrome tab to capture. Open Imagine Login first.", 404)
    return candidates[0]


def find_imagine_files_cdp_target(port: int) -> dict[str, Any]:
    targets = cdp_targets(port)
    candidates = [
        target for target in targets
        if isinstance(target, dict)
        and isinstance(target.get("webSocketDebuggerUrl"), str)
        and "grok.com" in str(target.get("url") or "")
    ]

    def rank(target: dict[str, Any]) -> tuple[int, str]:
        url = str(target.get("url") or "")
        if re.search(r"https://(?:www\.)?grok\.com/files(?:[?#/]|$)", url, re.IGNORECASE):
            return (0, url)
        if re.search(r"https://(?:www\.)?grok\.com/imagine/saved(?:[?#/]|$)", url, re.IGNORECASE):
            return (1, url)
        return (2, url)

    candidates.sort(key=rank)
    if not candidates:
        raise StudioError("Could not find a Chrome tab to capture. Open Imagine Login first.", 404)
    return candidates[0]


def wait_for_imagine_files_cdp_target(port: int, timeout: float = 8.0) -> dict[str, Any]:
    deadline = time.monotonic() + max(1.0, timeout)
    last_target: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        try:
            target = find_imagine_files_cdp_target(port)
        except StudioError:
            time.sleep(0.25)
            continue
        last_target = target
        url = str(target.get("url") or "")
        if re.search(r"https://(?:www\.)?grok\.com/files(?:[?#/]|$)", url, re.IGNORECASE):
            return target
        time.sleep(0.25)
    if last_target is not None:
        return last_target
    return find_imagine_files_cdp_target(port)


def centered_window_position_in_anchor(width: int, height: int, anchor: Any) -> tuple[int, int]:
    if isinstance(anchor, dict):
        try:
            left = int(float(anchor.get("left")))
            top = int(float(anchor.get("top")))
            outer_width = int(float(anchor.get("width")))
            outer_height = int(float(anchor.get("height")))
            if outer_width >= 240 and outer_height >= 240:
                return max(0, left + round((outer_width - width) / 2)), max(0, top + round((outer_height - height) / 2))
        except (TypeError, ValueError):
            pass
    return 120, 80


def close_imagine_chrome_browser(port: int) -> dict[str, Any]:
    def terminate_profile_processes() -> int:
        profile = str(IMAGINE_PROFILE_DIR)
        patterns = (f"--remote-debugging-port={port}", f"--user-data-dir={profile}")
        try:
            result = subprocess.run(
                ["ps", "-axo", "pid=,command="],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return 0
        pids: list[int] = []
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            first, _, command = stripped.partition(" ")
            try:
                pid = int(first)
            except ValueError:
                continue
            if pid == os.getpid():
                continue
            if "Google Chrome" not in command and "Chromium" not in command:
                continue
            if any(pattern in command for pattern in patterns):
                pids.append(pid)
        original_count = len(pids)
        for pid in pids:
            try:
                os.kill(pid, 15)
            except OSError:
                pass
        deadline = time.monotonic() + 2.0
        while pids and time.monotonic() < deadline:
            alive: list[int] = []
            for pid in pids:
                try:
                    os.kill(pid, 0)
                    alive.append(pid)
                except OSError:
                    pass
            if not alive:
                break
            pids = alive
            time.sleep(0.1)
        killed = 0
        for pid in pids:
            try:
                os.kill(pid, 9)
                killed += 1
            except OSError:
                pass
        return original_count or killed

    def port_is_alive() -> bool:
        try:
            cdp_targets(port)
            return True
        except StudioError:
            return False

    try:
        targets = cdp_targets(port)
    except StudioError as exc:
        log_event(f"Imagine Chrome close skipped: {exc.message}")
        terminated = terminate_profile_processes()
        return {"browser_closed": bool(terminated), "tabs_closed": 0, "processes_terminated": terminated}
    target = next((item for item in targets if isinstance(item, dict) and isinstance(item.get("webSocketDebuggerUrl"), str)), None)
    if not target:
        terminated = terminate_profile_processes()
        return {"browser_closed": bool(terminated), "tabs_closed": 0, "processes_terminated": terminated}
    try:
        ws = RawWebSocket(str(target.get("webSocketDebuggerUrl") or ""), timeout=2)
        try:
            ws.send_json({"id": 1, "method": "Browser.close"})
        finally:
            ws.close()
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if not port_is_alive():
                return {"browser_closed": True, "tabs_closed": 0, "processes_terminated": 0}
            time.sleep(0.2)
        terminated = terminate_profile_processes()
        return {"browser_closed": True, "tabs_closed": 0, "processes_terminated": terminated}
    except Exception as exc:
        log_event(f"Imagine Chrome browser close skipped: {exc}")
        terminated = terminate_profile_processes()
        return {"browser_closed": bool(terminated), "tabs_closed": 0, "processes_terminated": terminated}


class XaiClient:
    def __init__(self, auth_file: str, base_url: str, timeout: float) -> None:
        self.auth_file = auth_file
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._request(method, path, payload, retried=False)

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None, retried: bool = False
    ) -> dict[str, Any]:
        data = None
        headers = {"Authorization": f"Bearer {load_api_key(self.auth_file)}"}
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
            if exc.code in {401, 403} and not retried and not os.environ.get("XAI_API_KEY"):
                log_event(f"OAuth token rejected with HTTP {exc.code}; refreshing and retrying once")
                refresh_oauth_token(self.auth_file, force=True)
                return self._request(method, path, payload, retried=True)
            try:
                parsed = json.loads(body)
                body = json.dumps(parsed, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                pass
            raise StudioError(f"xAI API error HTTP {exc.code}:\n{body}", exc.code) from exc
        except urllib.error.URLError as exc:
            raise StudioError(f"Network error: {format_network_error(exc)}", 502) from exc

        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise StudioError(f"API returned non-JSON response: {body[:500]}", 502) from exc

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", path, payload)

    def get(self, path: str) -> dict[str, Any]:
        return self.request("GET", path)


class Library:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        ensure_dirs()
        self.reload_paths()
        if not self.db_path.exists():
            self._write(self.empty_data())

    def empty_data(self) -> dict[str, Any]:
        return {
            "version": 3,
            "categories": ["Inbox", "Image", "Video", "Prompt", "Finals"],
            "gallery_folders": [],
            "gallery_sort": "",
            "items": [],
        }

    def reload_paths(self) -> None:
        paths = library_paths()
        ensure_library_paths(paths)
        self.root = paths["root"]
        self.db_path = paths["db"]
        self.image_dir = paths["image"]
        self.video_dir = paths["video"]
        self.upload_dir = paths["upload"]
        self.prompt_dir = paths["prompt"]
        self.gallery_dir = paths["gallery"]
        self.metadata_dir = paths["metadata"]
        self.using_external_root = self.root.resolve() != DATA_DIR.resolve()

    def trash_manifest_path(self) -> Path:
        return self.metadata_dir / "trash_manifest.json"

    def set_root(self, root_text: str) -> dict[str, Any]:
        root_text = str(root_text or "").strip()
        if not root_text:
            settings = read_settings()
            settings.pop("library_root", None)
            write_settings(settings)
        else:
            root = Path(root_text).expanduser().resolve()
            paths = library_paths(root)
            ensure_library_paths(paths)
            settings = read_settings()
            settings["library_root"] = str(root)
            write_settings(settings)
        with self.lock:
            self.reload_paths()
            if not self.db_path.exists():
                self._write(self.empty_data())
        return self.info()

    def info(self) -> dict[str, Any]:
        self.reload_paths()
        return {
            "root": str(self.root),
            "image_dir": str(self.image_dir),
            "video_dir": str(self.video_dir),
            "upload_dir": str(self.upload_dir),
            "prompt_dir": str(self.prompt_dir),
            "gallery_dir": str(self.gallery_dir),
            "external": self.using_external_root,
            "default_folder_path": DEFAULT_LIBRARY_FOLDER_PATH,
        }

    def _read(self) -> dict[str, Any]:
        with self.lock:
            self.reload_paths()
            try:
                data = json.loads(self.db_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = self.empty_data()
            return data if isinstance(data, dict) else self.empty_data()

    def _write(self, data: dict[str, Any]) -> None:
        with self.lock:
            self.reload_paths()
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.db_path.with_suffix(".tmp")
            temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(self.db_path)

    def _read_trash_manifest(self) -> dict[str, Any]:
        with self.lock:
            self.reload_paths()
            path = self.trash_manifest_path()
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raw = {}
            entries = raw.get("items") if isinstance(raw, dict) else []
            folders = raw.get("folders") if isinstance(raw, dict) else []
            return {
                "version": 1,
                "items": [entry for entry in entries if isinstance(entry, dict)] if isinstance(entries, list) else [],
                "folders": [entry for entry in folders if isinstance(entry, dict)] if isinstance(folders, list) else [],
            }

    def _write_trash_manifest(self, manifest: dict[str, Any]) -> None:
        with self.lock:
            self.reload_paths()
            path = self.trash_manifest_path()
            entries = manifest.get("items")
            folders = manifest.get("folders")
            entries = entries if isinstance(entries, list) else []
            folders = folders if isinstance(folders, list) else []
            if not entries and not folders:
                try:
                    if path.exists():
                        path.unlink()
                except OSError as exc:
                    log_event(f"could not remove empty trash manifest: {exc}")
                return
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(".tmp")
            temp.write_text(
                json.dumps({"version": 1, "items": entries, "folders": folders}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp.replace(path)

    def media_url(self, path: Path) -> str:
        path = path.resolve()
        roots = [MEDIA_DIR.resolve(), self.root.resolve()]
        for root in roots:
            try:
                rel = path.relative_to(root)
                return "/media/" + urllib.parse.quote(str(rel).replace(os.sep, "/"))
            except ValueError:
                continue
        return media_url(path)

    def state(self) -> dict[str, Any]:
        data = self._read()
        changed = self.restore_trashed_items(data)
        if self.dedupe_imported_items(data):
            changed = True
        if self.sync_disk_files(data):
            changed = True
        if self.repair_imagine_import_relationships(data):
            changed = True
        if changed:
            self._write(data)
        items = sorted(data.get("items", []), key=lambda item: item.get("created_at", ""), reverse=True)
        return {
            "categories": data.get("categories", []),
            "gallery_folders": data.get("gallery_folders", []),
            "gallery_sort": str(data.get("gallery_sort") or ""),
            "items": items,
            "library": self.info(),
        }

    def item_file_identity(self, item: dict[str, Any]) -> str | None:
        file_path = item.get("file")
        if isinstance(file_path, str) and file_path:
            try:
                return "file:" + str(Path(file_path).expanduser().resolve())
            except OSError:
                return "file:" + file_path
        local_url = item.get("local_url")
        if isinstance(local_url, str) and local_url:
            return "url:" + urllib.parse.unquote(local_url)
        return None

    def is_imported_item(self, item: dict[str, Any]) -> bool:
        metadata = item.get("metadata")
        return item.get("mode") == "import" or (
            isinstance(metadata, dict) and metadata.get("imported") is True
        )

    def is_imagine_remote_import_item(self, item: dict[str, Any]) -> bool:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        imagine = metadata.get("imagine") if isinstance(metadata.get("imagine"), dict) else {}
        return bool(
            item.get("mode") == "imagine-import"
            or item.get("source") == "imagine-import"
            or metadata.get("source") == "imagine-import"
            or metadata.get("import_source") == "imagine-remote"
            or imagine.get("imported") is True
        )

    def imagine_remote_post_identity(self, item: dict[str, Any]) -> str:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        imagine = metadata.get("imagine") if isinstance(metadata.get("imagine"), dict) else {}
        values = [
            metadata.get("remote_item_id"),
            imagine.get("remote_item_id"),
            metadata.get("imagine_post_id"),
            metadata.get("imagine_video_post_id"),
            imagine.get("post_id"),
            item.get("request_id"),
        ]
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            for prefix in ("imagine-remote:image:", "imagine-remote:video:"):
                if text.startswith(prefix):
                    text = text[len(prefix):]
                    break
            if text:
                return text
        return ""

    def imagine_import_source_image_for_video(
        self,
        video: dict[str, Any],
        images: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not images:
            return None
        metadata = video.get("metadata") if isinstance(video.get("metadata"), dict) else {}
        imagine = metadata.get("imagine") if isinstance(metadata.get("imagine"), dict) else {}
        parent_remote_id = str(
            imagine.get("parent_post_id")
            or metadata.get("remote_parent_id")
            or metadata.get("parent_id")
            or "",
        ).strip()
        if parent_remote_id:
            for prefix in ("imagine-remote:image:", "imagine-remote:video:"):
                if parent_remote_id.startswith(prefix):
                    parent_remote_id = parent_remote_id[len(prefix):]
                    break
            for image in images:
                if self.imagine_remote_post_identity(image) == parent_remote_id:
                    return image
                if str(image.get("id") or "") == parent_remote_id:
                    return image

        roots = []
        for image in images:
            image_metadata = image.get("metadata") if isinstance(image.get("metadata"), dict) else {}
            if not str(image_metadata.get("parent_id") or "").strip():
                roots.append(image)
        if roots:
            return sorted(roots, key=lambda item: str(item.get("created_at") or ""))[0]

        video_created = str(video.get("created_at") or "")
        previous_images = [
            image for image in images
            if str(image.get("created_at") or "") <= video_created
        ]
        if previous_images:
            return sorted(previous_images, key=lambda item: str(item.get("created_at") or ""), reverse=True)[0]
        return sorted(images, key=lambda item: str(item.get("created_at") or ""))[0]

    def repair_imagine_import_relationships(self, data: dict[str, Any]) -> int:
        items = [item for item in data.get("items", []) if isinstance(item, dict)]
        images_by_group: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            if item.get("type") != "image" or not self.is_imagine_remote_import_item(item):
                continue
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            group_id = str(metadata.get("group_id") or item.get("id") or "").strip()
            if not group_id or not item.get("local_url"):
                continue
            images_by_group.setdefault(group_id, []).append(item)

        updated = 0
        for item in items:
            if item.get("type") != "video" or not self.is_imagine_remote_import_item(item):
                continue
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            item["metadata"] = metadata
            group_id = str(metadata.get("group_id") or item.get("id") or "").strip()
            source_image = self.imagine_import_source_image_for_video(item, images_by_group.get(group_id, []))
            if not source_image or not source_image.get("local_url"):
                continue
            changed = False
            expected_start_image = {"url": str(source_image["local_url"])}
            if metadata.get("start_image") != expected_start_image:
                metadata["start_image"] = expected_start_image
                changed = True
            source_image_id = str(source_image.get("id") or "")
            previous_parent_id = str(metadata.get("parent_id") or "")
            if source_image_id and previous_parent_id != source_image_id:
                if previous_parent_id:
                    metadata.setdefault("remote_parent_id", previous_parent_id)
                metadata["parent_id"] = source_image_id
                changed = True
            imagine = metadata.get("imagine") if isinstance(metadata.get("imagine"), dict) else {}
            metadata["imagine"] = imagine
            remote_parent_id = str(metadata.get("remote_parent_id") or previous_parent_id or "").strip()
            if remote_parent_id and not str(imagine.get("parent_post_id") or "").strip():
                imagine["parent_post_id"] = remote_parent_id
                changed = True
            if changed:
                item["updated_at"] = utc_now()
                updated += 1
        if updated:
            log_event(f"repaired {updated} Imagine imported video relationship(s)")
        return updated

    def repair_imagine_import_relationships_in_db(self) -> int:
        data = self._read()
        updated = self.repair_imagine_import_relationships(data)
        if updated:
            self._write(data)
        return updated

    def dedupe_imported_items(self, data: dict[str, Any]) -> int:
        items = data.setdefault("items", [])
        kept: list[dict[str, Any]] = []
        identity_indexes: dict[str, int] = {}
        removed = 0
        for item in items:
            if not isinstance(item, dict):
                removed += 1
                continue
            identity = self.item_file_identity(item)
            existing_index = identity_indexes.get(identity) if identity else None
            if existing_index is None:
                if identity:
                    identity_indexes[identity] = len(kept)
                kept.append(item)
                continue
            existing = kept[existing_index]
            existing_imported = self.is_imported_item(existing)
            current_imported = self.is_imported_item(item)
            if not existing_imported and not current_imported:
                kept.append(item)
                continue
            if existing_imported and not current_imported:
                kept[existing_index] = item
            removed += 1
        if removed:
            data["items"] = kept
            log_event(f"removed {removed} duplicate auto-imported library item(s)")
        return removed

    def remember_deleted_items(self, candidates: list[dict[str, Any]]) -> None:
        entries: list[dict[str, Any]] = []
        for item in candidates:
            if item.get("type") not in {"image", "video"}:
                continue
            file_path = item.get("file")
            if not isinstance(file_path, str) or not file_path:
                continue
            item_copy = json.loads(json.dumps(item, ensure_ascii=False))
            entry: dict[str, Any] = {
                "id": str(item.get("id") or ""),
                "identity": self.item_file_identity(item),
                "file": file_path,
                "metadata_file": item.get("metadata_file") if isinstance(item.get("metadata_file"), str) else "",
                "deleted_at": utc_now(),
                "item": item_copy,
            }
            metadata_path = item.get("metadata_file")
            if isinstance(metadata_path, str) and metadata_path:
                try:
                    path = Path(metadata_path).expanduser()
                    if path.is_file():
                        entry["metadata_text"] = path.read_text(encoding="utf-8")
                except OSError as exc:
                    log_event(f"could not snapshot metadata before Trash move: {exc}")
            entries.append(entry)
        if not entries:
            return

        manifest = self._read_trash_manifest()
        previous = manifest.get("items", [])
        entry_ids = {entry.get("id") for entry in entries if entry.get("id")}
        entry_identities = {entry.get("identity") for entry in entries if entry.get("identity")}
        manifest["items"] = [
            entry
            for entry in previous
            if entry.get("id") not in entry_ids and entry.get("identity") not in entry_identities
        ]
        manifest["items"].extend(entries)
        manifest["items"] = manifest["items"][-1000:]
        self._write_trash_manifest(manifest)

    def remember_deleted_gallery_folders(self, candidates: list[dict[str, Any]], data: dict[str, Any]) -> None:
        entries: list[dict[str, Any]] = []
        for folder in candidates:
            folder_id = str(folder.get("id") or "")
            if not folder_id:
                continue
            try:
                folder_path = self.gallery_folder_path(folder_id, data)
            except StudioError:
                continue
            entries.append(
                {
                    "id": folder_id,
                    "path": str(folder_path),
                    "deleted_at": utc_now(),
                    "folder": json.loads(json.dumps(folder, ensure_ascii=False)),
                }
            )
        if not entries:
            return

        manifest = self._read_trash_manifest()
        previous = manifest.get("folders", [])
        entry_ids = {entry.get("id") for entry in entries if entry.get("id")}
        manifest["folders"] = [
            entry
            for entry in previous
            if entry.get("id") not in entry_ids
        ]
        manifest["folders"].extend(entries)
        manifest["folders"] = manifest["folders"][-1000:]
        self._write_trash_manifest(manifest)

    def restore_trashed_items(self, data: dict[str, Any]) -> int:
        manifest = self._read_trash_manifest()
        entries = manifest.get("items", [])
        folder_entries = manifest.get("folders", [])
        if not entries and not folder_entries:
            return 0

        restored_folders = self.restore_trashed_gallery_folders(data, folder_entries)
        existing_folder_ids = {
            str(folder.get("id") or "")
            for folder in data.get("gallery_folders", [])
            if isinstance(folder, dict) and folder.get("id")
        }
        items = data.setdefault("items", [])
        categories = data.setdefault("categories", [])
        existing_ids = {
            str(item.get("id") or "")
            for item in items
            if isinstance(item, dict) and item.get("id")
        }
        existing_by_identity: dict[str, dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            identity = self.item_file_identity(item)
            if identity and identity not in existing_by_identity:
                existing_by_identity[identity] = item

        kept_entries: list[dict[str, Any]] = []
        restored = 0
        manifest_changed = False
        for entry in entries:
            item = entry.get("item")
            if not isinstance(item, dict):
                manifest_changed = True
                continue
            item_id = str(item.get("id") or entry.get("id") or "")
            if item_id and item_id in existing_ids:
                manifest_changed = True
                continue
            if item.get("type") not in {"image", "video"}:
                manifest_changed = True
                continue

            metadata = item.get("metadata")
            gallery_folder_id = str(metadata.get("gallery_folder_id") or "") if isinstance(metadata, dict) else ""
            if gallery_folder_id and gallery_folder_id not in existing_folder_ids:
                kept_entries.append(entry)
                continue

            file_path = item.get("file") if isinstance(item.get("file"), str) else entry.get("file")
            if not isinstance(file_path, str) or not file_path:
                manifest_changed = True
                continue
            media_path = Path(file_path).expanduser()
            if not media_path.is_file():
                kept_entries.append(entry)
                continue

            if item.get("local_url"):
                try:
                    item["local_url"] = self.media_url(media_path)
                except StudioError:
                    pass
            identity = self.item_file_identity(item)
            existing = existing_by_identity.get(identity) if identity else None
            if existing and not self.is_imported_item(existing):
                manifest_changed = True
                continue

            self.restore_trashed_metadata_file(item, entry)
            category = item.get("category") or "Inbox"
            if category not in categories:
                categories.append(category)
            items.append(item)
            if item_id:
                existing_ids.add(item_id)
            if identity:
                existing_by_identity[identity] = item
            restored += 1
            manifest_changed = True

        if manifest_changed:
            kept_folder_entries = [
                entry
                for entry in folder_entries
                if isinstance(entry, dict)
                and str(entry.get("id") or "") not in existing_folder_ids
            ]
            self._write_trash_manifest({"version": 1, "items": kept_entries, "folders": kept_folder_entries})
        elif restored_folders:
            kept_folder_entries = [
                entry
                for entry in folder_entries
                if isinstance(entry, dict)
                and str(entry.get("id") or "") not in existing_folder_ids
            ]
            self._write_trash_manifest({"version": 1, "items": entries, "folders": kept_folder_entries})
        if restored:
            log_event(f"restored {restored} library item(s) returned from Trash")
        if restored_folders:
            log_event(f"restored {restored_folders} Gallery folder(s) returned from Trash")
        return restored + restored_folders

    def restore_trashed_gallery_folders(self, data: dict[str, Any], entries: list[Any]) -> int:
        if not entries:
            return 0
        folders = data.setdefault("gallery_folders", [])
        existing_ids = {
            str(folder.get("id") or "")
            for folder in folders
            if isinstance(folder, dict) and folder.get("id")
        }
        restored = 0
        ordered_entries = sorted(
            (entry for entry in entries if isinstance(entry, dict)),
            key=lambda entry: bool((entry.get("folder") or {}).get("parent_id")) if isinstance(entry.get("folder"), dict) else True,
        )
        for entry in ordered_entries:
            folder = entry.get("folder")
            if not isinstance(folder, dict):
                continue
            folder_id = str(folder.get("id") or entry.get("id") or "")
            if not folder_id or folder_id in existing_ids:
                continue
            path_text = entry.get("path")
            if not isinstance(path_text, str) or not Path(path_text).expanduser().is_dir():
                continue
            parent_id = str(folder.get("parent_id") or "")
            if parent_id and parent_id not in existing_ids:
                continue
            folders.append(folder)
            existing_ids.add(folder_id)
            restored += 1
        return restored

    def restore_trashed_metadata_file(self, item: dict[str, Any], entry: dict[str, Any]) -> None:
        metadata_file = item.get("metadata_file")
        metadata_text = entry.get("metadata_text")
        if not isinstance(metadata_file, str) or not metadata_file:
            return
        if not isinstance(metadata_text, str):
            return
        try:
            path = Path(metadata_file).expanduser()
            if path.exists():
                return
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(metadata_text, encoding="utf-8")
        except OSError as exc:
            log_event(f"could not restore metadata file for returned Trash item: {exc}")

    def sync_disk_files(self, data: dict[str, Any]) -> int:
        categories = data.setdefault("categories", [])
        items = data.setdefault("items", [])
        existing_files = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            identity = self.item_file_identity(item)
            if identity:
                existing_files.add(identity)

        added = 0
        for path in self.import_candidates():
            try:
                resolved = path.resolve()
                stat = resolved.stat()
            except OSError:
                continue
            resolved_text = str(resolved)
            identity = "file:" + resolved_text
            if identity in existing_files:
                continue
            item = self.disk_file_item(resolved, stat.st_mtime)
            if not item:
                continue
            category = item.get("category") or "Inbox"
            if category not in categories:
                categories.append(category)
            items.append(item)
            existing_files.add(identity)
            added += 1
        if added:
            log_event(f"auto-imported {added} library file(s)")
        return added

    def import_candidates(self) -> list[Path]:
        roots: list[Path] = []
        for path in (self.image_dir, self.video_dir, self.prompt_dir):
            if path not in roots:
                roots.append(path)
        if self.root not in roots:
            roots.append(self.root)
        if not self.using_external_root and MEDIA_DIR not in roots:
            roots.append(MEDIA_DIR)
        candidates: list[Path] = []
        seen: set[str] = set()
        for root in roots:
            if not root.exists() or not root.is_dir():
                continue
            if root.name == EXTERNAL_META_DIR_NAME:
                continue
            try:
                entries = sorted(root.iterdir(), key=lambda item: item.name.lower())
            except OSError:
                continue
            for path in entries:
                if not path.is_file() or path.name.startswith("."):
                    continue
                try:
                    key = str(path.resolve())
                except OSError:
                    key = str(path)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(path)
        return candidates

    def disk_file_item(self, path: Path, mtime: float) -> dict[str, Any] | None:
        ext = path.suffix.lower()
        mime = mimetypes.guess_type(path.name)[0] or ""
        created_at = dt.datetime.fromtimestamp(mtime, dt.timezone.utc).isoformat().replace("+00:00", "Z")
        title = path.stem.replace("-", " ").replace("_", " ").strip() or path.name
        base = {
            "id": uuid.uuid4().hex,
            "title": title,
            "prompt": title,
            "tags": [],
            "created_at": created_at,
            "file": str(path),
            "mime": mime or "application/octet-stream",
            "metadata": {
                "library_root": str(self.root),
                "imported": True,
            },
        }
        if ext in IMAGE_IMPORT_EXTENSIONS or mime.startswith("image/"):
            return {
                **base,
                "type": "image",
                "mode": "import",
                "category": "Image",
                "local_url": self.media_url(path),
            }
        if ext in VIDEO_IMPORT_EXTENSIONS or mime.startswith("video/"):
            return {
                **base,
                "type": "video",
                "mode": "import",
                "category": "Video",
                "local_url": self.media_url(path),
            }
        if ext in TEXT_IMPORT_EXTENSIONS or mime == "text/plain":
            try:
                prompt = path.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                prompt = ""
            if not prompt:
                prompt = title
            return {
                **base,
                "type": "prompt",
                "mode": "import",
                "category": "Prompt",
                "prompt": prompt[:200000],
                "local_url": None,
                "mime": "text/plain",
            }
        return None

    def add_category(self, name: str) -> list[str]:
        name = name.strip()
        if not name:
            raise StudioError("Category cannot be empty.")
        data = self._read()
        categories = data.setdefault("categories", [])
        if name not in categories:
            categories.append(name)
            categories.sort(key=str.lower)
            self._write(data)
        return categories

    def add_gallery_folder(self, name: str, parent_id: str | None = None) -> dict[str, Any]:
        name = re.sub(r"\s+", " ", str(name or "").strip())
        if not name:
            raise StudioError("Folder name cannot be empty.")
        if len(name) > 80:
            raise StudioError("Folder name is too long.")
        parent_id = str(parent_id or "").strip() or None
        data = self._read()
        folders = data.setdefault("gallery_folders", [])
        if parent_id:
            parent = next((folder for folder in folders if folder.get("id") == parent_id), None)
            if not parent:
                raise StudioError("Parent folder not found.", 404)
            if parent.get("parent_id"):
                raise StudioError("Gallery supports two folder levels.")
        siblings = [folder for folder in folders if (folder.get("parent_id") or None) == parent_id]
        if any(str(folder.get("name") or "").casefold() == name.casefold() for folder in siblings):
            raise StudioError("A folder with this name already exists.")
        directory_name = safe_file_stem(name, "Folder")
        if parent_id:
            parent_path = self.gallery_folder_path(parent_id, data)
            directory = unique_path(parent_path / directory_name)
        else:
            directory = unique_path(self.gallery_dir / directory_name)
        directory.mkdir(parents=True, exist_ok=False)
        folder = {
            "id": uuid.uuid4().hex,
            "name": name,
            "parent_id": parent_id,
            "directory_name": directory.name,
            "created_at": utc_now(),
            "order": len(siblings),
            "grid_slot": len(siblings) if parent_id else None,
        }
        if parent_id:
            for kind in ("Image", "Video", "Prompt", "Upload Image"):
                (directory / kind).mkdir(parents=True, exist_ok=True)
        folders.append(folder)
        self._write(data)
        return folder

    def update_gallery_folder_layout(self, folders: Any, sort_mode: Any = None) -> dict[str, Any]:
        if not isinstance(folders, list):
            raise StudioError("Folder layout is invalid.")
        data = self._read()
        by_id = {
            str(folder.get("id") or ""): folder
            for folder in data.get("gallery_folders", [])
            if isinstance(folder, dict) and folder.get("id")
        }
        updated: list[str] = []
        for entry in folders:
            if not isinstance(entry, dict):
                continue
            folder_id = str(entry.get("id") or "")
            folder = by_id.get(folder_id)
            if not folder:
                continue
            if "order" in entry:
                folder["order"] = max(0, int(entry.get("order") or 0))
            if "grid_slot" in entry and folder.get("parent_id"):
                folder["grid_slot"] = max(0, int(entry.get("grid_slot") or 0))
            updated.append(folder_id)
        if sort_mode is not None:
            normalized_sort = str(sort_mode or "")
            data["gallery_sort"] = normalized_sort if normalized_sort in {"abc", "ko"} else ""
        self._write(data)
        return {
            "updated": updated,
            "gallery_folders": data.get("gallery_folders", []),
            "gallery_sort": str(data.get("gallery_sort") or ""),
        }

    def gallery_folder(self, folder_id: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        data = data or self._read()
        folder = next(
            (candidate for candidate in data.get("gallery_folders", []) if candidate.get("id") == folder_id),
            None,
        )
        if not folder:
            raise StudioError("Gallery folder not found.", 404)
        return folder

    def gallery_folder_path(self, folder_id: str, data: dict[str, Any] | None = None) -> Path:
        data = data or self._read()
        folder = self.gallery_folder(folder_id, data)
        directory_name = safe_file_stem(str(folder.get("directory_name") or folder.get("name") or ""), "Folder")
        parent_id = str(folder.get("parent_id") or "").strip()
        if not parent_id:
            return self.gallery_dir / directory_name
        return self.gallery_folder_path(parent_id, data) / directory_name

    def gallery_output_dir(self, folder_id: Any, kind: str) -> Path:
        folder_id = str(folder_id or "").strip()
        if not folder_id:
            return {
                "Image": self.image_dir,
                "Video": self.video_dir,
                "Prompt": self.prompt_dir,
                "Upload Image": self.upload_dir,
            }[kind]
        data = self._read()
        folder = self.gallery_folder(folder_id, data)
        if not folder.get("parent_id"):
            raise StudioError("Select a second-level Gallery folder.")
        output = self.gallery_folder_path(folder_id, data) / kind
        output.mkdir(parents=True, exist_ok=True)
        return output

    def ensure_gallery_upload_dirs(self, data: dict[str, Any] | None = None) -> None:
        data = data or self._read()
        for folder in data.get("gallery_folders", []):
            if not isinstance(folder, dict) or not folder.get("parent_id"):
                continue
            (self.gallery_folder_path(str(folder.get("id")), data) / "Upload Image").mkdir(
                parents=True,
                exist_ok=True,
            )

    def upload_image_locations(self, data: dict[str, Any] | None = None) -> list[tuple[Path, str]]:
        data = data or self._read()
        self.ensure_gallery_upload_dirs(data)
        locations = [(self.upload_dir, "")]
        for folder in data.get("gallery_folders", []):
            if not isinstance(folder, dict) or not folder.get("parent_id"):
                continue
            folder_id = str(folder.get("id") or "")
            if folder_id:
                locations.append((self.gallery_folder_path(folder_id, data) / "Upload Image", folder_id))
        return locations

    def local_media_path(self, value: Any) -> Path | None:
        if isinstance(value, dict):
            value = value.get("url")
        if not isinstance(value, str) or not value.startswith("/media/"):
            return None
        try:
            return resolve_media_path(value)
        except StudioError:
            return None

    def move_related_upload_images(
        self,
        data: dict[str, Any],
        items: list[dict[str, Any]],
        related_ids: set[str],
        folder_id: str,
    ) -> dict[str, str]:
        upload_roots = [path.resolve() for path, _ in self.upload_image_locations(data)]
        target_dir = self.gallery_output_dir(folder_id, "Upload Image")
        candidates: set[Path] = set()

        def add(value: Any) -> None:
            path = self.local_media_path(value)
            if path is None:
                return
            resolved = path.resolve()
            if any(resolved.parent == root for root in upload_roots):
                candidates.add(resolved)

        for item in items:
            if str(item.get("id") or "") not in related_ids:
                continue
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            add(item.get("local_url"))
            add(metadata.get("start_image"))
            for field in ("source_images", "reference_images"):
                values = metadata.get(field)
                if isinstance(values, list):
                    for value in values:
                        add(value)

        replacements: dict[str, str] = {}
        for source in candidates:
            try:
                if source.parent.resolve() == target_dir.resolve():
                    continue
            except OSError:
                continue
            old_url = self.media_url(source)
            target = unique_path(target_dir / source.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            replacements[old_url] = self.media_url(target)
        return replacements

    def move_selected_upload_images(
        self,
        data: dict[str, Any],
        selected_ids: set[str],
        folder_id: str,
    ) -> dict[str, str]:
        wanted = {
            item_id.removeprefix("upload-card:")
            for item_id in selected_ids
            if item_id.startswith("upload-card:") or item_id.startswith("upload:")
        }
        if not wanted:
            return {}
        target_dir = self.gallery_output_dir(folder_id, "Upload Image")
        replacements: dict[str, str] = {}
        for upload_dir, source_folder_id in self.upload_image_locations(data):
            for source in upload_dir.iterdir():
                if not source.is_file():
                    continue
                upload_id = f"upload:{source_folder_id}:{source.name}" if source_folder_id else f"upload:{source.name}"
                if upload_id not in wanted:
                    continue
                try:
                    if source.parent.resolve() == target_dir.resolve():
                        continue
                except OSError:
                    continue
                old_url = self.media_url(source)
                target = unique_path(target_dir / source.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))
                replacements[old_url] = self.media_url(target)
        return replacements

    def replace_item_media_references(self, items: list[dict[str, Any]], replacements: dict[str, str]) -> None:
        if not replacements:
            return

        def replace(value: Any) -> Any:
            if isinstance(value, str):
                return replacements.get(value, value)
            if isinstance(value, dict) and isinstance(value.get("url"), str):
                return {**value, "url": replacements.get(value["url"], value["url"])}
            return value

        for item in items:
            if isinstance(item.get("local_url"), str):
                item["local_url"] = replacements.get(item["local_url"], item["local_url"])
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            if "start_image" in metadata:
                metadata["start_image"] = replace(metadata.get("start_image"))
            for field in ("source_images", "reference_images"):
                values = metadata.get(field)
                if isinstance(values, list):
                    metadata[field] = [replace(value) for value in values]

    def media_reference_keys(self, item: dict[str, Any]) -> set[str]:
        keys: set[str] = set()

        def add(value: Any) -> None:
            if isinstance(value, dict):
                value = value.get("url")
            if not isinstance(value, str) or not value:
                return
            bare = value.split("?", 1)[0]
            keys.add(bare)
            keys.add(urllib.parse.unquote(bare))

        add(item.get("local_url"))
        add(item.get("remote_url"))
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        add(metadata.get("start_image"))
        for field in ("source_images", "reference_images"):
            values = metadata.get(field)
            if isinstance(values, list):
                for value in values:
                    add(value)
        return {key for key in keys if key}

    def related_media_components(
        self,
        items: list[dict[str, Any]],
        seed_ids: set[str],
    ) -> list[set[str]]:
        components: list[set[str]] = []
        assigned: set[str] = set()
        for seed_id in seed_ids:
            if seed_id in assigned:
                continue
            ids = {seed_id}
            group_ids: set[str] = set()
            url_keys: set[str] = set()
            changed = True
            while changed:
                changed = False
                for item in items:
                    item_id = str(item.get("id") or "")
                    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                    group_id = str(metadata.get("group_id") or "")
                    parent_id = str(metadata.get("parent_id") or "")
                    item_url_keys = self.media_reference_keys(item)
                    related = (
                        item_id in ids
                        or (group_id and group_id in group_ids)
                        or (parent_id and (parent_id in ids or parent_id in group_ids))
                        or bool(item_url_keys & url_keys)
                    )
                    if not related:
                        continue
                    before = (len(ids), len(group_ids), len(url_keys))
                    if item_id:
                        ids.add(item_id)
                    if group_id:
                        group_ids.add(group_id)
                    if parent_id:
                        ids.add(parent_id)
                    url_keys.update(item_url_keys)
                    if before != (len(ids), len(group_ids), len(url_keys)):
                        changed = True
            component = {
                str(item.get("id") or "")
                for item in items
                if str(item.get("id") or "") in ids
            }
            component.discard("")
            if component:
                components.append(component)
                assigned.update(component)
        return components

    def move_items_to_gallery(self, ids: list[str], folder_id: str) -> dict[str, Any]:
        wanted = set(ids)
        if not wanted:
            raise StudioError("No items selected.")
        data = self._read()
        folder = self.gallery_folder(folder_id, data)
        if not folder.get("parent_id"):
            raise StudioError("Select a second-level Gallery folder.")
        items = [item for item in data.get("items", []) if isinstance(item, dict)]
        components = self.related_media_components(items, wanted)
        related_ids = set().union(*components) if components else set(wanted)
        replacements = self.move_selected_upload_images(data, wanted, folder_id)
        replacements.update(self.move_related_upload_images(data, items, related_ids, folder_id))
        self.replace_item_media_references(items, replacements)
        component_group_ids: dict[str, str] = {}
        for component in components:
            existing_group_ids = [
                str(item.get("metadata", {}).get("group_id") or "")
                for item in items
                if item.get("id") in component and isinstance(item.get("metadata"), dict)
            ]
            canonical_group_id = next((group_id for group_id in existing_group_ids if group_id), "")
            if not canonical_group_id:
                canonical_group_id = next((item_id for item_id in ids if item_id in component), "")
            if not canonical_group_id:
                canonical_group_id = next(iter(component))
            for item_id in component:
                component_group_ids[item_id] = canonical_group_id
        moved: list[str] = []
        for item in items:
            if item.get("id") not in related_ids:
                continue
            metadata = item.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
                item["metadata"] = metadata
            kind = {"image": "Image", "video": "Video", "prompt": "Prompt"}.get(str(item.get("type") or ""))
            if not kind:
                continue
            canonical_group_id = component_group_ids.get(str(item.get("id") or ""), "")
            item_changed = (
                str(metadata.get("gallery_folder_id") or "") != folder_id
                or bool(canonical_group_id and metadata.get("group_id") != canonical_group_id)
            )
            if canonical_group_id:
                metadata["group_id"] = canonical_group_id
            file_path = item.get("file")
            if isinstance(file_path, str) and file_path:
                source = Path(file_path).expanduser()
                if source.exists() and source.is_file():
                    target_dir = self.gallery_output_dir(folder_id, kind)
                    try:
                        already_in_target = source.resolve().parent == target_dir.resolve()
                    except OSError:
                        already_in_target = False
                    if not already_in_target:
                        target = unique_path(target_dir / source.name)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(source), str(target))
                        item["file"] = str(target)
                        if item.get("local_url"):
                            item["local_url"] = self.media_url(target)
                        item_changed = True
            metadata["gallery_folder_id"] = folder_id
            item["updated_at"] = utc_now()
            if item_changed:
                moved.append(str(item.get("id")))
        if not moved and not replacements:
            raise StudioError("The selected items are already in this Gallery folder.")
        self._write(data)
        return {
            "moved": moved,
            "count": len(moved) + len(replacements),
            "folder_id": folder_id,
        }

    def delete_gallery_folder(self, folder_id: str) -> dict[str, Any]:
        data = self._read()
        folder = self.gallery_folder(folder_id, data)
        child_ids = {
            str(candidate.get("id"))
            for candidate in data.get("gallery_folders", [])
            if candidate.get("parent_id") == folder_id and candidate.get("id")
        }
        folder_ids = {folder_id, *child_ids}
        deleted_folder_candidates = [
            candidate
            for candidate in data.get("gallery_folders", [])
            if isinstance(candidate, dict) and candidate.get("id") in folder_ids
        ]
        deleted_item_candidates: list[dict[str, Any]] = []
        deleted_items: list[str] = []
        kept_items: list[dict[str, Any]] = []
        for item in data.get("items", []):
            metadata = item.get("metadata")
            item_folder_id = str(metadata.get("gallery_folder_id") or "") if isinstance(metadata, dict) else ""
            if item_folder_id not in folder_ids:
                kept_items.append(item)
                continue
            if isinstance(item, dict):
                deleted_item_candidates.append(item)
            deleted_items.append(str(item.get("id") or ""))
        self.remember_deleted_gallery_folders(deleted_folder_candidates, data)
        self.remember_deleted_items(deleted_item_candidates)
        folder_path = self.gallery_folder_path(folder_id, data)
        if folder_path.exists() and folder_path.is_dir():
            try:
                safe_move_to_trash(str(folder_path), folder_path.parent)
            except StudioError as exc:
                raise StudioError(f"Could not move Gallery folder to {platform_trash_name()}: {exc.message}", exc.status) from exc
        for item in deleted_item_candidates:
            delete_item_files(item)
        data["items"] = kept_items
        data["gallery_folders"] = [
            candidate
            for candidate in data.get("gallery_folders", [])
            if candidate.get("id") not in folder_ids
        ]
        self._write(data)
        return {
            "deleted_folder_ids": sorted(folder_ids),
            "deleted_item_ids": [item_id for item_id in deleted_items if item_id],
            "count": len(deleted_items),
        }

    def rename_gallery_folder(self, folder_id: str, name: str) -> dict[str, Any]:
        name = re.sub(r"\s+", " ", str(name or "").strip())
        if not name:
            raise StudioError("Folder name cannot be empty.")
        if len(name) > 80:
            raise StudioError("Folder name is too long.")
        data = self._read()
        folder = self.gallery_folder(folder_id, data)
        parent_id = str(folder.get("parent_id") or "").strip() or None
        siblings = [
            candidate
            for candidate in data.get("gallery_folders", [])
            if (candidate.get("parent_id") or None) == parent_id and candidate.get("id") != folder_id
        ]
        if any(str(candidate.get("name") or "").casefold() == name.casefold() for candidate in siblings):
            raise StudioError("A folder with this name already exists.")

        old_path = self.gallery_folder_path(folder_id, data)
        target = old_path.parent / safe_file_stem(name, "Folder")
        if target != old_path:
            if target.exists():
                try:
                    same_folder = old_path.exists() and target.samefile(old_path)
                except OSError:
                    same_folder = False
                if same_folder:
                    temporary = unique_path(old_path.parent / f".rename-{uuid.uuid4().hex[:8]}")
                    old_path.rename(temporary)
                    temporary.rename(target)
                else:
                    target = unique_path(target)
                    old_path.rename(target)
            elif old_path.exists():
                old_path.rename(target)
            else:
                target.mkdir(parents=True, exist_ok=True)

        affected_folder_ids = {folder_id}
        if not parent_id:
            affected_folder_ids.update(
                str(candidate.get("id"))
                for candidate in data.get("gallery_folders", [])
                if candidate.get("parent_id") == folder_id and candidate.get("id")
            )
        old_root = old_path.resolve(strict=False)
        new_root = target.resolve(strict=False)
        for item in data.get("items", []):
            metadata = item.get("metadata")
            item_folder_id = str(metadata.get("gallery_folder_id") or "") if isinstance(metadata, dict) else ""
            if item_folder_id not in affected_folder_ids:
                continue
            file_changed = False
            for key in ("file", "metadata_file"):
                value = item.get(key)
                if not isinstance(value, str) or not value:
                    continue
                try:
                    relative = Path(value).expanduser().resolve(strict=False).relative_to(old_root)
                except (OSError, ValueError):
                    continue
                item[key] = str(new_root / relative)
                if key == "file":
                    file_changed = True
            if file_changed and item.get("local_url"):
                item["local_url"] = self.media_url(Path(str(item["file"])))
            item["updated_at"] = utc_now()

        folder["name"] = name
        folder["directory_name"] = target.name
        folder["updated_at"] = utc_now()
        self._write(data)
        return folder

    def add_item(self, item: dict[str, Any]) -> dict[str, Any]:
        data = self._read()
        identity = self.item_file_identity(item)
        if identity:
            data["items"] = [
                existing
                for existing in data.get("items", [])
                if not (
                    isinstance(existing, dict)
                    and self.is_imported_item(existing)
                    and self.item_file_identity(existing) == identity
                )
            ]
        self.dedupe_imported_items(data)
        category = item.get("category") or "Inbox"
        if category not in data.setdefault("categories", []):
            data["categories"].append(category)
        data["items"].append(item)
        self._write(data)
        return item

    def get_item(self, item_id: str) -> dict[str, Any]:
        data = self._read()
        for item in data.get("items", []):
            if item.get("id") == item_id:
                return item
        raise StudioError("Item not found.", 404)

    def update_item(self, item_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        data = self._read()
        for item in data.get("items", []):
            if item.get("id") == item_id:
                for key in ("category", "tags", "title"):
                    if key in patch:
                        item[key] = patch[key]
                if item.get("type") == "prompt" and "prompt" in patch:
                    prompt = str(patch.get("prompt") or "").strip()
                    if not prompt:
                        raise StudioError("Prompt content is empty.")
                    item["prompt"] = prompt
                    file_path = item.get("file")
                    if file_path:
                        Path(file_path).write_text(prompt, encoding="utf-8")
                if item.get("type") == "prompt" and "translation" in patch:
                    item["translation"] = str(patch.get("translation") or "").strip()
                item["updated_at"] = utc_now()
                if item.get("category") not in data.setdefault("categories", []):
                    data["categories"].append(item["category"])
                self._write(data)
                return item
        raise StudioError("Item not found.", 404)

    def delete_items(self, ids: list[str]) -> dict[str, Any]:
        wanted = set(ids)
        if not wanted:
            raise StudioError("No items selected.")
        data = self._read()
        candidates = [
            item
            for item in data.get("items", [])
            if isinstance(item, dict) and item.get("id") in wanted
        ]
        self.remember_deleted_items(candidates)
        kept = []
        deleted = []
        for item in data.get("items", []):
            if item.get("id") not in wanted:
                kept.append(item)
                continue
            delete_item_files(item)
            deleted.append(item.get("id"))
        data["items"] = kept
        self._write(data)
        return {"deleted": deleted, "count": len(deleted)}


class JobRegistry:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.jobs: dict[str, dict[str, Any]] = {}

    def create(self, kind: str, prompt: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        job = {
            "id": uuid.uuid4().hex,
            "kind": kind,
            "prompt": prompt,
            "status": "queued",
            "progress": 0,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "request_id": None,
            "item": None,
            "error": None,
            "context": context if isinstance(context, dict) else {},
        }
        with self.lock:
            self.jobs[job["id"]] = job
        return job

    def update(self, job_id: str, **patch: Any) -> dict[str, Any]:
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                dismissed = {"id": job_id, "dismissed": True, **patch, "updated_at": utc_now()}
                return dismissed
            job.update(patch)
            job["updated_at"] = utc_now()
            return dict(job)

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self.lock:
            if job_id not in self.jobs:
                raise StudioError("Job not found.", 404)
            job = self.jobs[job_id]
            if job.get("status") in {"done", "failed", "cancelled"}:
                return dict(job)
            job["cancel_requested"] = True
            job["status"] = "cancelled"
            job["error"] = "Cancelled locally. The remote xAI request may still finish server-side."
            job["updated_at"] = utc_now()
            return dict(job)

    def dismiss(self, job_id: str) -> dict[str, Any]:
        with self.lock:
            if job_id not in self.jobs:
                raise StudioError("Job not found.", 404)
            job = self.jobs[job_id]
            if job.get("status") not in {"done", "failed", "cancelled"}:
                job["cancel_requested"] = True
                job["status"] = "cancelled"
                job["error"] = "Cancelled locally. The remote xAI request may still finish server-side."
                job["updated_at"] = utc_now()
                return dict(job)
            return dict(self.jobs.pop(job_id))

    def is_cancelled(self, job_id: str) -> bool:
        with self.lock:
            job = self.jobs.get(job_id)
            return bool(job and (job.get("cancel_requested") or job.get("status") == "cancelled"))

    def get(self, job_id: str) -> dict[str, Any]:
        with self.lock:
            if job_id not in self.jobs:
                raise StudioError("Job not found.", 404)
            return dict(self.jobs[job_id])

    def all(self) -> list[dict[str, Any]]:
        with self.lock:
            return sorted(self.jobs.values(), key=lambda item: item["created_at"], reverse=True)[:24]

    def has_active(self, exclude_job_id: str | None = None) -> bool:
        with self.lock:
            return any(
                job.get("id") != exclude_job_id and job.get("status") not in {"done", "failed", "cancelled"}
                for job in self.jobs.values()
            )


class StudioApp:
    def __init__(self, auth_file: str, base_url: str, timeout: float) -> None:
        self.cli_auth_file = str(Path(auth_file).expanduser())
        self.auth_file = self.cli_auth_file
        self.client = XaiClient(self.auth_file, base_url, timeout)
        self.timeout = timeout
        self.library = Library()
        self.jobs = JobRegistry()
        self.last_heartbeat = time.monotonic()
        self.shutdown_lock = threading.RLock()
        self.shutdown_token: str | None = None
        self.usage_lock = threading.RLock()
        self.usage_cache: dict[str, Any] | None = None
        self.usage_checked_at = 0.0
        self.imagine_saved_keys_lock = threading.RLock()
        self.imagine_saved_keys_cache: dict[str, dict[str, Any]] = {}
        self.sync_current_cli_account()

    def sync_current_cli_account(self) -> None:
        summary = load_auth_summary(self.cli_auth_file)
        email = summary.get("email")
        if not isinstance(email, str) or not email:
            return
        current_id = account_id_for_identity(email, self.cli_auth_file)
        if current_id in hidden_account_ids():
            return
        try:
            record = snapshot_auth_file(self.cli_auth_file)
            data = read_accounts_file()
            saved = [item for item in data.get("accounts", []) if isinstance(item, dict)]
            saved = upsert_saved_account_preserving_order(saved, record, preserve_existing_tier=True)
            write_accounts_file({"active_id": record["id"], "accounts": saved})
            self.auth_file = self.cli_auth_file
            self.client.auth_file = self.cli_auth_file
        except StudioError as exc:
            log_event(f"account sync skipped: {exc.message}")

    def state(self) -> dict[str, Any]:
        library_state = self.library.state()
        return {
            "app": APP_NAME,
            "auth": load_auth_summary(self.auth_file),
            "cli_auth_file": self.cli_auth_file,
            "data_dir": str(DATA_DIR),
            "generation_provider": self.generation_provider(),
            "imagine": imagine_session_summary(),
            "imagine_accounts": imagine_accounts_summary(),
            "library": library_state.get("library") or self.library.info(),
            "categories": library_state["categories"],
            "gallery_folders": library_state["gallery_folders"],
            "gallery_sort": library_state.get("gallery_sort") or "",
            "items": library_state["items"],
            "uploads": self.list_uploaded_images(),
            "jobs": self.jobs.all(),
        }

    def generation_provider(self) -> str:
        provider = str(read_settings().get("generation_provider") or "build").strip().lower()
        if provider == "imagine" and imagine_session_summary().get("connected"):
            return "imagine"
        return "build"

    def set_generation_provider(self, provider: str) -> str:
        provider = provider if provider in {"build", "imagine"} else "build"
        if provider == "imagine" and not imagine_session_summary().get("connected"):
            raise StudioError("Capture an Imagine login session first.", 401)
        settings = read_settings()
        settings["generation_provider"] = provider
        write_settings(settings)
        return provider

    def list_uploaded_images(self) -> list[dict[str, Any]]:
        self.library.reload_paths()
        data = self.library._read()
        uploads: list[dict[str, Any]] = []
        for upload_dir, folder_id in self.library.upload_image_locations(data):
            for path in upload_dir.iterdir():
                if not path.is_file():
                    continue
                mime = mimetypes.guess_type(path.name)[0] or ""
                if not mime.startswith("image/"):
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                upload_id = f"upload:{folder_id}:{path.name}" if folder_id else f"upload:{path.name}"
                uploads.append(
                    {
                        "id": upload_id,
                        "type": "upload-image",
                        "title": path.stem,
                        "name": path.name,
                        "created_at": dt.datetime.fromtimestamp(
                            stat.st_mtime,
                            dt.timezone.utc,
                        ).isoformat().replace("+00:00", "Z"),
                        "local_url": self.library.media_url(path),
                        "file": str(path),
                        "gallery_folder_id": folder_id,
                        "mime": mime,
                        "size": stat.st_size,
                    }
                )
        uploads.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return uploads[:120]

    def write_imagine_media_debug(self, event: str, payload: dict[str, Any]) -> None:
        try:
            log_dir = DATA_DIR / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            record = {"at": utc_now(), "event": event, **payload}
            with (log_dir / "imagine_media_debug.jsonl").open("a", encoding="utf-8") as file:
                file.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        except OSError as exc:
            log_event(f"could not write Imagine media debug log: {exc}")

    def read_imagine_deleted_conversation_cache(self) -> dict[str, Any]:
        with _IMAGINE_DELETED_CACHE_LOCK:
            try:
                raw = json.loads(IMAGINE_DELETED_CONVERSATION_CACHE_PATH.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return {"version": 1, "entries": {}}
        if not isinstance(raw, dict):
            return {"version": 1, "entries": {}}
        entries = raw.get("entries")
        if not isinstance(entries, dict):
            raw["entries"] = {}
        raw["version"] = 1
        return raw

    def write_imagine_deleted_conversation_cache(self, cache: dict[str, Any]) -> None:
        entries = cache.get("entries") if isinstance(cache.get("entries"), dict) else {}
        if len(entries) > 5000:
            ordered = sorted(
                entries.items(),
                key=lambda item: str(item[1].get("checked_at") if isinstance(item[1], dict) else ""),
            )
            entries = dict(ordered[-5000:])
        payload = {"version": 1, "entries": entries}
        try:
            ensure_dirs()
            temp = IMAGINE_DELETED_CONVERSATION_CACHE_PATH.with_suffix(".json.tmp")
            with _IMAGINE_DELETED_CACHE_LOCK:
                temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                os.chmod(temp, 0o600)
                temp.replace(IMAGINE_DELETED_CONVERSATION_CACHE_PATH)
        except OSError as exc:
            log_event(f"could not save Imagine deleted conversation cache: {exc}")

    def imagine_deleted_conversation_cache_key(self, asset: dict[str, Any], account: dict[str, Any]) -> str:
        account_key = (
            normalize_identity_text(account.get("id"))
            or normalize_identity_text(account.get("email"))
            or normalize_identity_text(account.get("label"))
            or "account"
        )
        asset_id = str(asset.get("assetId") or asset.get("id") or "").strip()
        conversation_id = self.imagine_files_asset_conversation_id(asset)
        response_id = str(asset.get("responseId") or "").strip()
        return "|".join((account_key, asset_id, conversation_id, response_id))

    def imagine_deleted_cached_conversation_status(
        self,
        cache: dict[str, Any],
        asset: dict[str, Any],
        account: dict[str, Any],
    ) -> str | None:
        entries = cache.get("entries") if isinstance(cache.get("entries"), dict) else {}
        key = self.imagine_deleted_conversation_cache_key(asset, account)
        entry = entries.get(key)
        if not isinstance(entry, dict):
            return None
        checked_at = parse_time(entry.get("checked_at")) or dt.datetime.min.replace(tzinfo=dt.timezone.utc)
        age = dt.datetime.now(dt.timezone.utc) - checked_at
        status = str(entry.get("status") or "")
        ttl = dt.timedelta(days=30) if status else dt.timedelta(hours=6)
        if age > ttl:
            return None
        return status

    def remember_imagine_deleted_conversation_status(
        self,
        cache: dict[str, Any],
        asset: dict[str, Any],
        account: dict[str, Any],
        status: str,
    ) -> None:
        entries = cache.setdefault("entries", {})
        if not isinstance(entries, dict):
            entries = {}
            cache["entries"] = entries
        asset_id = str(asset.get("assetId") or asset.get("id") or "").strip()
        entries[self.imagine_deleted_conversation_cache_key(asset, account)] = {
            "asset_id": asset_id,
            "conversation_id": self.imagine_files_asset_conversation_id(asset),
            "response_id": str(asset.get("responseId") or "").strip(),
            "status": str(status or ""),
            "checked_at": utc_now(),
        }

    def imagine_headers(self, session: dict[str, Any] | None = None) -> dict[str, str]:
        cookies = valid_imagine_cookies(session)
        if not cookies:
            raise StudioError("Select or capture an Imagine account first.", 401)
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Baggage": (
                "sentry-environment=production,"
                "sentry-release=d6add6fb0460641fd482d767a335ef72b9b6abb8,"
                "sentry-public_key=b311e0f2690c81f25e2c4cf6d4f7ce1c"
            ),
            "Content-Type": "application/json",
            "Cookie": cookie_header_from_cookies(cookies),
            "Origin": IMAGINE_BASE,
            "Priority": "u=1, i",
            "Referer": IMAGINE_BASE + "/imagine",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": imagine_user_agent(),
            "x-statsig-id": imagine_statsig_id(),
            "x-xai-request-id": str(uuid.uuid4()),
        }
        headers.update(imagine_client_hint_headers())
        return headers

    def imagine_get_json(
        self,
        path: str,
        session: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        req = urllib.request.Request(
            IMAGINE_BASE + path,
            headers=self.imagine_headers(session),
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout, context=https_context()) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read(4000).decode("utf-8", errors="replace")
            raise StudioError(f"Imagine HTTP {exc.code}:\n{detail}", exc.code) from exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise StudioError(f"Imagine network error: {format_network_error(exc)}", 502) from exc
        return parse_json_or_sse_body(body)

    def imagine_post_json_with_session(
        self,
        path: str,
        payload: dict[str, Any],
        session: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        req = urllib.request.Request(
            IMAGINE_BASE + path,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=self.imagine_headers(session),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout, context=https_context()) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read(4000).decode("utf-8", errors="replace")
            raise StudioError(f"Imagine HTTP {exc.code}:\n{detail}", exc.code) from exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise StudioError(f"Imagine network error: {format_network_error(exc)}", 502) from exc
        return parse_json_or_sse_body(body)

    def imagine_browser_fetch_json(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        timeout: float = 18,
    ) -> dict[str, Any]:
        if not path.startswith("/"):
            raise StudioError("Imagine browser fetch path must be relative.", 400)
        headers = {"Accept": "application/json, text/plain, */*"}
        options: dict[str, Any] = {
            "method": method.upper(),
            "credentials": "include",
            "headers": headers,
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
            options["body"] = json.dumps(payload, ensure_ascii=False)
        expression = f"""
(async () => {{
  const response = await fetch({json.dumps(path)}, {json.dumps(options, ensure_ascii=False)});
  const text = await response.text();
  let parsed = null;
  try {{
    parsed = text ? JSON.parse(text) : {{}};
  }} catch (_error) {{
    parsed = {{ bodyText: text.slice(0, 4000) }};
  }}
  return {{
    ok: response.ok,
    status: response.status,
    statusText: response.statusText,
    payload: parsed
  }};
}})()
"""
        result = cdp_evaluate(expression, timeout=timeout)
        if not isinstance(result, dict):
            raise StudioError("Imagine browser fetch returned an invalid response.", 502)
        body = result.get("payload")
        if not result.get("ok"):
            preview = ""
            if isinstance(body, dict):
                preview = str(body.get("bodyText") or body)[:500]
            raise StudioError(f"Imagine browser HTTP {result.get('status')}: {preview}", int(result.get("status") or 502))
        return body if isinstance(body, dict) else {"value": body}

    def imagine_browser_get_json(self, path: str, timeout: float = 18) -> dict[str, Any]:
        return self.imagine_browser_fetch_json(path, method="GET", timeout=timeout)

    def imagine_browser_post_json(self, path: str, payload: dict[str, Any], timeout: float = 18) -> dict[str, Any]:
        return self.imagine_browser_fetch_json(path, method="POST", payload=payload, timeout=timeout)

    def imagine_media_headers(self, kind: str, session: dict[str, Any] | None = None) -> dict[str, str]:
        accept = "video/*,*/*;q=0.8" if kind == "video" else "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
        cookies = valid_imagine_cookies(session)
        if not cookies:
            raise StudioError("Select or capture an Imagine account first.", 401)
        return {
            "Accept": accept,
            "Cookie": cookie_header_from_cookies(cookies),
            "Referer": IMAGINE_BASE + "/imagine",
            "User-Agent": imagine_user_agent(),
        }

    def media_response_matches(self, url: str, mime: str, kind: str) -> bool:
        clean_mime = mime.split(";", 1)[0].strip().lower()
        path = urllib.parse.urlparse(url).path.lower()
        if clean_mime.startswith(f"{kind}/"):
            return True
        return path.endswith(media_extensions(kind)) and clean_mime in {"", "application/octet-stream", "binary/octet-stream"}

    def probe_imagine_media_url_detail(
        self,
        url: str,
        kind: str,
        session: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = self.imagine_media_headers(kind, session)
        headers["Range"] = "bytes=0-0"
        req = urllib.request.Request(url, headers=headers, method="GET")
        detail: dict[str, Any] = {"kind": kind, "ok": False, "candidate": debug_media_url(url)}
        try:
            with urllib.request.urlopen(req, timeout=min(max(2, self.timeout), 4), context=https_context()) as response:
                mime = response.headers.get("Content-Type") or ""
                status = response.status
                response.read(1)
        except urllib.error.HTTPError as exc:
            detail.update({"status": exc.code, "reason": exc.reason, "error": "http"})
            return detail
        except (urllib.error.URLError, OSError, TimeoutError):
            detail.update({"error": "network"})
            return detail
        detail.update({"ok": self.media_response_matches(url, mime, kind), "status": status, "mime": mime})
        return detail

    def probe_imagine_media_url(self, url: str, kind: str, session: dict[str, Any] | None = None) -> bool:
        return bool(self.probe_imagine_media_url_detail(url, kind, session).get("ok"))

    def download_imagine_media(self, url: str, kind: str = "image") -> tuple[bytes, str]:
        req = urllib.request.Request(url, headers=self.imagine_media_headers(kind), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=https_context()) as response:
                return response.read(), response.headers.get("Content-Type") or "application/octet-stream"
        except urllib.error.URLError as exc:
            raise StudioError(f"Could not download Imagine media URL: {format_network_error(exc)}", 502) from exc

    def extract_media_posts(self, value: Any, include_id_only: bool = False) -> list[dict[str, Any]]:
        posts: list[dict[str, Any]] = []
        stack = [value]
        seen = 0
        while stack and seen < 3000:
            seen += 1
            item = stack.pop()
            if isinstance(item, dict):
                if isinstance(item.get("id"), str) and (
                    imagine_post_has_media_shape(item)
                    or include_id_only
                ):
                    posts.append(item)
                for key in ("posts", "childPosts", "children", "results"):
                    child = item.get(key)
                    if isinstance(child, list):
                        stack.extend(child)
                post = item.get("post")
                if isinstance(post, dict):
                    stack.append(post)
            elif isinstance(item, list):
                stack.extend(item)
        deduped: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for post in posts:
            key = str(post.get("id") or id(post))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(post)
        return deduped

    def media_post_image_urls(self, post: dict[str, Any]) -> list[str]:
        urls: list[str] = []
        for key in ("hd1080MediaUrl", "hdMediaUrl", "mediaUrl", "thumbnailImageUrl", "previewImageUrl", "sourceImageUrl", "imageUrl"):
            url = normalize_media_api_url(post.get(key))
            if isinstance(url, str) and url not in urls:
                urls.append(url)
        for url in extract_media_urls(post, "image"):
            if url not in urls:
                urls.append(url)
        return sorted(urls, key=lambda candidate: media_url_score(candidate, "image"), reverse=True)

    def imported_media_posts_page_direct(
        self,
        limit: int = 10,
        session: dict[str, Any] | None = None,
        cursor: str = "",
        filter_payload: dict[str, Any] | None = None,
        extra_payload: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "limit": max(1, min(limit, 20)),
            "includeCanvas": False,
        }
        if filter_payload is None:
            payload["filter"] = {"source": "MEDIA_POST_SOURCE_LIKED"}
        elif filter_payload:
            payload["filter"] = filter_payload
        if extra_payload:
            payload.update(extra_payload)
        if cursor:
            payload["cursor"] = cursor
        return self.imagine_post_json_with_session("/rest/media/post/list", payload, session=session, timeout=timeout or 12)

    def get_media_post_direct(
        self,
        post_id: str,
        session: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        errors: list[str] = []
        for payload in ({"id": post_id}, {"ids": [post_id]}):
            path = "/rest/media/post/get" if "id" in payload else "/rest/media/post/bulk-get"
            try:
                data = self.imagine_post_json_with_session(path, payload, session=session, timeout=timeout or 12)
            except StudioError as exc:
                errors.append(exc.message[:240])
                continue
            post = data.get("post") if isinstance(data.get("post"), dict) else None
            if post:
                return post
            posts = data.get("posts") if isinstance(data.get("posts"), list) else []
            for candidate in posts:
                if isinstance(candidate, dict) and candidate.get("id") == post_id:
                    return candidate
        raise StudioError("Could not load the Imagine source media post. " + "; ".join(errors[-2:]), 502)

    def create_imagine_media_post_from_url(
        self,
        media_url: str,
        expected_media_type: str,
        prompt: str = "",
        session: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "mediaType": expected_media_type,
            "mediaUrl": media_url,
        }
        if prompt:
            payload["prompt"] = prompt
        data = self.imagine_post_json_with_session("/rest/media/post/create", payload, session=session, timeout=20)
        post = data.get("post") if isinstance(data.get("post"), dict) else None
        if not post:
            media_post = data.get("mediaPost") if isinstance(data.get("mediaPost"), dict) else None
            post = media_post
        if not post and isinstance(data.get("id"), str):
            post = data
        if not post:
            requested_url = normalize_media_api_url(media_url)
            for candidate in self.extract_media_posts(data):
                candidate_type = str(candidate.get("mediaType") or "")
                candidate_urls = {
                    normalize_media_api_url(candidate.get("mediaUrl")),
                    normalize_media_api_url(candidate.get("hdMediaUrl")),
                    normalize_media_api_url(candidate.get("hd1080MediaUrl")),
                }
                if candidate_type == expected_media_type or (requested_url and requested_url in candidate_urls):
                    post = candidate
                    break
        if not post:
            raise StudioError("Imagine did not return a media post for the generated image URL.", 502)
        post_id = post.get("id")
        if not isinstance(post_id, str) or not post_id:
            raise StudioError("Imagine returned a media post without an id.", 502)
        try:
            self.imagine_post_json_with_session("/rest/media/post/like", {"id": post_id}, session=session, timeout=12)
            post["_grok_studio_liked"] = True
        except StudioError as exc:
            post["_grok_studio_liked"] = False
            post["_grok_studio_like_error"] = exc.message[:500]
        return post

    def create_imagine_image_media_post(
        self,
        media_url: str,
        prompt: str = "",
        session: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.create_imagine_media_post_from_url(
            media_url,
            "MEDIA_POST_TYPE_IMAGE",
            prompt=prompt,
            session=session,
        )

    def create_imagine_video_media_post(
        self,
        media_url: str,
        prompt: str = "",
        session: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.create_imagine_media_post_from_url(
            media_url,
            "MEDIA_POST_TYPE_VIDEO",
            prompt=prompt,
            session=session,
        )

    def imagine_import_account_context(self, session: dict[str, Any]) -> dict[str, Any]:
        account_id = str(session.get("id") or "").strip()
        email = str(session.get("email") or "").strip()
        label = str(session.get("label") or "").strip()
        folder_source = email or label or account_id or "imagine"
        identity_values = session.get("identity_values") if isinstance(session.get("identity_values"), list) else []
        return {
            "id": account_id,
            "email": email,
            "label": label,
            "folder": safe_account_folder_name(folder_source, account_id[:12] or "imagine"),
            "identity_values": sorted({
                normalize_identity_text(value)
                for value in [*identity_values, account_id, email, label]
                if normalize_identity_text(value)
            }),
        }

    def imagine_saved_keys_cache_key(self, account: dict[str, Any]) -> str:
        return str(account.get("id") or account.get("email") or account.get("label") or "imagine").strip()

    def imagine_saved_post_match_keys(self, post: dict[str, Any]) -> set[str]:
        media_type = str(post.get("mediaType") or "")
        kind = "video" if media_type == "MEDIA_POST_TYPE_VIDEO" else "image"
        keys: set[str] = set()
        for value in (
            post.get("id"),
            post.get("originalPostId"),
            post.get("rootPostId"),
            post.get("parentPostId"),
            post.get("sourcePostId"),
            post.get("imagePostId"),
        ):
            post_id = str(value or "").strip()
            if post_id:
                keys.add(f"asset:{kind}:{post_id}")
                keys.add(f"post:{kind}:{post_id}")
        urls: list[str] = []
        if kind == "image":
            urls.extend(self.media_post_image_urls(post))
        else:
            for url in extract_media_urls(post, "video"):
                normalized = normalize_media_api_url(url)
                if normalized:
                    urls.append(normalized)
            for key in ("hd1080MediaUrl", "hdMediaUrl", "mediaUrl", "videoUrl", "previewVideoUrl"):
                normalized = normalize_media_api_url(post.get(key))
                if normalized:
                    urls.append(normalized)
        for url in urls:
            url_key = canonical_media_key(url)
            if url_key:
                keys.add(f"url:{url_key}")
        return keys

    def remember_imagine_saved_post_keys(
        self,
        account: dict[str, Any],
        posts: list[dict[str, Any]],
        next_cursor: str = "",
    ) -> None:
        cache_key = self.imagine_saved_keys_cache_key(account)
        if not cache_key or not posts:
            return
        new_keys: set[str] = set()
        for post in posts:
            if isinstance(post, dict):
                new_keys.update(self.imagine_saved_post_match_keys(post))
        if not new_keys:
            return
        with self.imagine_saved_keys_lock:
            current = self.imagine_saved_keys_cache.get(cache_key)
            current_keys = current.get("keys") if isinstance(current, dict) else set()
            keys = set(current_keys) if isinstance(current_keys, set) else set()
            keys.update(new_keys)
            self.imagine_saved_keys_cache[cache_key] = {
                "at": time.monotonic(),
                "keys": keys,
                "next_cursor": str(next_cursor or ""),
                "complete": not bool(next_cursor),
            }

    def cached_imagine_saved_keys(self, account: dict[str, Any]) -> dict[str, Any] | None:
        cache_key = self.imagine_saved_keys_cache_key(account)
        if not cache_key:
            return None
        with self.imagine_saved_keys_lock:
            entry = self.imagine_saved_keys_cache.get(cache_key)
            if not isinstance(entry, dict):
                return None
            age = time.monotonic() - float(entry.get("at") or 0)
            keys = entry.get("keys")
            if age > IMAGINE_SAVED_KEYS_CACHE_SECONDS or not isinstance(keys, set):
                self.imagine_saved_keys_cache.pop(cache_key, None)
                return None
            return {
                "keys": set(keys),
                "next_cursor": str(entry.get("next_cursor") or ""),
                "complete": bool(entry.get("complete")),
                "age_seconds": age,
            }

    def imagine_import_post_matches_account(
        self,
        post: dict[str, Any],
        account: dict[str, Any],
        *,
        allow_seed: bool = False,
    ) -> bool:
        if imagine_post_has_negative_import_hint(post):
            return False
        account_values = {
            normalize_identity_text(account.get("id")),
            normalize_identity_text(account.get("email")),
            normalize_identity_text(account.get("label")),
        }
        for value in account.get("identity_values") or []:
            normalized = normalize_identity_text(value)
            if normalized:
                account_values.add(normalized)
        account_values = {value for value in account_values if value}
        post_values = imagine_post_identity_values(post)
        if account_values and post_values and account_values.intersection(post_values):
            return True
        if imagine_post_has_positive_ownership_hint(post):
            return True
        if allow_seed and (not account_values or not post_values):
            return True
        return not post_values

    def imagine_import_post_candidates(self, post: dict[str, Any]) -> list[tuple[str, str]]:
        post_id = str(post.get("id") or "")
        media_type = str(post.get("mediaType") or "")
        image_urls = [
            url for url in self.media_post_image_urls(post)
            if isinstance(url, str) and is_possible_image_url_candidate(url)
        ]
        image_urls.sort(key=lambda url: media_url_score(url, "image"), reverse=True)
        if media_type == "MEDIA_POST_TYPE_IMAGE":
            return [("image", url) for url in image_urls]

        video_urls: list[str] = []

        def add_video_url(value: Any) -> None:
            url = normalize_media_api_url(value if isinstance(value, str) else None)
            if isinstance(url, str) and url not in video_urls:
                video_urls.append(url)

        for key in ("hd1080MediaUrl", "hdMediaUrl", "mediaUrl"):
            add_video_url(post.get(key))
        stack: list[Any] = [post]
        seen = 0
        while stack and seen < 600:
            seen += 1
            item = stack.pop()
            if isinstance(item, dict):
                for key, value in item.items():
                    key_text = str(key).lower()
                    if isinstance(value, str) and any(token in key_text for token in ("video", "mediaurl", "media_url", "url")):
                        add_video_url(value)
                    elif isinstance(value, (dict, list)):
                        stack.append(value)
            elif isinstance(item, list):
                stack.extend(value for value in item if isinstance(value, (dict, list)))
        for url in extract_media_urls(post, "video"):
            if url not in video_urls:
                video_urls.append(url)
        for image_url in self.media_post_image_urls(post):
            predicted = predicted_imagine_video_url(image_url, post_id)
            if predicted and predicted not in video_urls:
                video_urls.append(predicted)
        video_urls = [url for url in video_urls if isinstance(url, str) and is_possible_video_url_candidate(url)]
        video_urls.sort(key=lambda url: media_url_score(url, "video"), reverse=True)
        if media_type == "MEDIA_POST_TYPE_VIDEO" or video_urls:
            return [("video", url) for url in video_urls]
        if image_urls:
            return [("image", url) for url in image_urls]
        return []

    def imagine_asset_kind(self, asset: dict[str, Any]) -> str:
        for key in ("mimeType", "mime", "contentType"):
            mime = str(asset.get(key) or "").strip().lower()
            if mime.startswith("video/"):
                return "video"
            if mime.startswith("image/"):
                return "image"
        for key in ("mediaType", "assetType", "type", "kind"):
            value = str(asset.get(key) or "").strip().lower()
            if "video" in value:
                return "video"
            if "image" in value:
                return "image"
        for kind in ("video", "image"):
            if self.imagine_asset_media_url(asset, preferred_kind=kind):
                return kind
        return ""

    def imagine_asset_url_candidates(self, asset: dict[str, Any]) -> list[str]:
        candidates: list[str] = []

        def add(value: Any) -> None:
            if not isinstance(value, str) or not value.strip():
                return
            text = value.strip()
            if text.startswith("//"):
                text = "https:" + text
            elif text.startswith("/users/"):
                text = "https://assets.grok.com" + text
            elif text.startswith("users/"):
                text = "https://assets.grok.com/" + text
            url = normalize_media_api_url(text)
            if url and url not in candidates:
                candidates.append(url)

        for key in (
            "url",
            "mediaUrl",
            "downloadUrl",
            "previewUrl",
            "thumbnailUrl",
            "imageUrl",
            "videoUrl",
            "assetUrl",
            "publicUrl",
            "key",
        ):
            add(asset.get(key))
        aux_keys = asset.get("auxKeys")
        if isinstance(aux_keys, list):
            for value in aux_keys:
                add(value)
        elif isinstance(aux_keys, dict):
            for value in aux_keys.values():
                add(value)
        for kind in ("video", "image"):
            for url in extract_media_urls(asset, kind):
                add(url)
        return candidates

    def imagine_asset_media_url(self, asset: dict[str, Any], preferred_kind: str = "") -> str:
        candidates = self.imagine_asset_url_candidates(asset)
        if not candidates:
            return ""
        if preferred_kind == "video":
            usable = [url for url in candidates if is_possible_video_url_candidate(url)]
            usable.sort(key=lambda url: media_url_score(url, "video"), reverse=True)
            return usable[0] if usable else ""
        if preferred_kind == "image":
            usable = [url for url in candidates if is_possible_image_url_candidate(url)]
            usable.sort(key=lambda url: media_url_score(url, "image"), reverse=True)
            return usable[0] if usable else ""
        kind = "video" if any(is_possible_video_url_candidate(url) for url in candidates) else "image"
        if kind == "video":
            usable = [url for url in candidates if is_possible_video_url_candidate(url)]
        else:
            usable = [url for url in candidates if is_possible_image_url_candidate(url)]
        usable.sort(key=lambda url: media_url_score(url, kind), reverse=True)
        return usable[0] if usable else ""

    def imagine_asset_dedupe_key(self, asset: dict[str, Any], kind: str = "") -> str:
        item_type = kind or self.imagine_asset_kind(asset)
        asset_id = str(asset.get("assetId") or asset.get("id") or "").strip()
        if asset_id and item_type:
            return f"asset:{item_type}:{asset_id}"
        url_key = canonical_media_key(self.imagine_asset_media_url(asset, item_type))
        if url_key:
            return f"url:{url_key}"
        return ""

    def merge_imagine_asset_records(self, primary: list[dict[str, Any]], extra: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for asset in [*primary, *extra]:
            if not isinstance(asset, dict):
                continue
            kind = self.imagine_asset_kind(asset)
            key = self.imagine_asset_dedupe_key(asset, kind) or json.dumps(
                {
                    "assetId": asset.get("assetId") or asset.get("id"),
                    "key": asset.get("key"),
                    "url": asset.get("url") or asset.get("mediaUrl") or asset.get("downloadUrl"),
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(asset)
        return merged

    def extract_imagine_asset_records(self, value: Any, limit: int = 1000) -> list[dict[str, Any]]:
        assets: list[dict[str, Any]] = []
        seen: set[str] = set()
        stack: list[Any] = [value]
        while stack and len(assets) < limit:
            current = stack.pop()
            if isinstance(current, dict):
                asset_id = str(current.get("assetId") or current.get("id") or "").strip()
                has_media_shape = any(
                    key in current
                    for key in (
                        "key",
                        "mimeType",
                        "mime",
                        "contentType",
                        "auxKeys",
                        "sourceConversationId",
                        "rootAssetId",
                        "rootAssetSourceConversationId",
                    )
                ) or bool(self.imagine_asset_url_candidates(current))
                if asset_id and has_media_shape:
                    dedupe = self.imagine_asset_dedupe_key(current) or f"asset:{asset_id}"
                    if dedupe not in seen:
                        seen.add(dedupe)
                        assets.append(current)
                        if len(assets) >= limit:
                            break
                for child in current.values():
                    if isinstance(child, (dict, list)):
                        stack.append(child)
            elif isinstance(current, list):
                stack.extend(item for item in current if isinstance(item, (dict, list)))
        return assets

    def extract_imagine_workspace_ids(self, value: Any, limit: int = 200) -> list[str]:
        ids: list[str] = []
        seen: set[str] = set()
        stack: list[Any] = [value]
        while stack and len(ids) < limit:
            current = stack.pop()
            if isinstance(current, dict):
                workspaceish = any(
                    key in current
                    for key in (
                        "workspaceId",
                        "canvasId",
                        "workspaceKind",
                        "lastUseTime",
                        "modifyTime",
                        "lastUseTimestamp",
                    )
                )
                if workspaceish and "assetId" not in current:
                    for field in ("workspaceId", "canvasId", "id"):
                        value_id = str(current.get(field) or "").strip()
                        if value_id and value_id not in seen:
                            seen.add(value_id)
                            ids.append(value_id)
                            if len(ids) >= limit:
                                break
                for child in current.values():
                    if isinstance(child, (dict, list)):
                        stack.append(child)
            elif isinstance(current, list):
                stack.extend(item for item in current if isinstance(item, (dict, list)))
        return ids

    def imagine_asset_conversation_ids(self, asset: dict[str, Any]) -> list[str]:
        ids: list[str] = []
        for field in (
            "sourceConversationId",
            "rootAssetSourceConversationId",
            "conversationId",
            "workspaceId",
            "canvasId",
        ):
            value = str(asset.get(field) or "").strip()
            if value and value not in ids:
                ids.append(value)
        return ids

    def recent_imagine_assets(self, limit: int, session: dict[str, Any]) -> list[dict[str, Any]]:
        assets: list[dict[str, Any]] = []
        seen: set[str] = set()
        page_token = ""
        attempts = 0
        while len(assets) < limit and attempts < 12:
            attempts += 1
            page_size = 100
            query: dict[str, str] = {"pageSize": str(page_size)}
            if page_token:
                query["pageToken"] = page_token
            paths = [
                "/rest/assets?" + urllib.parse.urlencode({**query, "orderBy": "ORDER_BY_LAST_USE_TIME"}),
                "/rest/assets?" + urllib.parse.urlencode(query),
                "/rest/assets?" + urllib.parse.urlencode({"limit": str(page_size), **({"cursor": page_token} if page_token else {})}),
            ]
            payload: dict[str, Any] = {}
            last_error = ""
            for path in paths:
                try:
                    payload = self.imagine_browser_get_json(path, timeout=18)
                    if payload:
                        break
                except StudioError as exc:
                    last_error = exc.message[:240]
                try:
                    payload = self.imagine_get_json(path, session=session, timeout=18)
                    break
                except StudioError as exc:
                    last_error = exc.message[:240]
            if not payload:
                if last_error:
                    self.write_imagine_media_debug("asset_list_error", {"error": last_error})
                break
            for asset in self.extract_imagine_asset_records(payload, limit - len(assets)):
                key = self.imagine_asset_dedupe_key(asset) or str(asset.get("assetId") or asset.get("id") or "")
                if not key or key in seen:
                    continue
                seen.add(key)
                assets.append(asset)
                if len(assets) >= limit:
                    break
            next_token = str(
                payload.get("nextPageToken")
                or payload.get("nextPageCursor")
                or payload.get("nextCursor")
                or payload.get("cursor")
                or ""
            ).strip()
            if not next_token or next_token == page_token:
                break
            page_token = next_token
        return assets

    def recent_imagine_saved_posts(
        self,
        limit: int,
        session: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        limit = max(1, min(limit, 500))
        posts: list[dict[str, Any]] = []
        seen: set[str] = set()
        cursor = ""
        attempts = 0
        last_error = ""
        while len(posts) < limit and attempts < 25:
            attempts += 1
            page_size = min(20, limit - len(posts))
            try:
                payload = self.imported_media_posts_page_direct(
                    page_size,
                    session,
                    cursor,
                    filter_payload={"source": "MEDIA_POST_SOURCE_LIKED"},
                    timeout=10,
                )
            except StudioError as exc:
                last_error = exc.message[:240]
                break
            raw_posts = payload.get("posts") if isinstance(payload.get("posts"), list) else []
            for post in self.extract_media_posts({"posts": raw_posts}):
                post_id = str(post.get("id") or "").strip()
                key = post_id or json.dumps(post, sort_keys=True, ensure_ascii=False, default=str)[:240]
                if not key or key in seen:
                    continue
                seen.add(key)
                posts.append(post)
                if len(posts) >= limit:
                    break
            next_cursor = str(payload.get("nextCursor") or "").strip()
            if not next_cursor or next_cursor == cursor:
                cursor = ""
                break
            cursor = next_cursor
        info = {
            "post_count": len(posts),
            "attempt_count": attempts,
            "next_cursor": cursor if len(posts) >= limit else "",
            "error": last_error,
        }
        self.write_imagine_media_debug("saved_posts", info)
        return posts, info

    def recent_imagine_saved_keys(
        self,
        limit: int,
        session: dict[str, Any],
        account: dict[str, Any],
    ) -> tuple[set[str], dict[str, Any]]:
        limit = max(1, min(limit, 80))
        cached = self.cached_imagine_saved_keys(account)
        keys: set[str] = set(cached.get("keys") or set()) if cached else set()
        cursor = str(cached.get("next_cursor") or "") if cached else ""
        complete = bool(cached.get("complete")) if cached else False
        cache_hit = bool(cached and keys)
        if cache_hit and (complete or len(keys) >= limit):
            info = {
                "saved_key_count": len(keys),
                "attempt_count": 0,
                "next_cursor": cursor if not complete else "",
                "cache_hit": True,
                "complete": complete,
                "error": "",
            }
            self.write_imagine_media_debug("saved_keys", info)
            return keys, info

        attempts = 0
        post_count = 0
        last_error = ""
        seen_posts: set[str] = set()
        while len(keys) < limit and not complete and attempts < 12:
            attempts += 1
            page_size = min(20, max(1, limit - len(keys)))
            try:
                payload = self.imported_media_posts_page_direct(
                    page_size,
                    session,
                    cursor,
                    filter_payload={"source": "MEDIA_POST_SOURCE_LIKED"},
                    timeout=8,
                )
            except StudioError as exc:
                last_error = exc.message[:240]
                break
            raw_posts = payload.get("posts") if isinstance(payload.get("posts"), list) else []
            posts = self.extract_media_posts({"posts": raw_posts})
            post_count += len(posts)
            for post in posts:
                post_id = str(post.get("id") or "").strip()
                post_key = post_id or json.dumps(post, sort_keys=True, ensure_ascii=False, default=str)[:240]
                if post_key in seen_posts:
                    continue
                seen_posts.add(post_key)
                keys.update(self.imagine_saved_post_match_keys(post))
            next_cursor = str(payload.get("nextCursor") or "").strip()
            self.remember_imagine_saved_post_keys(account, posts, next_cursor)
            if not next_cursor or next_cursor == cursor:
                cursor = ""
                complete = True
                break
            cursor = next_cursor

        info = {
            "saved_key_count": len(keys),
            "post_count": post_count,
            "attempt_count": attempts,
            "next_cursor": cursor if not complete else "",
            "cache_hit": cache_hit,
            "complete": complete,
            "error": last_error,
        }
        self.write_imagine_media_debug("saved_keys", info)
        return keys, info

    def recent_imagine_files_assets(
        self,
        limit: int,
        session: dict[str, Any],
        page_token: str = "",
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        limit = max(1, min(limit, 720))
        page_token = str(page_token or "").strip()
        assets: list[dict[str, Any]] = []
        seen: set[str] = set()
        attempts = 0
        next_page_token = ""
        last_error = ""
        response_source = ""

        while len(assets) < limit and attempts < 12:
            attempts += 1
            page_size = max(1, min(100, limit - len(assets)))
            query = {
                "pageSize": str(page_size),
                "orderBy": "ORDER_BY_LAST_USE_TIME",
                "source": "SOURCE_ANY",
                "isLatest": "true",
                "includeImagineFiles": "true",
            }
            if page_token:
                query["pageToken"] = page_token
            path = "/rest/assets?" + urllib.parse.urlencode(query)
            payload: dict[str, Any] = {}
            try:
                payload = self.imagine_get_json(path, session=session, timeout=18)
                response_source = response_source or "session"
            except StudioError as exc:
                last_error = exc.message[:240]
                try:
                    payload = self.imagine_browser_get_json(path, timeout=18)
                    response_source = response_source or "browser"
                except StudioError as fallback_exc:
                    last_error = fallback_exc.message[:240]
                    break
            records = self.extract_imagine_asset_records(payload, 200)
            for record in records:
                asset = dict(record)
                asset["_grokFilesPage"] = True
                asset["_grokFilesRest"] = True
                key = self.imagine_asset_dedupe_key(asset) or str(asset.get("assetId") or asset.get("id") or "")
                if not key or key in seen:
                    continue
                seen.add(key)
                assets.append(asset)
            next_page_token = str(
                payload.get("nextPageToken")
                or payload.get("nextPageCursor")
                or payload.get("nextCursor")
                or payload.get("cursor")
                or ""
            ).strip()
            if not next_page_token or next_page_token == page_token:
                break
            page_token = next_page_token

        info = {
            "asset_count": len(assets),
            "attempt_count": attempts,
            "next_page_token": next_page_token if len(assets) >= limit else "",
            "error": last_error,
            "source": response_source,
        }
        self.write_imagine_media_debug("files_rest_assets", info)
        return assets, info

    def recent_imagine_workspace_ids(self, limit: int, session: dict[str, Any]) -> list[str]:
        ids: list[str] = []
        page_token = ""
        while len(ids) < limit:
            page_size = max(1, min(100, limit - len(ids)))
            query = {
                "kind": "WORKSPACE_KIND_IMAGINE",
                "pageSize": str(page_size),
                "orderBy": "ORDER_BY_LAST_USE_TIME",
            }
            if page_token:
                query["pageToken"] = page_token
            path = "/rest/workspaces?" + urllib.parse.urlencode(query)
            try:
                payload = self.imagine_browser_get_json(path, timeout=18)
                if not payload:
                    payload = self.imagine_get_json(path, session=session, timeout=18)
            except StudioError:
                payload = self.imagine_get_json(path, session=session, timeout=18)
            for workspace_id in self.extract_imagine_workspace_ids(payload, limit - len(ids)):
                if workspace_id not in ids:
                    ids.append(workspace_id)
                    if len(ids) >= limit:
                        break
            next_token = str(payload.get("nextPageToken") or payload.get("nextCursor") or "").strip()
            if not next_token or next_token == page_token:
                break
            page_token = next_token
        return ids

    def imagine_conversation_assets(
        self,
        workspace_limit: int,
        asset_limit: int,
        session: dict[str, Any],
        seed_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        workspace_ids: list[str] = []
        for workspace_id in seed_ids or []:
            workspace_id = str(workspace_id or "").strip()
            if workspace_id and workspace_id not in workspace_ids:
                workspace_ids.append(workspace_id)
        try:
            for workspace_id in self.recent_imagine_workspace_ids(workspace_limit, session):
                if workspace_id not in workspace_ids:
                    workspace_ids.append(workspace_id)
        except StudioError as exc:
            self.write_imagine_media_debug("import_workspace_list_error", {"error": exc.message[:300]})

        assets: list[dict[str, Any]] = []
        seen: set[str] = set()
        for workspace_id in workspace_ids[:workspace_limit]:
            if len(assets) >= asset_limit:
                break
            responses: list[dict[str, Any]] = []
            last_error = ""
            for payload in ({"canvasId": workspace_id}, {"workspaceId": workspace_id}):
                try:
                    response = self.imagine_browser_post_json("/rest/media/conversation/get", payload, timeout=18)
                    if response:
                        responses.append(response)
                        break
                except StudioError as exc:
                    last_error = exc.message[:300]
                try:
                    response = self.imagine_post_json_with_session("/rest/media/conversation/get", payload, session=session, timeout=18)
                    responses.append(response)
                    break
                except StudioError as exc:
                    last_error = exc.message[:300]

            canvas_requests = (
                ("/rest/media/canvas/get", ({"id": workspace_id}, {"canvasId": workspace_id}, {"workspaceId": workspace_id})),
                ("/rest/media/canvas/node/list", ({"canvasId": workspace_id}, {"canvasId": workspace_id, "pageSize": 200}, {"workspaceId": workspace_id})),
            )
            for path, payloads in canvas_requests:
                if len(assets) >= asset_limit:
                    break
                for payload in payloads:
                    try:
                        response = self.imagine_browser_post_json(path, payload, timeout=18)
                        if response:
                            responses.append(response)
                            break
                    except StudioError as exc:
                        last_error = exc.message[:300]
                    try:
                        response = self.imagine_post_json_with_session(path, payload, session=session, timeout=18)
                        responses.append(response)
                        break
                    except StudioError as exc:
                        last_error = exc.message[:300]

            if not responses:
                self.write_imagine_media_debug(
                    "import_conversation_error",
                    {"workspace_id": workspace_id, "error": last_error},
                )
                continue
            for response in responses:
                if len(assets) >= asset_limit:
                    break
                for asset in self.extract_imagine_asset_records(response, asset_limit - len(assets)):
                    key = self.imagine_asset_dedupe_key(asset) or str(asset.get("assetId") or asset.get("id") or "")
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    assets.append(asset)
                    if len(assets) >= asset_limit:
                        break
        self.write_imagine_media_debug(
            "import_conversation_assets",
            {
                "workspace_count": len(workspace_ids),
                "asset_count": len(assets),
                "workspace_limit": workspace_limit,
                "asset_limit": asset_limit,
            },
        )
        return assets

    def imagine_deleted_local_storage_assets(
        self,
        session: dict[str, Any],
        asset_limit: int,
    ) -> tuple[list[dict[str, Any]], int, int]:
        expression = """
(() => {
  const prefix = "atlas_deleted_assets_";
  const backupKey = "grok_studio_deleted_asset_events";
  const groupsByCanvas = new Map();
  const addGroup = (canvasId, assetIds) => {
    if (!canvasId || !Array.isArray(assetIds) || !assetIds.length) return;
    const existing = groupsByCanvas.get(canvasId) || [];
    for (const value of assetIds) {
      const assetId = typeof value === "string" ? value.trim() : "";
      if (assetId && !existing.includes(assetId)) existing.push(assetId);
    }
    if (existing.length) groupsByCanvas.set(canvasId, existing);
  };
  const readAtlasGroups = () => {
    for (let index = 0; index < localStorage.length; index += 1) {
      const key = localStorage.key(index);
      if (!key || !key.startsWith(prefix)) continue;
      const canvasId = key.slice(prefix.length);
      try {
        const parsed = JSON.parse(localStorage.getItem(key) || "[]");
        addGroup(canvasId, parsed);
      } catch (_error) {}
    }
  };
  const readBackupGroups = () => {
    try {
      const events = JSON.parse(localStorage.getItem(backupKey) || "[]");
      if (!Array.isArray(events)) return;
      for (const event of events) {
        if (!event || typeof event !== "object") continue;
        const groups = Array.isArray(event.groups) ? event.groups : [];
        for (const group of groups) {
          if (!group || typeof group !== "object") continue;
          addGroup(String(group.canvasId || ""), Array.isArray(group.assetIds) ? group.assetIds : []);
        }
      }
    } catch (_error) {}
  };
  readAtlasGroups();
  readBackupGroups();
  if (!window.__grokStudioDeletedTrackerInstalled) {
    const snapshotGroups = () => {
      const groups = [];
      for (let index = 0; index < localStorage.length; index += 1) {
        const key = localStorage.key(index);
        if (!key || !key.startsWith(prefix)) continue;
        const canvasId = key.slice(prefix.length);
        try {
          const parsed = JSON.parse(localStorage.getItem(key) || "[]");
          if (canvasId && Array.isArray(parsed) && parsed.length) {
            groups.push({
              canvasId,
              assetIds: parsed.filter((value) => typeof value === "string" && value.trim()),
            });
          }
        } catch (_error) {}
      }
      return groups;
    };
    const rememberDeleteEvent = (event) => {
      try {
        const events = JSON.parse(localStorage.getItem(backupKey) || "[]");
        const next = Array.isArray(events) ? events.slice(-499) : [];
        next.push({
          at: Date.now(),
          url: String(event.url || ""),
          method: String(event.method || ""),
          status: event.status || 0,
          body: event.body || null,
          groups: snapshotGroups(),
        });
        localStorage.setItem(backupKey, JSON.stringify(next));
      } catch (_error) {}
    };
    const originalFetch = window.fetch;
    if (typeof originalFetch === "function") {
      window.fetch = async (...args) => {
        const input = args[0];
        const init = args[1] || {};
        const url = typeof input === "string" ? input : String((input && input.url) || "");
        const method = String(init.method || (input && input.method) || "GET").toUpperCase();
        const shouldTrack = url.includes("/rest/media/canvas/node/delete") || url.includes("/rest/media/canvas/delete");
        let body = null;
        if (shouldTrack) {
          try {
            const rawBody = init.body;
            if (typeof rawBody === "string") {
              body = JSON.parse(rawBody);
            }
          } catch (_error) {
            body = null;
          }
        }
        const response = await originalFetch.apply(this, args);
        if (shouldTrack) {
          rememberDeleteEvent({ url, method, status: response.status, body });
        }
        return response;
      };
      window.__grokStudioDeletedTrackerInstalled = true;
    }
  }
  const groups = [];
  for (let index = 0; index < localStorage.length; index += 1) {
    // Keep this loop so older pages that add atlas keys after installation are read immediately.
    const key = localStorage.key(index);
    if (!key || !key.startsWith(prefix)) continue;
    try {
      addGroup(key.slice(prefix.length), JSON.parse(localStorage.getItem(key) || "[]"));
    } catch (_error) {}
  }
  for (const [canvasId, assetIds] of groupsByCanvas.entries()) groups.push({ canvasId, assetIds });
  return { groups, trackerInstalled: Boolean(window.__grokStudioDeletedTrackerInstalled) };
})()
"""
        try:
            result = cdp_evaluate(expression, timeout=8)
        except StudioError as exc:
            self.write_imagine_media_debug("deleted_local_storage_skipped", {"error": exc.message[:240]})
            return [], 0, 0
        groups = result.get("groups") if isinstance(result, dict) and isinstance(result.get("groups"), list) else []
        ordered: list[tuple[str, str]] = []
        seen_ids: set[str] = set()
        for group in groups:
            if not isinstance(group, dict):
                continue
            canvas_id = str(group.get("canvasId") or "").strip()
            asset_ids = group.get("assetIds") if isinstance(group.get("assetIds"), list) else []
            for value in asset_ids:
                asset_id = str(value or "").strip()
                if not asset_id or asset_id in seen_ids:
                    continue
                seen_ids.add(asset_id)
                ordered.append((canvas_id, asset_id))
                if len(ordered) >= asset_limit:
                    break
            if len(ordered) >= asset_limit:
                break

        assets: list[dict[str, Any]] = []
        for offset in range(0, len(ordered), 50):
            batch = ordered[offset: offset + 50]
            ids = [asset_id for _, asset_id in batch]
            try:
                payload = self.imagine_post_json_with_session(
                    "/rest/media/canvas/assets",
                    {"assetIds": ids},
                    session=session,
                    timeout=18,
                )
            except StudioError as exc:
                self.write_imagine_media_debug(
                    "deleted_local_storage_asset_error",
                    {"asset_count": len(ids), "error": exc.message[:240]},
                )
                continue
            by_id = {
                str(asset.get("assetId") or asset.get("id") or "").strip(): asset
                for asset in payload.get("assets", [])
                if isinstance(asset, dict)
            }
            canvas_by_id = {asset_id: canvas_id for canvas_id, asset_id in batch}
            for asset_id in ids:
                asset = by_id.get(asset_id)
                if not asset:
                    continue
                asset = dict(asset)
                asset["_grokLocalDeleted"] = True
                asset["_grokDeletedCanvasId"] = canvas_by_id.get(asset_id, "")
                assets.append(asset)
                if len(assets) >= asset_limit:
                    break
            if len(assets) >= asset_limit:
                break

        self.write_imagine_media_debug(
            "deleted_local_storage_assets",
            {
                "group_count": len(groups),
                "asset_id_count": len(ordered),
                "asset_count": len(assets),
                "asset_limit": asset_limit,
            },
        )
        return assets, len(groups), len(ordered)

    def imagine_files_page_assets(self, asset_limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        asset_limit = max(1, min(asset_limit, 1800))
        try:
            self.open_imagine_chrome_page(IMAGINE_BASE + "/files", visible=False)
        except StudioError as exc:
            self.write_imagine_media_debug("files_page_open_skipped", {"error": exc.message[:240]})
        expression = """
(async () => {
  const maxAssets = __ASSET_LIMIT__;
  const trackerKey = "grok_studio_files_delete_tracker_v1";
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const safeKeys = (obj) => {
    try { return Object.keys(obj || {}); } catch (_error) { return []; }
  };
  const safeEntries = (obj) => {
    try { return Object.entries(obj || {}); } catch (_error) { return []; }
  };
  const safeGet = (obj, key) => {
    try { return obj ? obj[key] : undefined; } catch (_error) { return undefined; }
  };
  const locationText = String(location.href || "");
  const filesPage = /^https:\\/\\/(www\\.)?grok\\.com\\/files(?:[?#/]|$)/i.test(locationText);
  const savedPage = /^https:\\/\\/(www\\.)?grok\\.com\\/imagine\\/saved(?:[?#/]|$)/i.test(locationText);
  if (!filesPage && !savedPage) {
    return { location: locationText, assets: [], trackedAssets: [], skipped: "not-files-page" };
  }
  const copyAsset = (asset) => {
    const assetId = String(safeGet(asset, "assetId") || safeGet(asset, "id") || "").trim();
    if (!assetId) return null;
    const auxKeys = safeGet(asset, "auxKeys");
    return {
      assetId,
      id: assetId,
      mimeType: safeGet(asset, "mimeType") || safeGet(asset, "contentType") || "",
      name: safeGet(asset, "name") || safeGet(asset, "fileName") || "",
      sizeBytes: safeGet(asset, "sizeBytes") || 0,
      createTime: safeGet(asset, "createTime") || "",
      lastUseTime: safeGet(asset, "lastUseTime") || "",
      updateTime: safeGet(asset, "updateTime") || "",
      summary: safeGet(asset, "summary") || "",
      prompt: safeGet(asset, "prompt") || "",
      originalPrompt: safeGet(asset, "originalPrompt") || "",
      title: safeGet(asset, "title") || "",
      previewImageKey: safeGet(asset, "previewImageKey") || "",
      key: safeGet(asset, "key") || "",
      hdKey: safeGet(asset, "hdKey") || "",
      hd1080Key: safeGet(asset, "hd1080Key") || "",
      auxKeys: auxKeys && typeof auxKeys === "object" ? auxKeys : {},
      responseId: safeGet(asset, "responseId") || "",
      isDeleted: Boolean(safeGet(asset, "isDeleted")),
      fileSource: safeGet(asset, "fileSource") || "",
      currentConversationId: safeGet(asset, "currentConversationId") || "",
      rootAssetId: safeGet(asset, "rootAssetId") || "",
      sourceConversationId: safeGet(asset, "sourceConversationId") || "",
      rootAssetSourceConversationId: safeGet(asset, "rootAssetSourceConversationId") || "",
      inlineStatus: safeGet(asset, "inlineStatus") || "",
      isModelGenerated: Boolean(safeGet(asset, "isModelGenerated")),
      isLatest: Boolean(safeGet(asset, "isLatest")),
      isRootAssetCreatedByModel: Boolean(safeGet(asset, "isRootAssetCreatedByModel")),
      sharedWithTeam: Boolean(safeGet(asset, "sharedWithTeam")),
      isPublic: Boolean(safeGet(asset, "isPublic")),
      width: safeGet(asset, "width") || 0,
      height: safeGet(asset, "height") || 0,
      rRated: Boolean(safeGet(asset, "rRated")),
      _grokFilesPage: true
    };
  };
  const fiberValues = (el) => safeKeys(el)
    .filter((key) => key.startsWith("__reactFiber$") || key.startsWith("__reactProps$"))
    .map((key) => safeGet(el, key))
    .filter(Boolean);
  const collectAssets = () => {
    const roots = [
      document.body,
      document.querySelector("main"),
      ...Array.from(document.querySelectorAll("video[src*='assets.grok.com'], img[src*='assets.grok.com']")).slice(0, 12)
    ].filter(Boolean);
    const stack = [];
    for (const root of roots) stack.push(...fiberValues(root));
    const seenObjects = new Set();
    const assets = new Map();
    let visited = 0;
    while (stack.length && visited < 240000) {
      const current = stack.pop();
      if (!current || typeof current !== "object" || seenObjects.has(current)) continue;
      seenObjects.add(current);
      visited += 1;
      if (Array.isArray(current)) {
        for (const child of current.slice(0, 1200)) {
          if (child && typeof child === "object") stack.push(child);
        }
        continue;
      }
      const assetId = safeGet(current, "assetId") || safeGet(current, "id");
      if (
        typeof assetId === "string"
        && (safeGet(current, "mimeType") || safeGet(current, "key") || safeGet(current, "fileSource") || safeGet(current, "name"))
      ) {
        const copied = copyAsset(current);
        if (copied && !assets.has(copied.assetId) && assets.size < maxAssets) {
          assets.set(copied.assetId, copied);
        }
      }
      for (const [, child] of safeEntries(current)) {
        if (child && typeof child === "object") stack.push(child);
      }
    }
    return { assets: Array.from(assets.values()), visited };
  };
  const scrollContainers = () => {
    const base = [
      document.scrollingElement,
      document.documentElement,
      document.body,
      ...Array.from(document.querySelectorAll("*"))
    ].filter(Boolean);
    const seen = new Set();
    return base
      .filter((el) => {
        if (!el || seen.has(el)) return false;
        seen.add(el);
        try {
          return Number(el.scrollHeight || 0) > Number(el.clientHeight || 0) + 80;
        } catch (_error) {
          return false;
        }
      })
      .sort((a, b) => {
        const aRange = Number(a.scrollHeight || 0) - Number(a.clientHeight || 0);
        const bRange = Number(b.scrollHeight || 0) - Number(b.clientHeight || 0);
        return bRange - aRange;
      })
      .slice(0, 8);
  };
  const warmFilesPage = async () => {
    if (!filesPage) return { rounds: 0, moved: false, containerCount: 0, assets: [] };
    const remembered = new Map();
    const rememberCurrentAssets = () => {
      const snapshot = collectAssets();
      for (const asset of snapshot.assets || []) {
        if (asset && asset.assetId && !remembered.has(asset.assetId)) {
          remembered.set(asset.assetId, asset);
        }
      }
      return remembered.size;
    };
    for (const el of scrollContainers()) {
      try {
        el.scrollTop = 0;
        el.dispatchEvent(new Event("scroll", { bubbles: true }));
      } catch (_error) {}
    }
    await sleep(550);
    let rounds = 0;
    let movedAny = false;
    let bestCount = rememberCurrentAssets();
    let stable = 0;
    for (let index = 0; index < 42; index += 1) {
      const containers = scrollContainers();
      let moved = false;
      for (const el of containers) {
        try {
          const before = Number(el.scrollTop || 0);
          const maxTop = Math.max(0, Number(el.scrollHeight || 0) - Number(el.clientHeight || 0));
          const step = Math.max(720, Math.round(Number(el.clientHeight || 640) * 1.6));
          const next = Math.min(maxTop, before + step);
          if (next > before) {
            el.scrollTop = next;
            el.dispatchEvent(new Event("scroll", { bubbles: true }));
            el.dispatchEvent(new WheelEvent("wheel", { deltaY: step, bubbles: true, cancelable: true }));
            moved = true;
          }
        } catch (_error) {}
      }
      try {
        window.dispatchEvent(new WheelEvent("wheel", { deltaY: 1800, bubbles: true, cancelable: true }));
      } catch (_error) {}
      rounds += 1;
      movedAny = movedAny || moved;
      await sleep(index < 6 ? 480 : 300);
      const count = rememberCurrentAssets();
      if (count > bestCount) {
        bestCount = count;
        stable = 0;
      } else {
        stable += 1;
      }
      if (index >= 14 && stable >= 8 && !moved) break;
    }
    await sleep(350);
    rememberCurrentAssets();
    return { rounds, moved: movedAny, containerCount: scrollContainers().length, assets: Array.from(remembered.values()).slice(0, maxAssets) };
  };
  const compactAssets = (assets) => assets
    .filter((asset) => asset && asset.assetId)
    .slice(0, maxAssets)
    .map((asset) => ({
      assetId: asset.assetId,
      id: asset.assetId,
      mimeType: asset.mimeType || "",
      name: asset.name || "",
      sizeBytes: asset.sizeBytes || 0,
      createTime: asset.createTime || "",
      lastUseTime: asset.lastUseTime || "",
      updateTime: asset.updateTime || "",
      summary: asset.summary || "",
      prompt: asset.prompt || "",
      originalPrompt: asset.originalPrompt || "",
      title: asset.title || "",
      previewImageKey: asset.previewImageKey || "",
      key: asset.key || "",
      hdKey: asset.hdKey || "",
      hd1080Key: asset.hd1080Key || "",
      auxKeys: asset.auxKeys && typeof asset.auxKeys === "object" ? asset.auxKeys : {},
      responseId: asset.responseId || "",
      isDeleted: Boolean(asset.isDeleted),
      fileSource: asset.fileSource || "",
      currentConversationId: asset.currentConversationId || "",
      rootAssetId: asset.rootAssetId || "",
      sourceConversationId: asset.sourceConversationId || "",
      rootAssetSourceConversationId: asset.rootAssetSourceConversationId || "",
      inlineStatus: asset.inlineStatus || "",
      isModelGenerated: Boolean(asset.isModelGenerated),
      isLatest: Boolean(asset.isLatest),
      isRootAssetCreatedByModel: Boolean(asset.isRootAssetCreatedByModel),
      sharedWithTeam: Boolean(asset.sharedWithTeam),
      isPublic: Boolean(asset.isPublic),
      width: asset.width || 0,
      height: asset.height || 0,
      rRated: Boolean(asset.rRated),
      _grokFilesPage: true
    }));
  const readTracker = () => {
    try {
      const parsed = JSON.parse(localStorage.getItem(trackerKey) || "{}");
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
      return {
        version: 1,
        installedAt: parsed.installedAt || Date.now(),
        events: Array.isArray(parsed.events) ? parsed.events : [],
        snapshots: Array.isArray(parsed.snapshots) ? parsed.snapshots : [],
        deletedAssets: parsed.deletedAssets && typeof parsed.deletedAssets === "object" ? parsed.deletedAssets : {},
        lastInteraction: parsed.lastInteraction && typeof parsed.lastInteraction === "object" ? parsed.lastInteraction : null,
        lastSeenLocation: parsed.lastSeenLocation || ""
      };
    } catch (_error) {
      return { version: 1, installedAt: Date.now(), events: [], snapshots: [], deletedAssets: {}, lastInteraction: null, lastSeenLocation: "" };
    }
  };
      const writeTracker = (tracker) => {
        try {
          const payload = {
            version: 1,
            installedAt: tracker.installedAt || Date.now(),
            updatedAt: Date.now(),
            events: Array.isArray(tracker.events) ? tracker.events.slice(-40).map(compactStoredEvent) : [],
            snapshots: Array.isArray(tracker.snapshots) ? tracker.snapshots.slice(-6).map(compactStoredSnapshot) : [],
            deletedAssets: compactDeletedAssets(tracker.deletedAssets),
            lastInteraction: tracker.lastInteraction && typeof tracker.lastInteraction === "object" ? tracker.lastInteraction : null,
            lastSeenLocation: locationText
          };
          localStorage.setItem(trackerKey, JSON.stringify(payload));
    } catch (_error) {}
  };
  const bodyPreview = (body) => {
    try {
      if (typeof body === "string") return body.slice(0, 2000);
      if (body instanceof URLSearchParams) return body.toString().slice(0, 2000);
      if (body && typeof body === "object" && !(body instanceof FormData) && !(body instanceof Blob)) {
        return JSON.stringify(body).slice(0, 2000);
      }
    } catch (_error) {}
    return "";
  };
      const idsFromText = (...parts) => {
        const ids = [];
        const seen = new Set();
        const text = parts.filter(Boolean).join(" ");
        for (const match of text.matchAll(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi)) {
      const id = match[0].toLowerCase();
      if (!seen.has(id)) {
        seen.add(id);
        ids.push(id);
      }
        }
        return ids.slice(0, 80);
      };
      const assetText = (asset) => `${asset?.assetId || ""} ${asset?.id || ""} ${asset?.key || ""} ${asset?.previewImageKey || ""} ${JSON.stringify(asset?.auxKeys || {})}`.toLowerCase();
      const assetMatchesIds = (asset, ids) => {
        if (!asset || !ids || !ids.size) return false;
        const haystack = assetText(asset);
        for (const id of ids) {
          if (haystack.includes(String(id || "").toLowerCase())) return true;
        }
        return false;
      };
      const eventAssetsForStorage = (assets, ids, interactionAsset) => {
        const idSet = new Set((Array.isArray(ids) ? ids : []).map((id) => String(id || "").toLowerCase()).filter(Boolean));
        const selected = [];
        const seen = new Set();
        const addAsset = (asset) => {
          const compact = compactAssets([asset])[0];
          if (!compact || !compact.assetId || seen.has(compact.assetId)) return;
          seen.add(compact.assetId);
          selected.push(compact);
        };
        if (interactionAsset) addAsset(interactionAsset);
        for (const asset of Array.isArray(assets) ? assets : []) {
          if (selected.length >= 80) break;
          if (idSet.size && !assetMatchesIds(asset, idSet)) continue;
          addAsset(asset);
        }
        return selected;
      };
      const compactStoredEvent = (event) => {
        if (!event || typeof event !== "object") return {};
        const bodyText = String(event.bodyText || event.body || "").slice(0, 2000);
        const interactionAsset = event.interactionAsset && typeof event.interactionAsset === "object"
          ? compactAssets([event.interactionAsset])[0] || null
          : null;
        const ids = Array.isArray(event.ids) && event.ids.length
          ? event.ids.map((id) => String(id || "").toLowerCase()).filter(Boolean).slice(0, 80)
          : idsFromText(event.url, bodyText, interactionAsset?.assetId || "", interactionAsset?.key || "", interactionAsset?.previewImageKey || "");
        return {
          at: Number(event.at || Date.now()),
          location: String(event.location || locationText),
          url: String(event.url || ""),
          method: String(event.method || ""),
          status: Number(event.status || 0),
          bodyText,
          ids,
          interactionAsset,
          beforeAssets: eventAssetsForStorage(event.beforeAssets, ids, interactionAsset)
        };
      };
      const compactStoredSnapshot = (snapshot) => ({
        at: Number(snapshot?.at || Date.now()),
        location: String(snapshot?.location || locationText),
        assetCount: Number(snapshot?.assetCount || 0),
        assetIds: Array.isArray(snapshot?.assetIds) ? snapshot.assetIds.slice(0, 160) : [],
        assets: compactAssets(Array.isArray(snapshot?.assets) ? snapshot.assets : []).slice(0, 24)
      });
      const compactDeletedAssets = (deletedAssets) => {
        const compacted = {};
        if (!deletedAssets || typeof deletedAssets !== "object") return compacted;
        for (const asset of Object.values(deletedAssets).slice(-120)) {
          const compact = compactAssets([asset])[0];
          if (!compact || !compact.assetId) continue;
          compacted[compact.assetId] = {
            ...compact,
            _grokFilesTrackedDeleted: true,
            _grokFilesDeleteEventAt: asset._grokFilesDeleteEventAt || 0,
            _grokFilesDeleteEventUrl: asset._grokFilesDeleteEventUrl || "",
            _grokFilesDeleteEventStatus: asset._grokFilesDeleteEventStatus || 0
          };
        }
        return compacted;
      };
      const shouldTrackDelete = (url, method, bodyText) => {
        const normalizedUrl = String(url || "");
        const normalizedMethod = String(method || "GET").toUpperCase();
    const haystack = `${normalizedUrl} ${bodyText || ""}`.toLowerCase();
    if (!normalizedUrl.includes("/rest/")) return false;
    if (normalizedMethod === "DELETE") return true;
    if (!/(delete|trash|remove|archive|unlike|unsave)/i.test(haystack)) return false;
    return /(asset|assets|file|files|media|canvas|conversation)/i.test(haystack);
  };
  const isUuid = (value) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(value || ""));
  const idsFromElement = (target) => {
    const parts = [];
    let el = target && target.nodeType === 1 ? target : target?.parentElement;
    for (let depth = 0; el && depth < 10; depth += 1, el = el.parentElement) {
      for (const attr of ["src", "href", "poster", "data-src", "data-url", "aria-label", "title"]) {
        try {
          const value = attr === "src" && el.currentSrc ? el.currentSrc : el.getAttribute?.(attr);
          if (value) parts.push(value);
        } catch (_error) {}
      }
      const text = String(el.textContent || "").slice(0, 200);
      if (text) parts.push(text);
    }
    return idsFromText(...parts);
  };
  const assetFromFiberTarget = (target) => {
    let el = target && target.nodeType === 1 ? target : target?.parentElement;
    for (let depth = 0; el && depth < 10; depth += 1, el = el.parentElement) {
      const stack = fiberValues(el);
      const seenObjects = new Set();
      let visited = 0;
      while (stack.length && visited < 4000) {
        const current = stack.pop();
        if (!current || typeof current !== "object" || seenObjects.has(current)) continue;
        seenObjects.add(current);
        visited += 1;
        if (Array.isArray(current)) {
          for (const child of current.slice(0, 300)) {
            if (child && typeof child === "object") stack.push(child);
          }
          continue;
        }
        const copied = copyAsset(current);
        if (
          copied
          && isUuid(copied.assetId)
          && (copied.fileSource || copied.key || copied.mimeType)
        ) {
          return copied;
        }
        for (const [, child] of safeEntries(current)) {
          if (child && typeof child === "object") stack.push(child);
        }
      }
    }
    return null;
  };
  const interactionAssetFromEvent = (event) => {
    const ids = idsFromElement(event.target || null);
    let asset = assetFromFiberTarget(event.target || null);
    if (!asset && ids.length) {
      const assets = collectAssets().assets;
      asset = assets.find((candidate) => {
        const assetId = String(candidate.assetId || "").toLowerCase();
        const haystack = `${candidate.key || ""} ${candidate.previewImageKey || ""} ${JSON.stringify(candidate.auxKeys || {})}`.toLowerCase();
        return ids.some((id) => assetId === id || haystack.includes(id));
      }) || null;
    }
    if (!asset || !isUuid(asset.assetId)) return null;
    const compact = compactAssets([asset])[0];
    return compact || null;
  };
  const rememberInteraction = (event) => {
    const asset = interactionAssetFromEvent(event);
    if (!asset) return;
    const tracker = readTracker();
    tracker.lastInteraction = {
      at: Date.now(),
      location: locationText,
      asset,
      ids: idsFromText(asset.assetId, asset.key, asset.previewImageKey, JSON.stringify(asset.auxKeys || {}))
    };
    writeTracker(tracker);
      };
      const rememberDeleteEvent = (event) => {
        const tracker = readTracker();
        const bodyText = String(event.bodyText || "");
        const recent = tracker.lastInteraction && typeof tracker.lastInteraction === "object"
          && Date.now() - Number(tracker.lastInteraction.at || 0) < 20000
          ? tracker.lastInteraction
          : null;
    const interactionAsset = recent && recent.asset && typeof recent.asset === "object" ? recent.asset : null;
    const ids = idsFromText(
      event.url,
      bodyText,
          interactionAsset ? interactionAsset.assetId : "",
          interactionAsset ? interactionAsset.key : "",
          interactionAsset ? interactionAsset.previewImageKey : ""
        );
        const beforeAssets = eventAssetsForStorage(event.beforeAssets || collectAssets().assets, ids, interactionAsset);
        tracker.events.push({
          at: Date.now(),
          location: locationText,
      url: String(event.url || ""),
      method: String(event.method || ""),
      status: Number(event.status || 0),
      bodyText: bodyText.slice(0, 2000),
      ids,
      interactionAsset,
      beforeAssets
    });
    writeTracker(tracker);
  };
  const installTracker = () => {
    if (!window.__grokStudioFilesDeleteTrackerInstalled) {
      const originalFetch = window.fetch;
      if (typeof originalFetch === "function") {
        window.fetch = async (...args) => {
          const input = args[0];
          const init = args[1] || {};
          const url = typeof input === "string" ? input : String((input && input.url) || "");
          const method = String(init.method || (input && input.method) || "GET").toUpperCase();
          const rawBody = init.body !== undefined ? init.body : (input && input.body);
          const bodyText = bodyPreview(rawBody);
          const track = shouldTrackDelete(url, method, bodyText);
          const beforeAssets = track ? collectAssets().assets : [];
          const response = await originalFetch.apply(this, args);
          if (track) {
            rememberDeleteEvent({ url, method, status: response.status, bodyText, beforeAssets });
          }
          return response;
        };
      }
      if (window.XMLHttpRequest && window.XMLHttpRequest.prototype) {
        const xhrOpen = window.XMLHttpRequest.prototype.open;
        const xhrSend = window.XMLHttpRequest.prototype.send;
        window.XMLHttpRequest.prototype.open = function(method, url, ...rest) {
          this.__grokStudioFilesRequest = { method: String(method || "GET").toUpperCase(), url: String(url || "") };
          return xhrOpen.call(this, method, url, ...rest);
        };
        window.XMLHttpRequest.prototype.send = function(body) {
          const request = this.__grokStudioFilesRequest || {};
          const bodyText = bodyPreview(body);
          const track = shouldTrackDelete(request.url, request.method, bodyText);
          const beforeAssets = track ? collectAssets().assets : [];
          if (track) {
            this.addEventListener("loadend", () => {
              rememberDeleteEvent({
                url: request.url,
                method: request.method,
                status: this.status || 0,
                bodyText,
                beforeAssets
              });
            });
          }
          return xhrSend.call(this, body);
        };
      }
      document.addEventListener("pointerdown", rememberInteraction, true);
      document.addEventListener("click", rememberInteraction, true);
      window.__grokStudioFilesDeleteTrackerInstalled = true;
    }
  };
  installTracker();
  const warm = await warmFilesPage();
  const current = collectAssets();
  const mergedCurrentAssets = new Map();
  for (const asset of [...(Array.isArray(warm.assets) ? warm.assets : []), ...current.assets]) {
    if (asset && asset.assetId && !mergedCurrentAssets.has(asset.assetId)) {
      mergedCurrentAssets.set(asset.assetId, asset);
    }
  }
  const currentAssets = Array.from(mergedCurrentAssets.values()).slice(0, maxAssets);
  const currentIds = new Set(currentAssets.map((asset) => asset.assetId).filter(Boolean));
  const tracker = readTracker();
      const deletedAssets = tracker.deletedAssets && typeof tracker.deletedAssets === "object" ? tracker.deletedAssets : {};
      for (const event of tracker.events || []) {
        if (!event || typeof event !== "object") continue;
        const storedEvent = compactStoredEvent(event);
        const beforeAssets = Array.isArray(storedEvent.beforeAssets) ? storedEvent.beforeAssets : [];
        const eventIds = new Set(Array.isArray(storedEvent.ids) ? storedEvent.ids.map((id) => String(id || "").toLowerCase()) : []);
        const interactionAsset = storedEvent.interactionAsset && typeof storedEvent.interactionAsset === "object" ? storedEvent.interactionAsset : null;
        const candidates = interactionAsset ? [interactionAsset, ...beforeAssets] : beforeAssets;
        const seenCandidateIds = new Set();
        for (const beforeAsset of candidates) {
      if (!beforeAsset || typeof beforeAsset !== "object") continue;
          const assetId = String(beforeAsset.assetId || beforeAsset.id || "").trim();
          if (!assetId || seenCandidateIds.has(assetId)) continue;
          seenCandidateIds.add(assetId);
          const source = `${storedEvent.url || ""} ${storedEvent.bodyText || ""}`;
          const matchedById = eventIds.has(assetId.toLowerCase()) || source.includes(assetId);
          const matchedByInteraction = Boolean(interactionAsset && String(interactionAsset.assetId || "") === assetId);
          if (!matchedById && !matchedByInteraction && currentIds.has(assetId)) continue;
      if (eventIds.size && !eventIds.has(assetId.toLowerCase())) {
        if (!source.includes(assetId) && !matchedByInteraction) continue;
      }
      deletedAssets[assetId] = {
        ...beforeAsset,
        assetId,
            id: assetId,
            _grokFilesPage: true,
            _grokFilesTrackedDeleted: true,
            _grokFilesDeleteEventAt: storedEvent.at || 0,
            _grokFilesDeleteEventUrl: storedEvent.url || "",
            _grokFilesDeleteEventStatus: storedEvent.status || 0
          };
        }
      }
  tracker.deletedAssets = deletedAssets;
      tracker.snapshots.push({
        at: Date.now(),
        location: locationText,
        assetCount: currentAssets.length,
        assetIds: currentAssets.map((asset) => asset.assetId).filter(Boolean).slice(0, 160),
        assets: compactAssets(currentAssets).slice(0, 24)
      });
  writeTracker(tracker);
  return {
    location: locationText,
    visited: current.visited,
    scrollRounds: warm.rounds || 0,
    scrollMoved: Boolean(warm.moved),
    scrollContainerCount: warm.containerCount || 0,
    asset_count: currentAssets.length,
    tracked_deleted_count: Object.keys(deletedAssets).length,
    trackerInstalled: Boolean(window.__grokStudioFilesDeleteTrackerInstalled),
    assets: currentAssets,
    trackedAssets: Object.values(deletedAssets)
  };
})()
""".replace("__ASSET_LIMIT__", json.dumps(asset_limit))
        def evaluate_files_page() -> dict[str, Any]:
            target = wait_for_imagine_files_cdp_target(IMAGINE_DEBUG_PORT, timeout=8)
            value = cdp_evaluate(expression, timeout=45, target=target)
            return value if isinstance(value, dict) else {"error": "invalid-result"}

        try:
            result = evaluate_files_page()
        except StudioError as exc:
            self.write_imagine_media_debug("files_page_asset_scan_skipped", {"error": exc.message[:240]})
            return [], {"error": exc.message[:240]}
        if not isinstance(result, dict):
            return [], {"error": "invalid-result"}
        raw_assets = result.get("assets") if isinstance(result.get("assets"), list) else []
        tracked_assets: list[Any] = []
        assets: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw_asset in [*tracked_assets, *raw_assets]:
            if not isinstance(raw_asset, dict):
                continue
            asset_id = str(raw_asset.get("assetId") or raw_asset.get("id") or "").strip()
            if not asset_id or asset_id in seen:
                continue
            seen.add(asset_id)
            assets.append(raw_asset)

        def files_asset_sort_key(asset: dict[str, Any]) -> tuple[int, int, dt.datetime]:
            tracked = bool(asset.get("_grokFilesTrackedDeleted"))
            try:
                event_at = int(asset.get("_grokFilesDeleteEventAt") or 0)
            except (TypeError, ValueError):
                event_at = 0
            created = parse_time(asset.get("createTime")) or dt.datetime.max.replace(tzinfo=dt.timezone.utc)
            return (0 if tracked else 1, -event_at, created)

        assets.sort(key=files_asset_sort_key)
        info = {
            "location": str(result.get("location") or ""),
            "visited": int(result.get("visited") or 0),
            "scroll_rounds": int(result.get("scrollRounds") or 0),
            "scroll_moved": bool(result.get("scrollMoved")),
            "scroll_container_count": int(result.get("scrollContainerCount") or 0),
            "asset_count": len(assets),
            "current_asset_count": len(raw_assets),
            "tracked_deleted_count": 0,
            "tracker_installed": bool(result.get("trackerInstalled")),
            "skipped": str(result.get("skipped") or ""),
        }
        return assets, info

    def hydrate_imagine_tracked_deleted_assets(
        self,
        assets: list[dict[str, Any]],
        session: dict[str, Any],
        limit: int = 80,
    ) -> tuple[list[dict[str, Any]], int]:
        hydrated: list[dict[str, Any]] = []
        hydrated_count = 0
        checked = 0
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            if not asset.get("_grokFilesTrackedDeleted"):
                hydrated.append(asset)
                continue
            if checked >= limit or self.imagine_asset_media_url(asset, self.imagine_asset_kind(asset)):
                hydrated.append(asset)
                continue
            checked += 1
            asset_id = str(asset.get("assetId") or asset.get("id") or "").strip()
            if not asset_id:
                hydrated.append(asset)
                continue
            path = "/rest/assets/" + urllib.parse.quote(asset_id, safe="")
            payload: dict[str, Any] = {}
            try:
                payload = self.imagine_browser_get_json(path, timeout=8)
            except StudioError:
                try:
                    payload = self.imagine_get_json(path, session=session, timeout=8)
                except StudioError:
                    payload = {}
            records = self.extract_imagine_asset_records(payload, 1) if payload else []
            if not records:
                hydrated.append(asset)
                continue
            merged = dict(records[0])
            merged["assetId"] = str(merged.get("assetId") or merged.get("id") or asset_id)
            merged["id"] = str(merged.get("id") or merged.get("assetId") or asset_id)
            for key, value in asset.items():
                if key.startswith("_grokFiles"):
                    merged[key] = value
            merged["_grokFilesPage"] = True
            hydrated.append(merged)
            hydrated_count += 1
        if hydrated_count:
            self.write_imagine_media_debug(
                "files_page_tracked_hydrated",
                {"hydrated_count": hydrated_count, "checked_count": checked, "limit": limit},
            )
        return hydrated, hydrated_count

    def imagine_files_asset_conversation_id(self, asset: dict[str, Any]) -> str:
        for key in ("sourceConversationId", "rootAssetSourceConversationId", "currentConversationId", "conversationId"):
            value = str(asset.get(key) or "").strip()
            if value:
                return value
        return ""

    def imagine_asset_prompt_surrogate_status(self, asset: dict[str, Any]) -> str:
        for path, value in prompt_like_text_values(asset, max_depth=4):
            if prompt_surrogate_from_text(value):
                clean_path = re.sub(r"[^A-Za-z0-9_.\\[\\]-]+", "-", path)[:80] or "prompt"
                return f"files-numeric-prompt:{clean_path}"
        return ""

    def imagine_conversation_asset_status(self, asset: dict[str, Any], session: dict[str, Any]) -> str:
        conversation_id = self.imagine_files_asset_conversation_id(asset)
        if not conversation_id:
            return ""
        conversation_path = "/rest/app-chat/conversations/" + urllib.parse.quote(conversation_id, safe="")
        try:
            conversation = self.imagine_get_json(conversation_path, session=session, timeout=6)
        except StudioError as exc:
            if exc.status == 404 and "not found" in exc.message.lower():
                return "files-conversation-missing"
            return ""
        for _path, value in prompt_like_text_values(conversation, max_depth=2):
            if prompt_surrogate_from_text(value):
                return "files-numeric-prompt:conversation"
        response_id = str(asset.get("responseId") or "").strip()
        if not response_id:
            return ""
        responses_path = conversation_path + "/responses"
        try:
            responses_payload = self.imagine_get_json(responses_path, session=session, timeout=6)
        except StudioError:
            return ""
        responses = responses_payload.get("responses") if isinstance(responses_payload.get("responses"), list) else []
        for response in responses:
            if not isinstance(response, dict):
                continue
            if str(response.get("responseId") or "") != response_id:
                continue
            for _path, value in prompt_like_text_values(response, max_depth=3):
                if prompt_surrogate_from_text(value):
                    return "files-numeric-prompt:response"
        return ""

    def classify_imagine_files_page_deleted_assets(
        self,
        assets: list[dict[str, Any]],
        session: dict[str, Any],
        account: dict[str, Any],
        scan_limit: int,
        target_deleted_count: int = 0,
    ) -> dict[str, str]:
        statuses: dict[str, str] = {}
        candidates: list[dict[str, Any]] = []
        generated_count = 0
        account_filtered = 0
        cache = self.read_imagine_deleted_conversation_cache()
        cache_dirty = False
        cache_positive_hits = 0
        cache_negative_hits = 0
        cache_expired_or_miss = 0
        for asset in assets:
            if not isinstance(asset, dict) or not asset.get("_grokFilesPage"):
                continue
            asset_id = str(asset.get("assetId") or asset.get("id") or "").strip()
            if not asset_id:
                continue
            if str(asset.get("fileSource") or "") != "IMAGINE_GENERATED_FILE_SOURCE":
                continue
            generated_count += 1
            kind = self.imagine_asset_kind(asset)
            if kind not in {"image", "video"}:
                continue
            if not self.imagine_asset_matches_account(asset, account):
                account_filtered += 1
                continue
            prompt_status = self.imagine_asset_prompt_surrogate_status(asset)
            if prompt_status:
                statuses[asset_id] = prompt_status
                continue
            if self.imagine_files_asset_conversation_id(asset):
                cached_status = self.imagine_deleted_cached_conversation_status(cache, asset, account)
                if cached_status is not None:
                    if cached_status:
                        statuses[asset_id] = cached_status
                        cache_positive_hits += 1
                    else:
                        cache_negative_hits += 1
                    continue
                cache_expired_or_miss += 1
                candidates.append(asset)

        check_limit = max(40, min(max(scan_limit, 1), 720))
        target_deleted_count = max(0, int(target_deleted_count or 0))
        if target_deleted_count:
            needed = max(0, target_deleted_count - len(statuses))
            if needed <= 0:
                candidates = []
            else:
                check_limit = min(check_limit, max(needed * 2, needed + 40))
                candidates = candidates[:check_limit]
        else:
            candidates = candidates[:check_limit]
        checked = 0
        conversation_deleted = 0

        def check_asset(asset: dict[str, Any]) -> tuple[str, str]:
            asset_id = str(asset.get("assetId") or asset.get("id") or "").strip()
            if not asset_id:
                return "", ""
            return asset_id, self.imagine_conversation_asset_status(asset, session)

        if candidates:
            batch_size = min(80, max(24, (target_deleted_count or 40) * 2))
            for offset in range(0, len(candidates), batch_size):
                batch = candidates[offset: offset + batch_size]
                max_workers = min(16, max(1, len(batch)))
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_map = {executor.submit(check_asset, asset): asset for asset in batch}
                    for future in concurrent.futures.as_completed(future_map):
                        checked += 1
                        asset = future_map[future]
                        status = ""
                        asset_id = ""
                        try:
                            asset_id, status = future.result()
                        except Exception as exc:
                            log_event(f"Imagine files conversation check skipped: {exc}")
                        if asset_id:
                            self.remember_imagine_deleted_conversation_status(cache, asset, account, status)
                            cache_dirty = True
                        if asset_id and status:
                            statuses[asset_id] = status
                            if status == "files-conversation-missing":
                                conversation_deleted += 1
                    if target_deleted_count and len(statuses) >= target_deleted_count:
                        break

        if cache_dirty:
            self.write_imagine_deleted_conversation_cache(cache)

        self.write_imagine_media_debug(
            "files_page_deleted_classification",
            {
                "files_page_asset_count": len(assets),
                "generated_count": generated_count,
                "account_filtered_count": account_filtered,
                "candidate_count": len(candidates),
                "checked_count": checked,
                "deleted_count": len(statuses),
                "conversation_deleted_count": conversation_deleted,
                "check_limit": check_limit,
                "target_deleted_count": target_deleted_count,
                "cache_positive_hit_count": cache_positive_hits,
                "cache_negative_hit_count": cache_negative_hits,
                "cache_miss_count": cache_expired_or_miss,
            },
        )
        return statuses

    def imagine_asset_deleted_status(self, asset: dict[str, Any]) -> tuple[bool, str]:
        deleted_bool_keys = {
            "isdeleted",
            "deleted",
            "istrashed",
            "trashed",
            "isremoved",
            "removed",
            "isarchived",
            "archived",
        }
        deleted_time_keys = {
            "deletedat",
            "deletetime",
            "deletiontime",
            "trashedat",
            "removedat",
            "archivedat",
        }
        status_keys = {
            "status",
            "state",
            "lifecycle",
            "lifecyclestate",
            "visibility",
            "availability",
            "availabilitystatus",
            "inlinestatus",
        }
        deleted_terms = ("delete", "deleted", "trash", "trashed", "remove", "removed", "archive", "archived")

        def visit(value: Any, depth: int = 0) -> tuple[bool, str]:
            if depth > 4:
                return False, ""
            if isinstance(value, dict):
                for key, child in value.items():
                    key_text = str(key or "").strip()
                    key_norm = re.sub(r"[^a-z0-9]", "", key_text.lower())
                    if key_norm in deleted_bool_keys and child is True:
                        return True, key_text
                    if key_norm in deleted_time_keys and str(child or "").strip():
                        return True, key_text
                    if key_norm in status_keys:
                        status = str(child or "").strip()
                        if status and any(term in status.lower() for term in deleted_terms):
                            return True, status
                    if isinstance(child, (dict, list)):
                        found, reason = visit(child, depth + 1)
                        if found:
                            return found, reason
            elif isinstance(value, list):
                for child in value:
                    if isinstance(child, (dict, list)):
                        found, reason = visit(child, depth + 1)
                        if found:
                            return found, reason
            return False, ""

        return visit(asset)

    def imagine_asset_matches_account(self, asset: dict[str, Any], account: dict[str, Any]) -> bool:
        url = self.imagine_asset_media_url(asset)
        if url and media_url_matches_account(url, account):
            return True
        account_values = {
            normalize_identity_text(account.get("id")),
            normalize_identity_text(account.get("email")),
            normalize_identity_text(account.get("label")),
        }
        for value in account.get("identity_values") or []:
            normalized = normalize_identity_text(value)
            if normalized:
                account_values.add(normalized)
        account_values = {value for value in account_values if value}
        asset_values = imagine_post_identity_values(asset)
        if account_values and asset_values:
            return bool(account_values.intersection(asset_values))
        return not asset_values

    def imagine_asset_created_at(self, asset: dict[str, Any]) -> str:
        for key in ("createTime", "createdAt", "created_at", "lastUseTime", "modifyTime", "updatedAt"):
            value = asset.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, (int, float)) and value > 0:
                seconds = value / 1000 if value > 10_000_000_000 else value
                return dt.datetime.fromtimestamp(seconds, dt.timezone.utc).isoformat().replace("+00:00", "Z")
        return utc_now()

    def imagine_asset_group_context(self, asset: dict[str, Any], asset_id: str) -> tuple[str, str]:
        def clean(value: Any) -> str:
            return str(value or "").strip()

        if asset.get("_grokDeletedAssetIndividual"):
            return asset_id, ""

        response_group_id = clean(asset.get("_grokResponseGroupId"))
        if response_group_id:
            parent_id = clean(asset.get("_grokResponseParentId"))
            return response_group_id, parent_id if parent_id != asset_id else ""

        heuristic_group_id = clean(asset.get("_grokHeuristicGroupId"))
        if heuristic_group_id:
            return heuristic_group_id, clean(asset.get("_grokHeuristicParentId"))

        root_asset_id = clean(asset.get("rootAssetId"))
        group_id = (
            root_asset_id
            or clean(asset.get("rootAssetSourceConversationId"))
            or clean(asset.get("sourceConversationId"))
            or clean(asset.get("currentConversationId"))
            or clean(asset.get("conversationId"))
            or clean(asset.get("responseId"))
            or asset_id
        )
        parent_id = root_asset_id if root_asset_id and root_asset_id != asset_id else ""
        return group_id, parent_id

    def assign_imagine_deleted_asset_heuristic_groups(
        self,
        assets: list[dict[str, Any]],
        deleted_statuses: dict[str, str],
    ) -> int:
        return 0

    def assign_imagine_deleted_asset_response_groups(
        self,
        assets: list[dict[str, Any]],
        deleted_statuses: dict[str, str],
        session: dict[str, Any],
    ) -> int:
        deleted_ids = {
            str(asset_id or "").strip()
            for asset_id in deleted_statuses
            if str(asset_id or "").strip()
        }
        if not assets or not deleted_ids:
            return 0

        def asset_id_for(asset: dict[str, Any]) -> str:
            return str(asset.get("assetId") or asset.get("id") or "").strip()

        def clean(value: Any) -> str:
            return str(value or "").strip()

        by_conversation: dict[str, list[dict[str, Any]]] = {}
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            asset_id = asset_id_for(asset)
            if asset_id not in deleted_ids:
                continue
            conversation_id = self.imagine_files_asset_conversation_id(asset)
            if not conversation_id:
                continue
            by_conversation.setdefault(conversation_id, []).append(asset)
        by_conversation = {
            conversation_id: conversation_assets
            for conversation_id, conversation_assets in by_conversation.items()
            if len(conversation_assets) > 1
        }

        grouped_count = 0
        checked_conversations = 0
        linked_asset_ids: set[str] = set()

        for conversation_id, conversation_assets in by_conversation.items():
            response_ids = {
                clean(asset.get("responseId"))
                for asset in conversation_assets
                if clean(asset.get("responseId"))
            }
            if not response_ids:
                continue
            responses_path = (
                "/rest/app-chat/conversations/"
                + urllib.parse.quote(conversation_id, safe="")
                + "/responses"
            )
            try:
                responses_payload = self.imagine_get_json(responses_path, session=session, timeout=6)
            except StudioError:
                continue
            checked_conversations += 1
            responses = responses_payload.get("responses") if isinstance(responses_payload.get("responses"), list) else []
            if not responses:
                responses = self.extract_media_posts(responses_payload, include_id_only=True)
            response_assets: dict[str, set[str]] = {}
            for response in responses:
                if not isinstance(response, dict):
                    continue
                response_id = clean(response.get("responseId") or response.get("id"))
                if response_id not in response_ids:
                    continue
                ids = {
                    clean(value)
                    for value in walk_asset_identity_values(response)
                    if clean(value)
                }
                if ids:
                    response_assets.setdefault(response_id, set()).update(ids)

            for response_id, known_ids in response_assets.items():
                matched = [
                    asset
                    for asset in conversation_assets
                    if clean(asset.get("responseId")) == response_id
                    and asset_id_for(asset) in known_ids
                ]
                if len(matched) < 2:
                    continue
                group_id = f"files-response:{conversation_id}:{response_id}"
                parent_id = asset_id_for(matched[0])
                for asset in matched:
                    asset["_grokResponseGroupId"] = group_id
                    asset["_grokResponseParentId"] = parent_id
                    linked_asset_ids.add(asset_id_for(asset))
                grouped_count += 1

        if checked_conversations or grouped_count:
            self.write_imagine_media_debug(
                "files_response_groups",
                {
                    "conversation_count": len(by_conversation),
                    "checked_conversation_count": checked_conversations,
                    "group_count": grouped_count,
                    "asset_count": len(linked_asset_ids),
                },
            )
        return grouped_count

    def imagine_remote_item_from_asset(
        self,
        asset: dict[str, Any],
        kind: str,
        url: str,
        account: dict[str, Any],
        deleted_status: str,
    ) -> dict[str, Any]:
        asset_id = str(asset.get("assetId") or asset.get("id") or extract_imagine_post_id_from_url(url) or canonical_media_key(url) or uuid.uuid4().hex)
        title = str(asset.get("name") or asset.get("fileName") or asset.get("title") or asset.get("prompt") or asset_id).strip()
        created_at = self.imagine_asset_created_at(asset)
        remote_deleted = bool(deleted_status)
        item_id = f"imagine-remote:{kind}:asset:{asset_id}"
        group_id, parent_id = self.imagine_asset_group_context(asset, asset_id)
        imagine_meta = compact(
            {
                "remote": True,
                "imported": False,
                "account_id": account.get("id") or "",
                "account_email": account.get("email") or "",
                "account_label": account.get("label") or "",
                "account_folder": account.get("folder") or "",
                "asset_id": asset_id,
                "asset_url": url,
                "media_url": url,
                "media_type": kind,
                "group_id": group_id,
                "parent_asset_id": parent_id,
                "response_id": str(asset.get("responseId") or ""),
                "root_asset_id": str(asset.get("rootAssetId") or ""),
                "source_conversation_id": str(asset.get("sourceConversationId") or ""),
                "root_asset_source_conversation_id": str(asset.get("rootAssetSourceConversationId") or ""),
                "heuristic_group": bool(asset.get("_grokHeuristicGroupId")),
                "heuristic_group_reason": str(asset.get("_grokHeuristicGroupReason") or ""),
            }
        )
        metadata = {
            "group_id": group_id,
            "parent_id": parent_id,
            "model": str(asset.get("modelName") or asset.get("model") or imagine_model_name(kind)),
            "provider": "imagine",
            "source": "imagine-remote",
            "import_source": "imagine-remote",
            "imagine": imagine_meta,
            "imagine_asset_id": asset_id if kind == "image" else None,
            "imagine_asset_url": url if kind == "image" else None,
            "imagine_video_asset_id": asset_id if kind == "video" else None,
            "imagine_video_asset_url": url if kind == "video" else None,
            "remote_created_at": created_at,
            "raw_asset": asset,
        }
        if asset.get("_grokConversationOnly"):
            metadata["conversation_only"] = True
            imagine_meta["conversation_only"] = True
        if asset.get("_grokLocalDeleted"):
            canvas_id = str(asset.get("_grokDeletedCanvasId") or "")
            metadata["local_deleted"] = True
            metadata["deleted_canvas_id"] = canvas_id
            imagine_meta["local_deleted"] = True
            imagine_meta["deleted_canvas_id"] = canvas_id
        if remote_deleted:
            metadata["remote_deleted"] = True
            metadata["is_deleted_remote"] = True
            metadata["remote_deleted_status"] = deleted_status
            imagine_meta["deleted"] = True
            if deleted_status:
                imagine_meta["deleted_status"] = deleted_status
        return {
            "id": item_id,
            "type": kind,
            "mode": "imagine-remote",
            "source": "imagine-remote",
            "title": safe_file_stem(title[:64], f"Imagine {kind.title()}"),
            "prompt": str(asset.get("prompt") or asset.get("originalPrompt") or ""),
            "category": "Imagine",
            "tags": ["Imagine"],
            "created_at": created_at,
            "local_url": imagine_remote_media_proxy_url(url, kind),
            "remote_url": url,
            "file": "",
            "mime": "video/mp4" if kind == "video" else "image/jpeg",
            "request_id": asset_id if kind == "video" else None,
            "metadata": metadata,
        }

    def mark_existing_imagine_remote_deleted(self, asset: dict[str, Any], kind: str, status: str) -> int:
        asset_id = str(asset.get("assetId") or asset.get("id") or "").strip()
        url_key = canonical_media_key(self.imagine_asset_media_url(asset, preferred_kind=kind))
        if not asset_id and not url_key:
            return 0
        data = self.library._read()
        changed = 0
        for item in data.get("items", []):
            if not isinstance(item, dict) or str(item.get("type") or "") != kind:
                continue
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            imagine = metadata.get("imagine") if isinstance(metadata.get("imagine"), dict) else {}
            item_asset_ids = {
                str(value).strip()
                for value in (
                    metadata.get("imagine_asset_id"),
                    metadata.get("imagine_video_asset_id"),
                    imagine.get("asset_id"),
                )
                if isinstance(value, str) and value.strip()
            }
            item_url_keys = {
                canonical_media_key(value)
                for value in (
                    item.get("remote_url"),
                    metadata.get("remote_url"),
                    metadata.get("imagine_asset_url"),
                    metadata.get("imagine_video_asset_url"),
                    metadata.get("imagine_media_url"),
                    metadata.get("imagine_video_media_url"),
                    imagine.get("asset_url"),
                    imagine.get("media_url"),
                )
                if isinstance(value, str) and value.strip()
            }
            matches_asset = bool(asset_id and asset_id in item_asset_ids)
            matches_url = bool(url_key and url_key in item_url_keys)
            if not matches_asset and not matches_url:
                continue
            metadata = dict(metadata)
            imagine = dict(imagine)
            if metadata.get("remote_deleted") and imagine.get("deleted"):
                continue
            metadata["remote_deleted"] = True
            metadata["is_deleted_remote"] = True
            metadata["remote_deleted_status"] = status
            imagine["deleted"] = True
            imagine["deleted_status"] = status
            metadata["imagine"] = imagine
            item["metadata"] = metadata
            item["updated_at"] = utc_now()
            changed += 1
        if changed:
            self.library._write(data)
        return changed

    def expand_imagine_import_posts(
        self,
        posts: list[dict[str, Any]],
        limit: int,
        session: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        expanded: list[dict[str, Any]] = []
        by_id: dict[str, dict[str, Any]] = {}
        queue: list[str] = []

        def add_post(post: dict[str, Any]) -> None:
            post_id = str(post.get("id") or "").strip()
            if post_id:
                if post_id in by_id:
                    by_id[post_id] = {**by_id[post_id], **post}
                else:
                    by_id[post_id] = post
                    expanded.append(post)
                for related_id in imagine_import_source_post_ids(post):
                    if related_id and related_id not in by_id and related_id not in queue:
                        queue.append(related_id)
            elif post not in expanded:
                expanded.append(post)

        for post in posts:
            add_post(post)
        detail_budget = max(8, min(max(limit, 1), 48))
        checked = 0
        while queue and checked < detail_budget:
            post_id = queue.pop(0)
            if post_id in by_id:
                continue
            checked += 1
            try:
                detail = self.get_media_post_direct(post_id, session)
            except StudioError as exc:
                log_event(f"Imagine remote detail skipped {post_id}: {exc.message[:180]}")
                continue
            for post in self.extract_media_posts(detail):
                add_post(post)
        return expanded

    def assign_imagine_import_groups(self, posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_id = {
            str(post.get("id") or ""): post
            for post in posts
            if isinstance(post, dict) and str(post.get("id") or "")
        }
        if not by_id:
            return posts
        parent: dict[str, str] = {post_id: post_id for post_id in by_id}

        def find(post_id: str) -> str:
            while parent.get(post_id, post_id) != post_id:
                parent[post_id] = parent.get(parent[post_id], parent[post_id])
                post_id = parent[post_id]
            return post_id

        def union(left: str, right: str) -> None:
            if left not in parent or right not in parent:
                return
            root_left = find(left)
            root_right = find(right)
            if root_left != root_right:
                parent[root_right] = root_left

        for post in by_id.values():
            post_id = str(post.get("id") or "")
            for related_id in imagine_related_post_ids(post):
                if related_id and related_id != post_id and related_id in by_id:
                    union(post_id, related_id)

        components: dict[str, list[dict[str, Any]]] = {}
        for post_id, post in by_id.items():
            components.setdefault(find(post_id), []).append(post)

        for component in components.values():
            def score(post: dict[str, Any]) -> tuple[int, str, str]:
                media_type = str(post.get("mediaType") or "")
                has_parent = bool(imagine_post_parent_id(post))
                created = imagine_post_created_at(post)
                return (1 if has_parent else 0, "1" if media_type != "MEDIA_POST_TYPE_IMAGE" else "0", created)

            root = sorted(component, key=score)[0]
            group_id = str(root.get("id") or imagine_post_group_id(root))
            for post in component:
                post["_grokImportGroupId"] = group_id
                post["_grokImportParentId"] = imagine_post_parent_id(post)
        return posts

    def imagine_remote_item_from_post(
        self,
        post: dict[str, Any],
        kind: str,
        url: str,
        account: dict[str, str],
    ) -> dict[str, Any]:
        post_id = str(post.get("id") or "")
        prompt = imagine_post_text(post)
        created_at = imagine_post_created_at(post)
        parent_id = imagine_post_parent_id(post)
        group_id = str(post.get("_grokImportGroupId") or imagine_post_group_id(post))
        item_id_source = post_id or canonical_media_key(url) or uuid.uuid4().hex
        item_id = f"imagine-remote:{kind}:{item_id_source}"
        title = safe_file_stem(prompt[:48] or post_id or f"Imagine {kind.title()}", f"Imagine {kind.title()}")
        imagine_meta = {
            "remote": True,
            "imported": False,
            "account_id": account.get("id") or "",
            "account_email": account.get("email") or "",
            "account_label": account.get("label") or "",
            "account_folder": account.get("folder") or "",
            "post_id": post_id,
            "media_url": url,
            "media_type": kind,
            "group_id": group_id,
            "parent_post_id": parent_id or "",
            "original_post_id": str(post.get("originalPostId") or ""),
            "root_post_id": str(post.get("rootPostId") or ""),
        }
        remote_deleted = bool(post.get("_grokDeletedView"))
        remote_deleted_status = str(post.get("_grokListVariant") or "deleted-list") if remote_deleted else ""
        if remote_deleted:
            imagine_meta["deleted"] = True
            imagine_meta["deleted_status"] = remote_deleted_status
        return {
            "id": item_id,
            "type": kind,
            "mode": "imagine-remote",
            "source": "imagine-remote",
            "title": title,
            "prompt": prompt,
            "category": "Imagine",
            "tags": ["Imagine"],
            "created_at": created_at,
            "local_url": imagine_remote_media_proxy_url(url, kind),
            "remote_url": url,
            "file": "",
            "mime": "video/mp4" if kind == "video" else "image/jpeg",
            "request_id": post_id if kind == "video" else None,
            "metadata": {
                "group_id": group_id,
                "parent_id": parent_id,
                "model": imagine_model_name(kind),
                "provider": "imagine",
                "source": "imagine-remote",
                "import_source": "imagine-remote",
                "imagine": imagine_meta,
                "imagine_post_id": post_id if kind == "image" else None,
                "imagine_media_url": url if kind == "image" else None,
                "imagine_video_post_id": post_id if kind == "video" else None,
                "imagine_video_media_url": url if kind == "video" else None,
                "remote_created_at": created_at,
                "remote_deleted": remote_deleted or None,
                "is_deleted_remote": remote_deleted or None,
                "remote_deleted_status": remote_deleted_status or None,
            },
        }

    def imagine_remote_post_candidate_urls(self, post: dict[str, Any]) -> tuple[str, list[str]]:
        media_type = str(post.get("mediaType") or "")
        kind = "video" if media_type == "MEDIA_POST_TYPE_VIDEO" else "image"
        raw_urls: list[str] = []

        def add_url(value: Any) -> None:
            url = normalize_media_api_url(value if isinstance(value, str) else None)
            if isinstance(url, str) and url not in raw_urls:
                raw_urls.append(url)

        if kind == "video":
            for key in ("hd1080MediaUrl", "hdMediaUrl", "mediaUrl"):
                add_url(post.get(key))
            for candidate_kind, url in self.imagine_import_post_candidates(post):
                if candidate_kind == "video":
                    add_url(url)
            raw_urls = [url for url in raw_urls if is_possible_video_url_candidate(url)]
        else:
            for key in ("mediaUrl", "hdMediaUrl", "hd1080MediaUrl", "thumbnailImageUrl", "previewImageUrl", "sourceImageUrl", "imageUrl"):
                add_url(post.get(key))
            for url in self.media_post_image_urls(post):
                add_url(url)
            raw_urls = [url for url in raw_urls if is_possible_image_url_candidate(url)]

        raw_urls.sort(key=lambda url: remote_display_url_score(url, kind), reverse=True)
        return kind, raw_urls

    def imagine_remote_post_candidates_fast(self, post: dict[str, Any]) -> list[tuple[str, str]]:
        kind, raw_urls = self.imagine_remote_post_candidate_urls(post)
        return [(kind, raw_urls[0])] if raw_urls else []

    def imagine_remote_post_candidates(self, post: dict[str, Any], session: dict[str, Any]) -> list[tuple[str, str]]:
        kind, raw_urls = self.imagine_remote_post_candidate_urls(post)
        verified: list[tuple[str, str]] = []
        for url in raw_urls[:8]:
            probe = self.probe_imagine_media_url_detail(url, kind, session)
            if probe.get("ok"):
                verified.append((kind, url))
                break
        return verified

    def imagine_remote_items_from_seed_posts(
        self,
        seed_posts: list[dict[str, Any]],
        seed_ids: set[str],
        session: dict[str, Any],
        account: dict[str, Any],
        limit: int,
        relaxed_account_filter: bool = False,
        verify_candidates: bool = True,
    ) -> dict[str, Any]:
        posts = self.assign_imagine_import_groups(
            self.expand_imagine_import_posts(seed_posts, limit * 4, session)
        )
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        filtered_posts: list[dict[str, Any]] = []
        filtered = 0
        skipped = 0
        for post in posts:
            post_id = str(post.get("id") or "")
            if not relaxed_account_filter and not self.imagine_import_post_matches_account(post, account, allow_seed=post_id in seed_ids):
                filtered += 1
                continue
            filtered_posts.append(post)

        def remote_candidates_for(post: dict[str, Any]) -> list[tuple[str, str]]:
            try:
                if verify_candidates:
                    return self.imagine_remote_post_candidates(post, session)
                return self.imagine_remote_post_candidates_fast(post)
            except Exception as exc:
                log_event(f"Imagine remote candidate lookup skipped: {exc}")
                return []

        max_workers = min(5, max(1, len(filtered_posts)))
        if filtered_posts:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                candidate_lists = list(executor.map(remote_candidates_for, filtered_posts))
        else:
            candidate_lists = []

        for post, candidates in zip(filtered_posts, candidate_lists):
            post_id = str(post.get("id") or "")
            if not candidates:
                skipped += 1
                continue
            for kind, url in candidates:
                key = f"{kind}:{post_id or canonical_media_key(url) or url}"
                if key in seen:
                    continue
                seen.add(key)
                items.append(self.imagine_remote_item_from_post(post, kind, url, account))
                break

        return {
            "items": items,
            "scanned_count": len(posts),
            "remote_count": len(items),
            "filtered_count": filtered,
            "skipped_count": skipped,
        }

    def imagine_discover_items_from_posts(
        self,
        posts: list[dict[str, Any]],
        account: dict[str, Any],
        limit: int,
    ) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        skipped = 0
        for post in posts:
            if not isinstance(post, dict):
                continue
            candidates = self.imagine_import_post_candidates(post)
            if not candidates:
                skipped += 1
                continue
            added = False
            for kind, url in candidates:
                key = f"{kind}:{str(post.get('id') or '') or canonical_media_key(url) or url}"
                if key in seen:
                    continue
                seen.add(key)
                item = self.imagine_remote_item_from_post(post, kind, url, account)
                metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                imagine = metadata.get("imagine") if isinstance(metadata.get("imagine"), dict) else {}
                metadata["remote_view"] = "discover"
                imagine["remote_view"] = "discover"
                metadata["imagine"] = imagine
                item["metadata"] = metadata
                items.append(item)
                added = True
                break
            if not added:
                skipped += 1
            if len(items) >= limit:
                break
        return {
            "items": items,
            "scanned_count": len(posts),
            "remote_count": len(items),
            "filtered_count": 0,
            "skipped_count": skipped,
        }

    def parse_imagine_discover_cursor(self, cursor: str) -> dict[str, str]:
        if not cursor:
            return {}
        try:
            raw = json.loads(cursor)
        except json.JSONDecodeError:
            return {"image": cursor}
        if not isinstance(raw, dict) or raw.get("mode") != "discover":
            return {"image": cursor}
        cursors = raw.get("cursors")
        return {
            str(key): str(value)
            for key, value in (cursors.items() if isinstance(cursors, dict) else [])
            if key in {"image", "video"} and isinstance(value, str) and value
        }

    def list_imagine_discover_remote_library(
        self,
        limit: int,
        session: dict[str, Any],
        account: dict[str, Any],
        cursor: str,
        media_kind: str = "",
    ) -> dict[str, Any]:
        media_kind = media_kind if media_kind in {"image", "video"} else ""
        cursor_state = self.parse_imagine_discover_cursor(cursor)
        video_limit = max(1, limit // 2)
        image_limit = max(1, limit - video_limit)
        common_payload = {"isNsfwEnabled": True, "withContainerOnly": False, "includeCanvas": False}

        def fetch_public_posts(media_type: str, page_limit: int, page_cursor: str) -> tuple[list[dict[str, Any]], str]:
            payload = self.imported_media_posts_page_direct(
                page_limit,
                session,
                page_cursor,
                filter_payload={"source": "MEDIA_POST_SOURCE_PUBLIC", "mediaType": media_type},
                extra_payload=common_payload,
                timeout=12,
            )
            posts = payload.get("posts") if isinstance(payload.get("posts"), list) else []
            return [post for post in posts if isinstance(post, dict)], str(payload.get("nextCursor") or "")

        if media_kind == "image":
            image_posts, next_image_cursor = fetch_public_posts("MEDIA_POST_TYPE_IMAGE", limit, cursor_state.get("image", ""))
            video_posts, next_video_cursor = [], ""
        elif media_kind == "video":
            image_posts, next_image_cursor = [], ""
            video_posts, next_video_cursor = fetch_public_posts("MEDIA_POST_TYPE_VIDEO", limit, cursor_state.get("video", ""))
        else:
            image_posts, next_image_cursor = fetch_public_posts("MEDIA_POST_TYPE_IMAGE", image_limit, cursor_state.get("image", ""))
            video_posts, next_video_cursor = fetch_public_posts("MEDIA_POST_TYPE_VIDEO", video_limit, cursor_state.get("video", ""))
        root_posts: list[dict[str, Any]] = []
        for index in range(max(len(image_posts), len(video_posts))):
            if index < len(image_posts):
                root_posts.append(image_posts[index])
            if index < len(video_posts):
                root_posts.append(video_posts[index])
        root_posts = root_posts[:limit]
        processed = self.imagine_discover_items_from_posts(root_posts, account, limit)
        next_cursors = {
            key: value
            for key, value in (("image", next_image_cursor), ("video", next_video_cursor))
            if value
        }
        next_cursor_text = json.dumps({"mode": "discover", "cursors": next_cursors}, separators=(",", ":")) if next_cursors else ""
        return {
            "ok": True,
            "url": IMAGINE_BASE + "/imagine",
            "view": "discover",
            "discover_type": media_kind or "all",
            "imagine": imagine_session_summary(session),
            "cursor": cursor,
            "next_cursor": next_cursor_text,
            "has_more": bool(next_cursors),
            "root_count": len(root_posts),
            "seed_count": len(root_posts),
            **processed,
        }

    def imagine_deleted_list_variants(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "deleted-source",
                "label": "deleted source",
                "filter": {"source": "MEDIA_POST_SOURCE_DELETED"},
                "trust_deleted": True,
            },
            {
                "id": "trashed-source",
                "label": "trashed source",
                "filter": {"source": "MEDIA_POST_SOURCE_TRASHED"},
                "trust_deleted": True,
            },
            {
                "id": "trash-source",
                "label": "trash source",
                "filter": {"source": "MEDIA_POST_SOURCE_TRASH"},
                "trust_deleted": True,
            },
            {
                "id": "liked-include-deleted",
                "label": "liked includeDeleted",
                "filter": {"source": "MEDIA_POST_SOURCE_LIKED", "includeDeleted": True},
            },
            {
                "id": "liked-deleted-flag",
                "label": "liked deleted flag",
                "filter": {"source": "MEDIA_POST_SOURCE_LIKED", "deleted": True},
            },
        ]

    def parse_imagine_deleted_cursor(self, cursor: str) -> dict[str, str] | None:
        if not cursor:
            return None
        try:
            raw = json.loads(cursor)
        except json.JSONDecodeError:
            return None
        if not isinstance(raw, dict) or raw.get("mode") != "all_files":
            return None
        cursors = raw.get("cursors")
        parsed = {
            str(key): str(value)
            for key, value in (cursors.items() if isinstance(cursors, dict) else [])
            if isinstance(value, str) and value
        }
        return parsed

    def imagine_deleted_seed_candidate(
        self,
        post: dict[str, Any],
        session: dict[str, Any],
        variant: dict[str, Any],
        detail_cache: dict[str, dict[str, Any]],
        detail_limit: int = 8,
    ) -> dict[str, Any] | None:
        post_id = str(post.get("id") or "").strip()
        trust_deleted = bool(variant.get("trust_deleted"))
        root_deleted = imagine_post_has_deleted_hint(post)
        candidate = post
        needs_detail = not imagine_post_has_media_shape(candidate) or (not trust_deleted and not root_deleted)
        if post_id and needs_detail:
            try:
                if post_id not in detail_cache and len(detail_cache) >= detail_limit:
                    return None
                if post_id not in detail_cache:
                    detail_cache[post_id] = self.get_media_post_direct(post_id, session, timeout=5)
                candidate = detail_cache[post_id]
            except StudioError as exc:
                log_event(f"Imagine deleted detail skipped {post_id}: {exc.message[:180]}")
                candidate = post
        if not trust_deleted and not (root_deleted or imagine_post_has_deleted_hint(candidate)):
            return None
        candidate = {**post, **candidate}
        candidate["_grokDeletedView"] = True
        candidate["_grokListVariant"] = str(variant.get("id") or "")
        return candidate

    def scan_current_imagine_deleted_media(
        self,
        session: dict[str, Any],
        account: dict[str, Any],
        limit: int,
    ) -> dict[str, Any]:
        expression = """
(async () => {
  const urls = [];
  const add = (value) => {
    if (!value || typeof value !== "string") return;
    let clean = value.trim();
    if (!clean) return;
    try {
      clean = new URL(clean, location.href).href;
    } catch (_error) {}
    if (/^https?:\\/\\//i.test(clean) && !urls.includes(clean)) urls.push(clean);
  };
  const attrs = ["src", "href", "poster", "data-src", "data-url", "data-media-url", "data-image-url", "data-video-url"];
  document
    .querySelectorAll("img, video, source, a, [src], [href], [poster], [data-src], [data-url], [data-media-url], [data-image-url], [data-video-url]")
    .forEach((el) => {
      if (el.currentSrc) add(el.currentSrc);
      for (const attr of attrs) add(el.getAttribute(attr));
    });
  for (const entry of performance.getEntriesByType("resource")) add(entry.name);
  return {
    title: document.title,
    location: location.href,
    urls: urls.slice(-350),
    at: Date.now()
  };
})()
"""
        try:
            scan = cdp_evaluate(expression, timeout=10)
        except StudioError as exc:
            log_event(f"Imagine deleted page scan skipped: {exc.message[:180]}")
            return {"items": [], "scan_count": 0, "scan_remote_count": 0, "scan_error": exc.message[:240]}
        if not isinstance(scan, dict):
            return {"items": [], "scan_count": 0, "scan_remote_count": 0}

        location = str(scan.get("location") or "")
        allowed_grok_page = (
            location.startswith("https://grok.com/")
            or location.startswith("https://www.grok.com/")
            or location == "https://grok.com"
            or location == "https://www.grok.com"
        )
        if not allowed_grok_page:
            return {"items": [], "scan_count": 0, "scan_remote_count": 0, "scan_location": location}

        candidate_pairs: list[tuple[str, str]] = []
        for kind in ("video", "image"):
            for url in extract_media_urls(scan, kind):
                if not media_url_matches_account(url, account):
                    continue
                if (kind, url) not in candidate_pairs:
                    candidate_pairs.append((kind, url))

        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for kind, url in candidate_pairs[: max(1, min(limit * 2, 24))]:
            key = f"{kind}:{canonical_media_key(url) or url}"
            if key in seen:
                continue
            seen.add(key)
            try:
                probe = self.probe_imagine_media_url_detail(url, kind, session)
            except StudioError as exc:
                log_event(f"Imagine deleted page scan probe skipped: {exc.message[:180]}")
                continue
            if not probe.get("ok"):
                continue
            post_id = extract_imagine_post_id_from_url(url) or extract_imagine_post_id_from_url(location) or canonical_media_key(url) or uuid.uuid4().hex
            post = {
                "id": post_id,
                "mediaType": "MEDIA_POST_TYPE_VIDEO" if kind == "video" else "MEDIA_POST_TYPE_IMAGE",
                "mediaUrl": url,
                "hdMediaUrl": url if kind == "video" else None,
                "thumbnailImageUrl": url if kind == "image" else None,
                "createTime": utc_now(),
                "_grokImportGroupId": post_id,
                "_grokDeletedView": True,
                "_grokScanFallback": True,
            }
            items.append(self.imagine_remote_item_from_post(post, kind, url, account))
            if len(items) >= limit:
                break

        return {
            "items": items,
            "scan_count": len(candidate_pairs),
            "scan_remote_count": len(items),
            "scan_location": location,
        }

    def list_imagine_deleted_asset_remote_library(
        self,
        limit: int,
        session: dict[str, Any],
        account: dict[str, Any],
        scan_limit: int,
        workspace_limit: int,
        include_conversations: bool,
        files_cursor: str = "",
        files_offset: int = 0,
        raw_files: bool = True,
    ) -> dict[str, Any]:
        def asset_match_keys(asset: dict[str, Any]) -> set[str]:
            kind = self.imagine_asset_kind(asset)
            keys: set[str] = set()
            dedupe = self.imagine_asset_dedupe_key(asset, kind)
            if dedupe:
                keys.add(dedupe)
            asset_id = str(asset.get("assetId") or asset.get("id") or "").strip()
            if asset_id:
                keys.add(f"asset:{kind}:{asset_id}" if kind else f"asset:{asset_id}")
            for url in self.imagine_asset_url_candidates(asset):
                url_key = canonical_media_key(url)
                if url_key:
                    keys.add(f"url:{url_key}")
            return keys

        primary_assets: list[dict[str, Any]] = []
        primary_asset_keys: set[str] = set()
        saved_posts_count = 0
        saved_posts_error = ""
        local_deleted_assets: list[dict[str, Any]] = []
        local_deleted_group_count = 0
        local_deleted_asset_id_count = 0
        files_rest_limit = min(max(scan_limit, 160), 720)
        files_rest_assets_all, files_rest_info = self.recent_imagine_files_assets(files_rest_limit, session, files_cursor)
        files_offset = max(0, min(int(files_offset or 0), len(files_rest_assets_all)))
        files_rest_assets = files_rest_assets_all[files_offset:]
        files_page_limit = max(scan_limit, min(1800, max(limit * 24, 720)))
        if files_rest_assets_all or files_cursor or files_offset:
            files_page_assets: list[dict[str, Any]] = []
            files_page_info: dict[str, Any] = {"skipped": "files-rest-primary" if files_rest_assets else "paged-files-cursor"}
        else:
            files_page_assets, files_page_info = self.imagine_files_page_assets(files_page_limit)
        files_page_tracked_hydrated_count = 0
        files_assets = self.merge_imagine_asset_records(files_rest_assets, files_page_assets)
        raw_files_view = raw_files and bool(files_assets)
        save_diff_view = bool(files_assets) and not raw_files_view
        if raw_files_view:
            files_page_deleted_statuses: dict[str, str] = {}
        else:
            saved_scan_limit = min(scan_limit, 80)
            primary_asset_keys, saved_posts_info = self.recent_imagine_saved_keys(saved_scan_limit, session, account)
            saved_posts_count = int(saved_posts_info.get("post_count") or 0)
            saved_posts_error = str(saved_posts_info.get("error") or "")
            if not primary_asset_keys and saved_posts_error:
                raise StudioError("Could not load Imagine saved files for Trash classification: " + saved_posts_error, 502)
            files_page_deleted_statuses = {}
            for asset in files_assets:
                asset_id = str(asset.get("assetId") or asset.get("id") or "").strip()
                if not asset_id:
                    continue
                keys = asset_match_keys(asset)
                if keys and keys.intersection(primary_asset_keys):
                    continue
                files_page_deleted_statuses[asset_id] = "files-save-missing"
            self.write_imagine_media_debug(
                "files_save_diff_classification",
                {
                    "files_asset_count": len(files_assets),
                    "saved_post_count": saved_posts_count,
                    "saved_key_count": len(primary_asset_keys),
                    "deleted_count": len(files_page_deleted_statuses),
                    "error": saved_posts_error,
                },
            )
        files_response_group_count = 0
        files_heuristic_group_count = 0
        assets = [*local_deleted_assets, *files_assets]
        conversation_assets: list[dict[str, Any]] = []
        conversation_only_count = 0
        if include_conversations and not raw_files_view and not save_diff_view:
            conversation_ids: list[str] = []
            for asset in assets:
                for conversation_id in self.imagine_asset_conversation_ids(asset):
                    if conversation_id not in conversation_ids:
                        conversation_ids.append(conversation_id)
            conversation_assets = self.imagine_conversation_assets(
                workspace_limit,
                scan_limit,
                session,
                seed_ids=conversation_ids,
            )
            marked_conversation_assets: list[dict[str, Any]] = []
            for asset in conversation_assets:
                keys = asset_match_keys(asset)
                conversation_only = bool(keys) and not keys.intersection(primary_asset_keys)
                if conversation_only:
                    asset = dict(asset)
                    asset["_grokConversationOnly"] = True
                    conversation_only_count += 1
                marked_conversation_assets.append(asset)
            conversation_assets = marked_conversation_assets
            assets = self.merge_imagine_asset_records(assets, conversation_assets)

        self.write_imagine_media_debug(
            "deleted_asset_scan",
            {
                "asset_count": len(assets),
                "conversation_asset_count": len(conversation_assets),
                "conversation_only_count": conversation_only_count,
                "local_deleted_asset_count": len(local_deleted_assets),
                "local_deleted_asset_id_count": local_deleted_asset_id_count,
                "local_deleted_group_count": local_deleted_group_count,
                "files_page_asset_count": len(files_page_assets),
                "files_rest_asset_count": len(files_rest_assets_all),
                "files_rest_offset": files_offset,
                "files_rest_attempt_count": files_rest_info.get("attempt_count", 0),
                "files_rest_has_more": bool(files_rest_info.get("next_page_token")),
                "files_page_current_asset_count": files_page_info.get("current_asset_count", 0),
                "files_page_tracked_deleted_count": files_page_info.get("tracked_deleted_count", 0),
                "files_page_tracked_hydrated_count": files_page_tracked_hydrated_count,
                "files_page_deleted_count": len(files_page_deleted_statuses),
                "saved_post_count": saved_posts_count,
                "saved_key_count": len(primary_asset_keys),
                "files_response_group_count": files_response_group_count,
                "files_heuristic_group_count": files_heuristic_group_count,
                "files_page_tracker_installed": files_page_info.get("tracker_installed", False),
                "files_page_location": files_page_info.get("location", ""),
                "files_page_skipped": files_page_info.get("skipped", ""),
                "files_page_scroll_rounds": files_page_info.get("scroll_rounds", 0),
                "files_page_scroll_moved": files_page_info.get("scroll_moved", False),
                "files_page_scroll_container_count": files_page_info.get("scroll_container_count", 0),
                "limit": limit,
                "scan_limit": scan_limit,
                "workspace_limit": workspace_limit,
            },
        )

        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        scanned = 0
        skipped = 0
        filtered = 0
        deleted_count = 0
        conversation_only_deleted_count = 0
        local_deleted_count = 0
        files_page_deleted_count = 0
        updated_deleted = 0
        failed = 0
        item_limit = limit
        files_rest_consumed = 0

        for asset in assets:
            if len(items) >= item_limit:
                break
            if asset.get("_grokFilesRest"):
                files_rest_consumed += 1
            scanned += 1
            kind = self.imagine_asset_kind(asset)
            if kind not in {"image", "video"}:
                skipped += 1
                continue
            remote_deleted = False
            remote_deleted_status = ""
            conversation_only = bool(asset.get("_grokConversationOnly"))
            local_deleted = bool(asset.get("_grokLocalDeleted"))
            tracked_deleted = bool(asset.get("_grokFilesTrackedDeleted"))
            asset_id = str(asset.get("assetId") or asset.get("id") or "").strip()
            files_page_status = files_page_deleted_statuses.get(asset_id)
            raw_files_asset = raw_files_view
            save_diff_asset = save_diff_view and bool(asset.get("_grokFilesPage"))
            if not raw_files_view:
                remote_deleted, remote_deleted_status = self.imagine_asset_deleted_status(asset)
                if local_deleted and not remote_deleted:
                    remote_deleted = True
                    remote_deleted_status = "atlas-local-storage"
                if files_page_status and not remote_deleted:
                    remote_deleted = True
                    remote_deleted_status = files_page_status
                if not remote_deleted:
                    filtered += 1
                    continue
                deleted_count += 1
                if local_deleted:
                    local_deleted_count += 1
                if files_page_status:
                    files_page_deleted_count += 1
                if conversation_only:
                    conversation_only_deleted_count += 1
                if not save_diff_asset and not tracked_deleted and not self.imagine_asset_matches_account(asset, account):
                    filtered += 1
                    continue
                if asset.get("_grokFilesPage"):
                    asset["_grokDeletedAssetIndividual"] = True
            url = self.imagine_asset_media_url(asset, preferred_kind=kind)
            if not url:
                skipped += 1
                continue
            if kind == "video" and not is_possible_video_url_candidate(url):
                skipped += 1
                continue
            if kind == "image" and not is_possible_image_url_candidate(url):
                skipped += 1
                continue
            dedupe_key = self.imagine_asset_dedupe_key(asset, kind)
            url_key = canonical_media_key(url)
            item_keys = {
                value
                for value in (
                    f"{kind}:{dedupe_key}" if dedupe_key else "",
                    f"{kind}:url:{url_key}" if url_key else "",
                    f"{kind}:url:{url}" if not url_key else "",
                )
                if value
            }
            if item_keys.intersection(seen):
                continue
            seen.update(item_keys)
            if not raw_files_asset and not save_diff_asset and not (asset.get("_grokFilesRest") and files_page_status):
                try:
                    probe = self.probe_imagine_media_url_detail(url, kind, session)
                except StudioError as exc:
                    failed += 1
                    log_event(f"Imagine deleted asset probe skipped: {exc.message[:180]}")
                    continue
                if not probe.get("ok"):
                    failed += 1
                    if probe.get("error"):
                        log_event(f"Imagine deleted asset probe skipped: {str(probe.get('error'))[:180]}")
                    continue
            if not raw_files_asset and not save_diff_asset:
                updated_deleted += self.mark_existing_imagine_remote_deleted(asset, kind, remote_deleted_status)
            items.append(self.imagine_remote_item_from_asset(asset, kind, url, account, remote_deleted_status))

        next_files_cursor = str(files_rest_info.get("next_page_token") or "")
        next_files_offset = 0
        if files_rest_assets_all:
            absolute_files_consumed = files_offset + files_rest_consumed
            if len(items) >= item_limit and absolute_files_consumed < len(files_rest_assets_all):
                next_files_cursor = files_cursor or "__first__"
                next_files_offset = absolute_files_consumed

        return {
            "items": items,
            "asset_count": len(assets),
            "conversation_asset_count": len(conversation_assets),
            "conversation_only_count": conversation_only_count,
            "local_deleted_asset_count": len(local_deleted_assets),
            "local_deleted_asset_id_count": local_deleted_asset_id_count,
            "local_deleted_group_count": local_deleted_group_count,
            "asset_scanned_count": scanned,
            "asset_deleted_count": deleted_count,
            "conversation_only_deleted_count": conversation_only_deleted_count,
            "local_deleted_count": local_deleted_count,
            "files_page_deleted_count": files_page_deleted_count,
            "saved_post_count": saved_posts_count,
            "saved_key_count": len(primary_asset_keys),
            "files_page_tracked_deleted_count": files_page_info.get("tracked_deleted_count", 0),
            "files_page_tracked_hydrated_count": files_page_tracked_hydrated_count,
            "files_page_tracker_installed": files_page_info.get("tracker_installed", False),
            "files_response_group_count": files_response_group_count,
            "files_heuristic_group_count": files_heuristic_group_count,
            "files_rest_asset_count": len(files_rest_assets_all),
            "files_rest_offset": files_offset,
            "files_rest_attempt_count": files_rest_info.get("attempt_count", 0),
            "next_files_cursor": next_files_cursor,
            "next_files_offset": next_files_offset,
            "files_page_scroll_rounds": files_page_info.get("scroll_rounds", 0),
            "files_page_scroll_moved": files_page_info.get("scroll_moved", False),
            "files_page_scroll_container_count": files_page_info.get("scroll_container_count", 0),
            "asset_filtered_count": filtered,
            "asset_skipped_count": skipped,
            "asset_failed_count": failed,
            "updated_deleted_count": updated_deleted,
            "remote_count": len(items),
            "files_view_mode": "raw" if raw_files_view else ("save-diff" if save_diff_view else "all_files"),
        }

    def list_imagine_deleted_remote_library(
        self,
        limit: int,
        session: dict[str, Any],
        account: dict[str, Any],
        cursor: str,
        scan_limit: int,
        workspace_limit: int,
        include_conversations: bool,
        raw_files: bool = True,
    ) -> dict[str, Any]:
        cursor_state = self.parse_imagine_deleted_cursor(cursor)
        files_cursor_value = cursor_state.get("_files", "") if cursor_state is not None else ""
        files_cursor = "" if files_cursor_value == "__first__" else files_cursor_value
        try:
            files_offset = int(cursor_state.get("_files_offset", "0")) if cursor_state is not None else 0
        except (TypeError, ValueError):
            files_offset = 0
        variants = [] if raw_files else self.imagine_deleted_list_variants()
        root_posts: list[dict[str, Any]] = []
        seed_posts: list[dict[str, Any]] = []
        seed_ids: set[str] = set()
        next_cursors: dict[str, str] = {}
        attempts: list[dict[str, Any]] = []
        errors: list[str] = []
        detail_cache: dict[str, dict[str, Any]] = {}
        deleted_limit = max(1, min(limit, 12))
        skip_deleted_variants = raw_files or cursor_state is None or any(key.startswith("_files") for key in cursor_state)
        for variant in variants:
            if skip_deleted_variants:
                break
            variant_id = str(variant.get("id") or "")
            if cursor_state is not None and variant_id not in cursor_state:
                continue
            variant_cursor = cursor_state.get(variant_id, "") if cursor_state is not None else ""
            try:
                posts_payload = self.imported_media_posts_page_direct(
                    deleted_limit,
                    session,
                    variant_cursor,
                    filter_payload=variant.get("filter") if isinstance(variant.get("filter"), dict) else {},
                    extra_payload=variant.get("extra") if isinstance(variant.get("extra"), dict) else None,
                    timeout=6,
                )
            except StudioError as exc:
                errors.append(f"{variant_id}: {exc.message[:240]}")
                attempts.append({"id": variant_id, "ok": False, "error": exc.message[:240]})
                log_event(f"Imagine deleted filter skipped {variant_id}: {exc.message[:180]}")
                continue
            raw_posts = posts_payload.get("posts") if isinstance(posts_payload.get("posts"), list) else []
            root_posts.extend(post for post in raw_posts if isinstance(post, dict))
            next_cursor = str(posts_payload.get("nextCursor") or "")
            if next_cursor:
                next_cursors[variant_id] = next_cursor
            extracted = self.extract_media_posts({"posts": raw_posts}, include_id_only=True)
            accepted = 0
            for post in extracted:
                if len(seed_posts) >= limit:
                    break
                candidate = self.imagine_deleted_seed_candidate(post, session, variant, detail_cache)
                if not candidate:
                    continue
                if not self.imagine_import_post_matches_account(candidate, account, allow_seed=False):
                    continue
                seed_posts.append(candidate)
                accepted += 1
                post_id = str(candidate.get("id") or "")
                if post_id:
                    seed_ids.add(post_id)
            attempts.append(
                {
                    "id": variant_id,
                    "ok": True,
                    "root_count": len(raw_posts),
                    "seed_count": len(extracted),
                    "accepted_count": accepted,
                    "has_more": bool(next_cursor),
                }
            )

        if errors and not any(attempt.get("ok") for attempt in attempts):
            log_event("Imagine deleted filters returned no usable response: " + "; ".join(errors[-3:]))

        deduped_seed_posts: list[dict[str, Any]] = []
        seen_seed_ids: set[str] = set()
        for post in seed_posts:
            post_id = str(post.get("id") or "")
            key = post_id or json.dumps(post, sort_keys=True, ensure_ascii=False)[:200]
            if key in seen_seed_ids:
                continue
            seen_seed_ids.add(key)
            deduped_seed_posts.append(post)

        processed = self.imagine_remote_items_from_seed_posts(
            deduped_seed_posts,
            seed_ids,
            session,
            account,
            limit,
        )
        asset_result: dict[str, Any] = {
            "items": [],
            "asset_count": 0,
            "conversation_asset_count": 0,
            "conversation_only_count": 0,
            "local_deleted_asset_count": 0,
            "local_deleted_asset_id_count": 0,
            "local_deleted_group_count": 0,
            "files_page_deleted_count": 0,
            "files_page_tracked_deleted_count": 0,
            "files_page_tracked_hydrated_count": 0,
            "files_page_tracker_installed": False,
            "files_response_group_count": 0,
            "files_heuristic_group_count": 0,
            "files_rest_asset_count": 0,
            "files_rest_offset": 0,
            "files_rest_attempt_count": 0,
            "next_files_cursor": "",
            "next_files_offset": 0,
            "files_page_scroll_rounds": 0,
            "files_page_scroll_moved": False,
            "files_page_scroll_container_count": 0,
            "asset_scanned_count": 0,
            "asset_deleted_count": 0,
            "conversation_only_deleted_count": 0,
            "local_deleted_count": 0,
            "asset_filtered_count": 0,
            "asset_skipped_count": 0,
            "asset_failed_count": 0,
            "updated_deleted_count": 0,
            "remote_count": 0,
        }
        scan_result: dict[str, Any] = {"items": [], "scan_count": 0, "scan_remote_count": 0}
        next_cursor_text = ""
        if not processed.get("remote_count"):
            try:
                asset_result = self.list_imagine_deleted_asset_remote_library(
                    limit,
                    session,
                    account,
                    scan_limit,
                    workspace_limit,
                    include_conversations,
                    files_cursor,
                    files_offset,
                    raw_files,
                )
            except StudioError as exc:
                log_event(f"Imagine deleted asset scan skipped: {exc.message[:180]}")
                asset_result["asset_error"] = exc.message[:240]
            asset_items = asset_result.get("items") if isinstance(asset_result.get("items"), list) else []
            if asset_items:
                processed["items"] = asset_items
                processed["remote_count"] = len(asset_items)
                processed["skipped_count"] = 0
        if asset_result.get("next_files_cursor"):
            next_cursors["_files"] = str(asset_result.get("next_files_cursor") or "")
            next_files_offset = int(asset_result.get("next_files_offset") or 0)
            if next_files_offset:
                next_cursors["_files_offset"] = str(next_files_offset)
        if next_cursors:
            payload: dict[str, Any] = {"mode": "all_files", "cursors": next_cursors}
            next_cursor_text = json.dumps(payload, separators=(",", ":"))
        return {
            "ok": True,
            "url": IMAGINE_BASE + "/imagine",
            "view": "all_files",
            "imagine": imagine_session_summary(session),
            "cursor": cursor,
            "next_cursor": next_cursor_text,
            "has_more": bool(next_cursors),
            "root_count": len(root_posts),
            "seed_count": len(deduped_seed_posts),
            "attempts": attempts,
            "scan_count": scan_result.get("scan_count", 0),
            "scan_remote_count": scan_result.get("scan_remote_count", 0),
            "scan_location": scan_result.get("scan_location", ""),
            "scan_error": scan_result.get("scan_error", ""),
            "asset_count": asset_result.get("asset_count", 0),
            "conversation_asset_count": asset_result.get("conversation_asset_count", 0),
            "conversation_only_count": asset_result.get("conversation_only_count", 0),
            "local_deleted_asset_count": asset_result.get("local_deleted_asset_count", 0),
            "local_deleted_asset_id_count": asset_result.get("local_deleted_asset_id_count", 0),
            "local_deleted_group_count": asset_result.get("local_deleted_group_count", 0),
            "asset_scanned_count": asset_result.get("asset_scanned_count", 0),
            "asset_deleted_count": asset_result.get("asset_deleted_count", 0),
            "conversation_only_deleted_count": asset_result.get("conversation_only_deleted_count", 0),
            "local_deleted_count": asset_result.get("local_deleted_count", 0),
            "files_page_deleted_count": asset_result.get("files_page_deleted_count", 0),
            "files_page_tracked_deleted_count": asset_result.get("files_page_tracked_deleted_count", 0),
            "files_page_tracked_hydrated_count": asset_result.get("files_page_tracked_hydrated_count", 0),
            "files_page_tracker_installed": asset_result.get("files_page_tracker_installed", False),
            "files_response_group_count": asset_result.get("files_response_group_count", 0),
            "files_heuristic_group_count": asset_result.get("files_heuristic_group_count", 0),
            "files_rest_asset_count": asset_result.get("files_rest_asset_count", 0),
            "files_rest_offset": asset_result.get("files_rest_offset", 0),
            "files_rest_attempt_count": asset_result.get("files_rest_attempt_count", 0),
            "next_files_offset": asset_result.get("next_files_offset", 0),
            "files_page_scroll_rounds": asset_result.get("files_page_scroll_rounds", 0),
            "files_page_scroll_moved": asset_result.get("files_page_scroll_moved", False),
            "files_page_scroll_container_count": asset_result.get("files_page_scroll_container_count", 0),
            "asset_filtered_count": asset_result.get("asset_filtered_count", 0),
            "asset_skipped_count": asset_result.get("asset_skipped_count", 0),
            "asset_failed_count": asset_result.get("asset_failed_count", 0),
            "updated_deleted_count": asset_result.get("updated_deleted_count", 0),
            "asset_error": asset_result.get("asset_error", ""),
            "files_view_mode": asset_result.get("files_view_mode", ""),
            **processed,
        }

    def list_imagine_remote_library(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            limit = int(payload.get("limit") or 20)
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(limit, 40))
        try:
            scan_limit = int(payload.get("scan_limit") or max(240, limit * 4))
        except (TypeError, ValueError):
            scan_limit = max(240, limit * 4)
        scan_limit = max(limit, min(scan_limit, 1000))
        try:
            workspace_limit = int(payload.get("workspace_limit") or 160)
        except (TypeError, ValueError):
            workspace_limit = 160
        workspace_limit = max(1, min(workspace_limit, 500))
        include_conversations = payload.get("include_conversations", True) is not False
        cursor = str(payload.get("cursor") or "").strip()
        requested_view = str(payload.get("view") or "").strip().lower()
        view = requested_view if requested_view in {"all_files", "discover"} else "all"
        discover_type = str(payload.get("discover_type") or payload.get("media_type") or "").strip().lower()
        portfolio_type = str(payload.get("portfolio_type") or (payload.get("media_type") if view == "all" else "") or "").strip().lower()
        session = read_imagine_session()
        if not session or not valid_imagine_cookies(session):
            raise StudioError("Select or capture an Imagine account first.", 401)
        session = persist_imagine_session_identity(session)

        account = self.imagine_import_account_context(session)
        if view == "all_files":
            return self.list_imagine_deleted_remote_library(
                limit,
                session,
                account,
                cursor,
                scan_limit,
                workspace_limit,
                include_conversations,
                True,
            )
        if view == "discover":
            return self.list_imagine_discover_remote_library(limit, session, account, cursor, discover_type)

        portfolio_filter = {"source": "MEDIA_POST_SOURCE_LIKED"}
        if portfolio_type == "video":
            portfolio_filter["mediaType"] = "MEDIA_POST_TYPE_VIDEO"
        elif portfolio_type == "image":
            portfolio_filter["mediaType"] = "MEDIA_POST_TYPE_IMAGE"
        else:
            portfolio_type = "all"
        posts_payload = self.imported_media_posts_page_direct(limit, session, cursor, filter_payload=portfolio_filter)
        root_posts = posts_payload.get("posts") if isinstance(posts_payload.get("posts"), list) else []
        seed_posts = self.extract_media_posts({"posts": root_posts})
        if portfolio_type == "all":
            self.remember_imagine_saved_post_keys(account, seed_posts, str(posts_payload.get("nextCursor") or ""))
        seed_ids = {str(post.get("id") or "") for post in seed_posts if isinstance(post, dict)}
        processed = self.imagine_remote_items_from_seed_posts(
            seed_posts,
            seed_ids,
            session,
            account,
            limit,
            verify_candidates=False,
        )

        return {
            "ok": True,
            "url": IMAGINE_BASE + "/imagine",
            "view": "all",
            "portfolio_type": portfolio_type,
            "imagine": imagine_session_summary(session),
            "cursor": cursor,
            "next_cursor": str(posts_payload.get("nextCursor") or ""),
            "has_more": bool(posts_payload.get("nextCursor")),
            "root_count": len(root_posts),
            "seed_count": len(seed_posts),
            **processed,
        }

    def remote_media_url_from_item_payload(self, item: dict[str, Any], kind: str) -> str:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        imagine = metadata.get("imagine") if isinstance(metadata.get("imagine"), dict) else {}
        candidates = [
            item.get("remote_url"),
            imagine.get("media_url"),
            imagine.get("asset_url"),
            metadata.get("imagine_asset_url"),
            metadata.get("imagine_video_asset_url"),
            metadata.get("imagine_video_media_url") if kind == "video" else metadata.get("imagine_media_url"),
            metadata.get("media_url"),
        ]
        local_url = item.get("local_url")
        if isinstance(local_url, str) and "/api/imagine/remote/media" in local_url:
            try:
                parsed = urllib.parse.urlparse(local_url)
                query = urllib.parse.parse_qs(parsed.query)
                candidates.append((query.get("url") or [""])[0])
            except ValueError:
                pass
        for candidate in candidates:
            url = normalize_media_api_url(candidate if isinstance(candidate, str) else None)
            if not url:
                continue
            if kind == "video" and is_possible_video_url_candidate(url):
                return url
            if kind == "image" and is_possible_image_url_candidate(url):
                return url
        raise StudioError("Imagine remote media URL is missing.", 400)

    def existing_item_remote_media_keys(self, item: dict[str, Any]) -> set[str]:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        imagine = metadata.get("imagine") if isinstance(metadata.get("imagine"), dict) else {}
        values = [
            item.get("remote_url"),
            metadata.get("remote_url"),
            metadata.get("imagine_media_url"),
            metadata.get("imagine_video_media_url"),
            metadata.get("imagine_asset_url"),
            metadata.get("imagine_video_asset_url"),
            imagine.get("media_url"),
            imagine.get("asset_url"),
        ]
        return {canonical_media_key(value) for value in values if canonical_media_key(value)}

    def remote_url_from_payload_value(self, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            return ""
        candidate = value.strip()
        if "/api/imagine/remote/media" in candidate:
            try:
                parsed = urllib.parse.urlparse(candidate)
                query = urllib.parse.parse_qs(parsed.query)
                candidate = (query.get("url") or [""])[0] or candidate
            except ValueError:
                pass
        return normalize_media_api_url(candidate) or ""

    def imagine_remote_primary_marker(self, item: dict[str, Any]) -> dict[str, str]:
        primary_url = ""
        for key in ("primary_remote_url", "primary_local_url"):
            primary_url = self.remote_url_from_payload_value(item.get(key))
            if primary_url:
                break
        return compact(
            {
                "primary_remote_item_id": str(item.get("primary_remote_item_id") or "").strip(),
                "primary_remote_url": primary_url,
                "primary_remote_key": canonical_media_key(primary_url) if primary_url else "",
                "primary_type": str(item.get("primary_type") or "").strip(),
                "primary_created_at": str(item.get("primary_created_at") or "").strip(),
            }
        )

    def apply_imagine_primary_markers(self, markers_by_item_id: dict[str, dict[str, str]]) -> int:
        markers_by_item_id = {
            str(item_id): marker
            for item_id, marker in markers_by_item_id.items()
            if item_id and marker
        }
        if not markers_by_item_id:
            return 0
        data = self.library._read()
        updated = 0
        for item in data.get("items", []):
            if not isinstance(item, dict):
                continue
            marker = markers_by_item_id.get(str(item.get("id") or ""))
            if not marker:
                continue
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            item["metadata"] = metadata
            imagine = metadata.get("imagine") if isinstance(metadata.get("imagine"), dict) else {}
            metadata["imagine"] = imagine
            changed = False
            for key, value in marker.items():
                if value and metadata.get(key) != value:
                    metadata[key] = value
                    changed = True
                if value and imagine.get(key) != value:
                    imagine[key] = value
                    changed = True
            if changed:
                item["updated_at"] = utc_now()
                updated += 1
        if updated:
            self.library._write(data)
        return updated

    def import_imagine_remote_to_gallery(self, payload: dict[str, Any]) -> dict[str, Any]:
        folder_id = require_text(payload, "folder_id")
        remote_items = payload.get("items")
        if not isinstance(remote_items, list) or not remote_items:
            raise StudioError("items must be a non-empty list.")
        data = self.library._read()
        folder = self.library.gallery_folder(folder_id, data)
        if not folder.get("parent_id"):
            raise StudioError("Select a second-level Gallery folder.")
        existing_by_key: dict[str, dict[str, Any]] = {}
        for item in data.get("items", []):
            if not isinstance(item, dict):
                continue
            for key in self.existing_item_remote_media_keys(item):
                existing_by_key.setdefault(key, item)

        imported: list[dict[str, Any]] = []
        existing_ids: list[str] = []
        existing_primary_markers: dict[str, dict[str, str]] = {}
        seen_keys: set[str] = set()
        for raw_item in remote_items:
            if not isinstance(raw_item, dict):
                continue
            kind = "video" if str(raw_item.get("type") or "").lower() == "video" else "image"
            url = self.remote_media_url_from_item_payload(raw_item, kind)
            key = canonical_media_key(url) or url
            primary_marker = self.imagine_remote_primary_marker(raw_item)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            existing = existing_by_key.get(key)
            if existing and existing.get("id"):
                existing_id = str(existing["id"])
                existing_ids.append(existing_id)
                if primary_marker:
                    existing_primary_markers[existing_id] = primary_marker
                continue

            media_bytes, mime = self.download_imagine_media(url, kind)
            item_id = uuid.uuid4().hex
            metadata = raw_item.get("metadata") if isinstance(raw_item.get("metadata"), dict) else {}
            imagine = metadata.get("imagine") if isinstance(metadata.get("imagine"), dict) else {}
            remote_deleted = bool(metadata.get("remote_deleted") or metadata.get("is_deleted_remote") or imagine.get("deleted"))
            remote_deleted_status = str(metadata.get("remote_deleted_status") or imagine.get("deleted_status") or "").strip()
            conversation_only = bool(metadata.get("conversation_only") or imagine.get("conversation_only"))
            group_id = str(metadata.get("group_id") or imagine.get("group_id") or raw_item.get("id") or item_id)
            parent_id = str(metadata.get("parent_id") or imagine.get("parent_post_id") or "")
            prompt = str(raw_item.get("prompt") or "")
            title = str(raw_item.get("title") or "").strip() or ("Video" if kind == "video" else "Image")
            created_at = str(raw_item.get("created_at") or "") or utc_now()
            output_dir = self.library.gallery_output_dir(folder_id, "Video" if kind == "video" else "Image")
            stem = safe_file_stem(
                f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-imagine-remote-{item_id[:8]}",
                f"Imagine-{kind.title()}",
            )
            path = unique_path(output_dir / f"{stem}{guess_ext(mime, '.mp4' if kind == 'video' else '.jpg')}")
            path.write_bytes(media_bytes)
            metadata_payload = {
                "provider": "imagine",
                "token_source": "imagine",
                "source": "imagine-remote-import",
                "import_source": "imagine-remote",
                "remote_item_id": raw_item.get("id"),
                "remote_url": url,
                "raw_metadata": metadata,
                **primary_marker,
            }
            metadata_path = self.write_metadata(item_id, metadata_payload)
            item = {
                "id": item_id,
                "type": kind,
                "mode": "imagine-import",
                "source": "imagine-import",
                "title": title,
                "prompt": prompt,
                "category": "Video" if kind == "video" else "Image",
                "tags": ["Imagine"],
                "created_at": created_at,
                "local_url": self.library.media_url(path),
                "remote_url": url,
                "file": str(path),
                "mime": mime,
                "request_id": str(raw_item.get("request_id") or imagine.get("post_id") or ""),
                "provider": "imagine",
                "token_source": "imagine",
                "metadata_file": str(metadata_path),
                "metadata": {
                    "group_id": group_id,
                    "parent_id": parent_id,
                    "gallery_folder_id": folder_id,
                    "provider": "imagine",
                    "token_source": "imagine",
                    "model": metadata.get("model") or imagine_model_name(kind),
                    "source": "imagine-import",
                    "import_source": "imagine-remote",
                    "imported": True,
                    "remote_url": url,
                    "remote_item_id": raw_item.get("id"),
                    "remote_created_at": created_at,
                    "remote_deleted": remote_deleted or None,
                    "is_deleted_remote": remote_deleted or None,
                    "remote_deleted_status": remote_deleted_status or None,
                    "conversation_only": conversation_only or None,
                    "imagine_asset_id": metadata.get("imagine_asset_id"),
                    "imagine_asset_url": metadata.get("imagine_asset_url"),
                    "imagine_video_asset_id": metadata.get("imagine_video_asset_id"),
                    "imagine_video_asset_url": metadata.get("imagine_video_asset_url"),
                    **primary_marker,
                    "imagine": compact(
                        {
                            **imagine,
                            "remote": False,
                            "imported": True,
                            "media_url": url,
                            "media_type": kind,
                            "group_id": group_id,
                            "parent_post_id": parent_id,
                            "deleted": remote_deleted or None,
                            "deleted_status": remote_deleted_status or None,
                            "conversation_only": conversation_only or None,
                            **primary_marker,
                        }
                    ),
                },
            }
            if kind == "video":
                item["metadata"]["imagine_video_media_url"] = url
            else:
                item["metadata"]["imagine_media_url"] = url
            imported.append(self.library.add_item(item))

        moved_existing = 0
        if existing_ids:
            try:
                moved_existing = int(self.library.move_items_to_gallery(existing_ids, folder_id).get("count") or 0)
            except StudioError as exc:
                if "already in this Gallery folder" not in exc.message:
                    raise
                moved_existing = len(set(existing_ids))
        self.apply_imagine_primary_markers(existing_primary_markers)
        repaired_relationships = self.library.repair_imagine_import_relationships_in_db()
        if not imported and not moved_existing:
            raise StudioError("No Imagine remote media could be imported.", 400)
        return {
            "ok": True,
            "imported": imported,
            "imported_count": len(imported),
            "moved_existing_count": moved_existing,
            "repaired_relationships_count": repaired_relationships,
            "count": len(imported) + moved_existing,
            "folder_id": folder_id,
        }

    def save_uploaded_images(self, payload: dict[str, Any]) -> dict[str, Any]:
        images = payload.get("images")
        names = payload.get("names") if isinstance(payload.get("names"), list) else []
        if not isinstance(images, list) or not images:
            raise StudioError("No upload images were provided.")
        if len(images) > 24:
            raise StudioError("Upload up to 24 images at a time.")
        saved: list[dict[str, Any]] = []
        self.library.reload_paths()
        gallery_folder_id = str(payload.get("gallery_folder_id") or "").strip()
        upload_dir = self.library.gallery_output_dir(gallery_folder_id, "Upload Image")
        for index, value in enumerate(images):
            if not isinstance(value, str):
                continue
            media_bytes, mime = data_uri_to_bytes(value)
            if not mime.startswith("image/"):
                raise StudioError("Only image uploads are supported.")
            name = str(names[index] if index < len(names) else "").strip()
            source_stem = safe_file_stem(Path(name).stem if name else "Source Image", "Source Image")
            ext = guess_ext(mime, Path(name).suffix if name else ".png")
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            path = unique_path(upload_dir / f"{stamp}-{source_stem}{ext}")
            path.write_bytes(media_bytes)
            upload_id = f"upload:{gallery_folder_id}:{path.name}" if gallery_folder_id else f"upload:{path.name}"
            saved.append(
                {
                    "id": upload_id,
                    "type": "upload-image",
                    "title": path.stem,
                    "name": path.name,
                    "created_at": utc_now(),
                    "local_url": self.library.media_url(path),
                    "file": str(path),
                    "gallery_folder_id": gallery_folder_id,
                    "mime": mime,
                    "size": len(media_bytes),
                }
            )
        return {"saved": saved, "uploads": self.list_uploaded_images()}

    def save_image_edit(self, payload: dict[str, Any]) -> dict[str, Any]:
        item_id = require_text(payload, "item_id")
        image_data = require_text(payload, "image")
        if item_id.startswith("upload-card:"):
            upload_id = item_id.removeprefix("upload-card:")
            upload = next(
                (candidate for candidate in self.list_uploaded_images() if candidate.get("id") == upload_id),
                None,
            )
            if not upload:
                raise StudioError("Uploaded image not found.", 404)
            source = {
                **upload,
                "id": item_id,
                "type": "image",
                "mode": "upload",
                "prompt": "",
                "tags": [],
                "metadata": {"gallery_folder_id": upload.get("gallery_folder_id") or None},
            }
        else:
            source = self.library.get_item(item_id)
        if source.get("type") not in {"image", "video"}:
            raise StudioError("Only Library images and video source images can be edited.")
        source_url = str(payload.get("source_url") or "").strip()
        if not source_url and source.get("type") == "image":
            source_url = str(source.get("local_url") or "").strip()
        if not source_url:
            raise StudioError("This video does not have a source image to edit.")

        media_bytes, mime = data_uri_to_bytes(image_data)
        if mime not in {"image/png", "image/jpeg"}:
            raise StudioError("Edited images must be PNG or JPEG.")

        self.library.reload_paths()
        source_url_path = urllib.parse.unquote(urllib.parse.urlparse(source_url).path)
        source_stem = Path(source_url_path).stem or Path(str(source.get("file") or source.get("title") or "Image")).stem
        ext = ".jpg" if mime == "image/jpeg" else ".png"
        path = next_image_edit_path(self.library.image_dir, source_stem, ext)
        path.write_bytes(media_bytes)

        source_metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
        item_id_new = uuid.uuid4().hex
        item = {
            "id": item_id_new,
            "type": "image",
            "mode": "basic-image-edit",
            "title": path.stem,
            "prompt": str(source.get("prompt") or ""),
            "category": "Image",
            "tags": normalize_tags(source.get("tags")),
            "created_at": utc_now(),
            "local_url": self.library.media_url(path),
            "file": str(path),
            "mime": mime,
            "metadata": {
                "group_id": str(source_metadata.get("group_id") or source.get("id") or item_id_new),
                "parent_id": source.get("id"),
                "gallery_folder_id": None,
                "editor": "TOAST UI Image Editor",
                "source_images": [{"url": source_url}],
            },
        }
        return {"item": self.library.add_item(item)}

    def delete_uploaded_image(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_id = str(payload.get("id") or "").strip()
        raw_file = str(payload.get("file") or "").strip()
        if raw_id.startswith("upload:"):
            name = raw_id.removeprefix("upload:")
        elif raw_file:
            name = Path(raw_file).name
        else:
            name = raw_id
        if not name:
            raise StudioError("Upload image id is required.")

        self.library.reload_paths()
        target = Path(raw_file).expanduser().resolve() if raw_file else (self.library.upload_dir / name).resolve()
        roots = [path.resolve() for path, _ in self.library.upload_image_locations()]
        if not any(target.parent == root for root in roots):
            raise StudioError("Invalid upload image path.", 400)
        if target.exists():
            if not target.is_file():
                raise StudioError("Upload image is not a file.", 400)
            safe_move_to_trash(str(target), target.parent)
        return {"ok": True, "uploads": self.list_uploaded_images()}

    def account_usage(self, force: bool = False) -> dict[str, Any]:
        auth = load_auth_summary(self.auth_file)
        email = auth.get("email") if isinstance(auth.get("email"), str) else None
        with self.usage_lock:
            if (
                not force
                and self.usage_cache is not None
                and time.monotonic() - self.usage_checked_at < USAGE_CACHE_SECONDS
            ):
                cached = dict(self.usage_cache)
                cached["cached"] = True
                return cached
        usage = fetch_account_usage(self.auth_file, self.timeout)
        if usage.get("ok"):
            write_usage_snapshot(usage)
        else:
            snapshot = read_usage_snapshot(email)
            if snapshot is not None:
                snapshot["message"] = snapshot.get("message") or "Last saved usage"
                usage = snapshot
        with self.usage_lock:
            self.usage_cache = dict(usage)
            self.usage_checked_at = time.monotonic()
        usage["cached"] = False
        return usage

    def import_account_usage(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = require_text(payload, "text")
        auth = load_auth_summary(self.auth_file)
        email = auth.get("email") if isinstance(auth.get("email"), str) else None
        usage = usage_from_text(text, email=email, source="manual")
        write_usage_snapshot(usage)
        with self.usage_lock:
            self.usage_cache = dict(usage)
            self.usage_checked_at = time.monotonic()
        usage["cached"] = False
        return usage

    def set_library_folder(self, payload: dict[str, Any]) -> dict[str, Any]:
        root = str(payload.get("path") or "").strip()
        info = self.library.set_root(root)
        log_event(f"library folder set to {info['root']}")
        return {"ok": True, "library": info, "state": self.state()}

    def choose_library_folder(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = str(payload.get("current") or self.library.root or "").strip()
        selected = choose_library_folder(current)
        if selected is None:
            return {"ok": True, "cancelled": True, "library": self.library.info(), "state": self.state()}
        info = self.library.set_root(selected)
        log_event(f"library folder set to {info['root']}")
        return {"ok": True, "cancelled": False, "library": info, "state": self.state()}

    def accounts(self) -> dict[str, Any]:
        data = read_accounts_file()
        current = account_record(self.auth_file)
        current_email = current.get("email")
        current_is_usable = bool(current.get("exists") and isinstance(current_email, str) and current_email)
        active_id = data.get("active_id") or (current["id"] if current_is_usable else "")
        records = merge_account_records(data.get("accounts", []), self.auth_file)
        hidden = hidden_account_ids()
        if active_id in hidden:
            active_id = ""
        records = [record for record in records if record.get("id") not in hidden]
        if active_id and not any(record.get("id") == active_id for record in records):
            active_id = records[0]["id"] if records else ""
        for record in records:
            record["selected"] = record["id"] == active_id or record["auth_file"] == str(Path(self.auth_file).expanduser())
            record["tier"] = normalize_account_tier(record.get("tier"))
        return {
            "accounts": records,
            "active_id": active_id,
            "cli_auth_file": self.cli_auth_file,
            "generation_provider": self.generation_provider(),
            "imagine": imagine_session_summary(),
            "imagine_accounts": imagine_accounts_summary(data),
        }

    def register_account(self, payload: dict[str, Any]) -> dict[str, Any]:
        auth_file = str(payload.get("auth_file") or self.auth_file).strip()
        label = str(payload.get("label") or "").strip() or None
        if not auth_file:
            raise StudioError("Auth file path is required.")
        path = Path(auth_file).expanduser()
        if not path.exists():
            raise StudioError(f"Auth file not found: {path}", 404)
        data = read_accounts_file()
        saved = [item for item in data.get("accounts", []) if isinstance(item, dict)]
        record = snapshot_auth_file(str(path), label)
        record_email = record.get("email")
        if (
            label
            and "@" in label
            and isinstance(record_email, str)
            and record_email.lower() != label.lower()
        ):
            raise StudioError(
                f"Auth file belongs to {record_email}, not {label}. Log in as {label} first, then register again.",
                400,
            )
        forget_hidden_account(record["id"])
        saved = upsert_saved_account(saved, record, preserve_existing_tier=True)
        data["active_id"] = record["id"]
        data["accounts"] = saved
        data = prioritize_linked_accounts(data, "build", record)
        write_accounts_file(data)
        installed = install_account_auth(record["auth_file"], self.cli_auth_file)
        self.auth_file = installed
        self.client.auth_file = installed
        with self.usage_lock:
            self.usage_cache = None
            self.usage_checked_at = 0.0
        log_event(f"CLI auth switched to registered account {record.get('email') or record.get('label') or record['id']}")
        self.set_generation_provider("build")
        return self.accounts()

    def set_active_account(self, account_id: str) -> dict[str, Any]:
        data = read_accounts_file()
        records = merge_account_records(data.get("accounts", []), self.auth_file)
        selected = next((record for record in records if record["id"] == account_id), None)
        if selected is None:
            raise StudioError("Account not found.", 404)
        if not selected["exists"]:
            raise StudioError(f"Auth file not found: {selected['auth_file']}", 404)
        installed = install_account_auth(selected["auth_file"], self.cli_auth_file)
        self.auth_file = installed
        self.client.auth_file = installed
        with self.usage_lock:
            self.usage_cache = None
            self.usage_checked_at = 0.0
        saved = [item for item in data.get("accounts", []) if isinstance(item, dict)]
        saved = upsert_saved_account(saved, selected)
        data["active_id"] = selected["id"]
        data["accounts"] = saved
        data = prioritize_linked_accounts(data, "build", selected)
        write_accounts_file(data)
        log_event(f"CLI auth switched to account {selected.get('email') or selected.get('label') or selected['id']}")
        self.set_generation_provider("build")
        return self.accounts()

    def delete_account(self, account_id: str) -> dict[str, Any]:
        data = read_accounts_file()
        saved = [item for item in data.get("accounts", []) if isinstance(item, dict)]
        selected = next((item for item in saved if str(item.get("id") or "") == account_id), None)
        if selected is None:
            raise StudioError("Account not found.", 404)
        auth_file = str(selected.get("auth_file") or "")
        source_auth_file = str(selected.get("source_auth_file") or "")
        kept = [item for item in saved if str(item.get("id") or "") != account_id]
        active_id = str(data.get("active_id") or "")
        if active_id == account_id:
            active_id = ""
            self.auth_file = self.cli_auth_file
            self.client.auth_file = self.cli_auth_file
            self.set_generation_provider("build")
            with self.usage_lock:
                self.usage_cache = None
                self.usage_checked_at = 0.0
        data["active_id"] = active_id
        data["accounts"] = kept
        write_accounts_file(data)
        remember_hidden_account(account_id)
        if auth_file and auth_file != source_auth_file:
            try:
                path = Path(auth_file).expanduser().resolve()
                if path.is_file() and is_saved_account_auth_copy(path):
                    path.unlink()
            except OSError as exc:
                log_event(f"could not delete saved account auth copy: {exc}")
        log_event(f"deleted registered account {account_id}")
        return self.accounts()

    def reorder_accounts(self, payload: dict[str, Any]) -> dict[str, Any]:
        provider = str(payload.get("provider") or "build").strip().lower()
        ordered_ids = payload.get("ids")
        if not isinstance(ordered_ids, list):
            raise StudioError("Account order is invalid.")
        data = read_accounts_file()
        if provider == "imagine":
            accounts = reorder_records_by_ids(stored_imagine_accounts(data), [str(value) for value in ordered_ids])
            data["imagine_accounts"] = accounts
            write_accounts_file(data)
            return self.accounts()
        saved = [item for item in data.get("accounts", []) if isinstance(item, dict)]
        data["accounts"] = reorder_records_by_ids(saved, [str(value) for value in ordered_ids])
        write_accounts_file(data)
        return self.accounts()

    def update_account_tier(self, payload: dict[str, Any]) -> dict[str, Any]:
        provider = str(payload.get("provider") or "build").strip().lower()
        account_id = require_text(payload, "id")
        tier = normalize_account_tier(payload.get("tier"))
        data = read_accounts_file()
        if provider == "imagine":
            accounts = stored_imagine_accounts(data)
            found = False
            for account in accounts:
                if str(account.get("id") or "") == account_id:
                    account["tier"] = tier
                    found = True
                    if str(data.get("imagine_active_id") or "") == account_id:
                        write_active_imagine_session_file(account)
                    break
            if not found:
                raise StudioError("Imagine account not found.", 404)
            data["imagine_accounts"] = accounts
            write_accounts_file(data)
            return self.accounts()

        saved = [item for item in data.get("accounts", []) if isinstance(item, dict)]
        records = merge_account_records(saved, self.auth_file)
        selected = next((record for record in records if str(record.get("id") or "") == account_id), None)
        if selected is None:
            raise StudioError("Account not found.", 404)
        selected["tier"] = tier
        data["accounts"] = upsert_saved_account(saved, selected)
        write_accounts_file(data)
        return self.accounts()

    def open_imagine_chrome_page(
        self,
        url: str,
        *,
        visible: bool = False,
        popup: bool = False,
        anchor: Any = None,
    ) -> dict[str, Any]:
        ensure_dirs()
        if popup:
            width, height = IMAGINE_POPUP_WINDOW_SIZE
            left, top = centered_window_position_in_anchor(width, height, anchor)
        elif visible:
            width, height = 1160, 820
            left, top = centered_window_position_in_anchor(width, height, anchor)
        else:
            width, height = 520, 320
            left, top = -20000, 80

        parsed_url = urllib.parse.urlparse(url)
        if url.startswith(IMAGINE_BASE) and parsed_url.path.startswith(("/files", "/imagine")):
            try:
                target = (
                    find_imagine_files_cdp_target(IMAGINE_DEBUG_PORT)
                    if parsed_url.path.startswith("/files")
                    else find_imagine_cdp_target(IMAGINE_DEBUG_PORT)
                )
                if parsed_url.path.startswith("/files") and not re.search(
                    r"https://(?:www\.)?grok\.com/files(?:[?#/]|$)",
                    str(target.get("url") or ""),
                    re.IGNORECASE,
                ):
                    raise StudioError("No existing Grok Files window to reuse.", 404)
                ws_url = str(target.get("webSocketDebuggerUrl") or "")
                cdp_call(ws_url, "Page.navigate", {"url": url}, timeout=5)
                if not visible:
                    cdp_hide_target_window(target)
                return {
                    "ok": True,
                    "fallback": False,
                    "reused": True,
                    "url": url,
                    "debug_port": IMAGINE_DEBUG_PORT,
                    "profile_dir": str(IMAGINE_PROFILE_DIR),
                    "imagine": imagine_session_summary(),
                }
            except StudioError:
                pass

        args = ["/usr/bin/open"]
        if not visible:
            args.append("-g")
        args.extend(
            [
                "-na",
                "Google Chrome",
                "--args",
                f"--remote-debugging-port={IMAGINE_DEBUG_PORT}",
                f"--user-data-dir={IMAGINE_PROFILE_DIR}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
                "--new-window",
                f"--window-size={width},{height}",
                f"--window-position={left},{top}",
            ]
        )
        args.append(url)
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            webbrowser.open(url)
            return {
                "ok": True,
                "fallback": True,
                "message": "Opened the page in the default browser. Chrome capture may not be available.",
                "url": url,
                "imagine": imagine_session_summary(),
            }
        return {
            "ok": True,
            "fallback": False,
            "url": url,
            "debug_port": IMAGINE_DEBUG_PORT,
            "profile_dir": str(IMAGINE_PROFILE_DIR),
            "imagine": imagine_session_summary(),
        }

    def start_imagine_login(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload if isinstance(payload, dict) else {}
        ensure_dirs()
        width, height = IMAGINE_POPUP_WINDOW_SIZE
        left, top = centered_window_position_in_anchor(width, height, payload.get("anchor"))
        url = IMAGINE_BASE + "/imagine"
        args = [
            "/usr/bin/open",
            "-na",
            "Google Chrome",
            "--args",
            f"--remote-debugging-port={IMAGINE_DEBUG_PORT}",
            f"--user-data-dir={IMAGINE_PROFILE_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
            f"--window-size={width},{height}",
            f"--window-position={left},{top}",
            url,
        ]
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {
            "ok": True,
            "url": url,
            "debug_port": IMAGINE_DEBUG_PORT,
            "profile_dir": str(IMAGINE_PROFILE_DIR),
            "imagine": imagine_session_summary(),
        }

    def open_imagine_usage_page(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload if isinstance(payload, dict) else {}
        ensure_dirs()
        width, height = 560, 760
        left, top = centered_window_position_in_anchor(width, height, payload.get("anchor"))
        args = [
            "/usr/bin/open",
            "-na",
            "Google Chrome",
            "--args",
            f"--remote-debugging-port={IMAGINE_DEBUG_PORT}",
            f"--user-data-dir={IMAGINE_PROFILE_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
            f"--window-size={width},{height}",
            f"--window-position={left},{top}",
            USAGE_URL,
        ]
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"ok": True, "url": USAGE_URL, "imagine": imagine_session_summary()}

    def capture_imagine_login(self) -> dict[str, Any]:
        try:
            target = find_imagine_cdp_target(IMAGINE_DEBUG_PORT)
            ws_url = str(target.get("webSocketDebuggerUrl") or "")
            result = cdp_call(ws_url, "Network.getAllCookies")
            cookies = normalize_imagine_cookies(result.get("cookies") if isinstance(result.get("cookies"), list) else [])
            summary = write_imagine_session(cookies, str(target.get("url") or ""), self.timeout)
            self.set_generation_provider("imagine")
            log_event(f"captured Imagine session cookies={summary.get('cookie_count')}")
            return self.accounts()
        finally:
            close_imagine_chrome_browser(IMAGINE_DEBUG_PORT)

    def select_imagine_account(self, account_id: str | None = None) -> dict[str, Any]:
        data = read_accounts_file()
        accounts = saved_imagine_accounts(data)
        selected = None
        if account_id:
            selected = next((account for account in accounts if str(account.get("id") or "") == account_id), None)
            if selected is None:
                raise StudioError("Imagine account not found.", 404)
        else:
            active_id = str(data.get("imagine_active_id") or "")
            selected = next((account for account in accounts if str(account.get("id") or "") == active_id), None)
            selected = selected or (accounts[0] if accounts else None)
        if selected is None:
            raise StudioError("Capture an Imagine login session first.", 401)
        selected = persist_imagine_session_identity(selected)
        data = read_accounts_file()
        write_active_imagine_session_file(selected)
        data["imagine_accounts"] = upsert_imagine_account(stored_imagine_accounts(data), selected)
        data["imagine_active_id"] = str(selected.get("id") or "")
        data = prioritize_linked_accounts(data, "imagine", selected)
        write_accounts_file(data)
        self.set_generation_provider("imagine")
        return self.accounts()

    def imagine_account_statuses(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload if isinstance(payload, dict) else {}
        requested_ids = payload.get("ids") if isinstance(payload.get("ids"), list) else []
        requested = {str(value) for value in requested_ids if str(value)}
        accounts = stored_imagine_accounts(read_accounts_file())
        if requested:
            accounts = [account for account in accounts if str(account.get("id") or "") in requested]
        statuses = [imagine_account_status(account) for account in accounts]
        return {"statuses": statuses}

    def clear_imagine_login(self) -> dict[str, Any]:
        close_result = close_imagine_chrome_browser(IMAGINE_DEBUG_PORT)
        try:
            session_path = imagine_session_store_path()
            if session_path.exists():
                session_path.unlink()
        except OSError as exc:
            raise StudioError(f"Could not remove Imagine session: {exc}", 500) from exc
        try:
            if IMAGINE_PROFILE_DIR.exists():
                shutil.rmtree(IMAGINE_PROFILE_DIR)
            IMAGINE_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StudioError(f"Could not clear Imagine Chrome profile: {exc}", 500) from exc
        data = read_accounts_file()
        data["imagine_active_id"] = ""
        write_accounts_file(data)
        self.set_generation_provider("build")
        result = self.accounts()
        result["logout"] = close_result
        return result

    def delete_imagine_account(self, account_id: str) -> dict[str, Any]:
        data = read_accounts_file()
        accounts = stored_imagine_accounts(data)
        if not account_id:
            account_id = str(data.get("imagine_active_id") or "")
        if not account_id or not any(str(account.get("id") or "") == account_id for account in accounts):
            raise StudioError("Imagine account not found.", 404)
        kept = [account for account in accounts if str(account.get("id") or "") != account_id]
        active_id = str(data.get("imagine_active_id") or "")
        if active_id == account_id:
            active_id = str(kept[0].get("id") or "") if kept else ""
            if active_id:
                write_active_imagine_session_file(kept[0])
            else:
                try:
                    session_path = imagine_session_store_path()
                    if session_path.exists():
                        session_path.unlink()
                except OSError as exc:
                    raise StudioError(f"Could not remove Imagine session: {exc}", 500) from exc
                self.set_generation_provider("build")
        data["imagine_accounts"] = kept
        data["imagine_active_id"] = active_id
        write_accounts_file(data)
        if active_id:
            self.set_generation_provider("imagine")
        return self.accounts()

    def heartbeat(self) -> dict[str, Any]:
        with self.shutdown_lock:
            self.last_heartbeat = time.monotonic()
        return {"ok": True}

    def request_shutdown(self, server: ThreadingHTTPServer, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.jobs.has_active():
            log_event("shutdown skipped: active job is running")
            return {"ok": False, "active_jobs": True}
        immediate = isinstance(payload, dict) and payload.get("event") == "restart-cleanup"
        token = uuid.uuid4().hex
        with self.shutdown_lock:
            self.shutdown_token = token
        threading.Thread(target=self._shutdown_if_idle, args=(server, token, immediate), daemon=True).start()
        return {"ok": True, "delay": 0.3 if immediate else 8}

    def _shutdown_if_idle(self, server: ThreadingHTTPServer, token: str, immediate: bool = False) -> None:
        time.sleep(0.3 if immediate else 8)
        with self.shutdown_lock:
            if self.shutdown_token != token:
                return
            idle_for = time.monotonic() - self.last_heartbeat
        if not immediate and idle_for < 6:
            log_event("shutdown cancelled: browser heartbeat resumed")
            return
        if self.jobs.has_active():
            log_event("shutdown cancelled: active job is running")
            return
        log_event("restart cleanup requested; shutting down local server" if immediate else "browser tab closed; shutting down local server")
        server.shutdown()

    def close_imagine_chrome_when_idle(self, job_id: str | None = None) -> dict[str, Any] | None:
        if self.jobs.has_active(job_id):
            log_event("Imagine Chrome close delayed: another active job is running")
            return None
        result = close_imagine_chrome_browser(IMAGINE_DEBUG_PORT)
        log_event(f"Imagine Chrome close result: {result}")
        return result

    def save_prompt(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = require_text(payload, "prompt")
        translation = str(payload.get("translation") or "").strip()
        title = str(payload.get("title") or "").strip() or safe_name(prompt[:48], "Prompt").replace("-", " ")
        stem = safe_file_stem(title, "Prompt")
        prompt_dir = self.library.gallery_output_dir(payload.get("gallery_folder_id"), "Prompt")
        path = unique_path(prompt_dir / f"{stem}.txt")
        path.write_text(prompt, encoding="utf-8")
        tags = normalize_tags(payload.get("tags"))
        item = {
            "id": uuid.uuid4().hex,
            "type": "prompt",
            "mode": payload.get("mode") or "note",
            "title": title,
            "prompt": prompt,
            "translation": translation,
            "category": payload.get("category") or "Prompt",
            "tags": tags,
            "created_at": utc_now(),
            "file": str(path),
            "local_url": None,
            "mime": "text/plain",
            "metadata": {
                "library_root": str(self.library.root),
                "gallery_folder_id": payload.get("gallery_folder_id"),
            },
        }
        return self.library.add_item(item)

    def analyze_image(self, payload: dict[str, Any]) -> dict[str, Any]:
        image = require_text(payload, "image")
        model = str(payload.get("model") or DEFAULT_ANALYZE_MODEL).strip()
        if model not in ANALYZE_MODELS:
            raise StudioError("Unsupported Analyze model.")
        request = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analyze this image and write a detailed, reusable image-generation prompt in English. "
                                "Then translate that prompt naturally into Korean. Describe visible subjects, setting, "
                                "composition, lighting, colors, camera perspective, and style without inventing hidden "
                                "facts. Return exactly this plain-text structure with no markdown fences:\n"
                                "English\n\n<English prompt>\n\nKorean\n\n<Korean translation>"
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": image_reference(image),
                        },
                    ],
                }
            ],
        }
        result = self.client.post("/chat/completions", request)
        choices = result.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise StudioError("Analyze response did not contain a result.", 502)
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):
            content = "\n".join(
                str(part.get("text") or "")
                for part in content
                if isinstance(part, dict) and part.get("text")
            )
        if not isinstance(content, str) or not content.strip():
            raise StudioError("Analyze response did not contain text.", 502)
        english, korean = parse_analyze_result(content)
        return {"english": english, "korean": korean, "model": model}

    def translate_prompt(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = require_text(payload, "text")
        target_language = str(payload.get("target_language") or "Korean").strip()
        if target_language not in {"Korean", "English"}:
            raise StudioError("Unsupported translation language.")
        target_code = "ko" if target_language == "Korean" else "en"
        url = (
            "https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl=auto&tl={target_code}&dt=t"
        )
        request = urllib.request.Request(
            url,
            data=urllib.parse.urlencode({"q": text}).encode("utf-8"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                "User-Agent": "Grok Studio Lab local translator",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=min(max(5, self.timeout), 30),
                context=https_context(),
            ) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read(1000).decode("utf-8", errors="replace")
            raise StudioError(f"Google translation HTTP {exc.code}: {detail}", 502) from exc
        except urllib.error.URLError as exc:
            raise StudioError(f"Google translation network error: {format_network_error(exc)}", 502) from exc
        except json.JSONDecodeError as exc:
            raise StudioError("Google translation returned an invalid response.", 502) from exc
        segments = result[0] if isinstance(result, list) and result and isinstance(result[0], list) else []
        translation = "".join(
            str(segment[0])
            for segment in segments
            if isinstance(segment, list) and segment and isinstance(segment[0], str)
        ).strip()
        if not translation:
            raise StudioError("Google translation response did not contain text.", 502)
        return {
            "translation": translation,
            "target_language": target_language,
            "provider": "Google Translate",
        }

    def imagine_image_rest_candidate_urls(self, request_id: str, post_id: str | None) -> list[str]:
        keys = [value for value in (post_id, request_id) if isinstance(value, str) and value]
        paths: list[str] = []
        for key in keys:
            quoted = urllib.parse.quote(key)
            paths.extend(
                [
                    f"/rest/app-chat/posts/{quoted}",
                    f"/rest/app-chat/conversations/{quoted}",
                    f"/rest/app-chat/conversations/{quoted}/posts",
                ]
            )
        candidates: list[str] = []
        for path in paths:
            try:
                payload = self.imagine_get_json(path, timeout=1.5)
            except StudioError as exc:
                self.write_imagine_media_debug(
                    "image_rest_lookup",
                    {
                        "request_id": request_id,
                        "post_id": post_id,
                        "path": path,
                        "ok": False,
                        "error": exc.message[:300],
                    },
                )
                continue
            urls = extract_media_urls(payload, "image")
            self.write_imagine_media_debug(
                "image_rest_lookup",
                {
                    "request_id": request_id,
                    "post_id": post_id,
                    "path": path,
                    "ok": True,
                    "event_shape": debug_event_shape(payload),
                    "candidate_count": len(urls),
                    "candidates": [debug_media_url(url) for url in urls[:12]],
                },
            )
            for url in urls:
                if url not in candidates:
                    candidates.append(url)
        return sorted(candidates, key=lambda candidate: media_url_score(candidate, "image"), reverse=True)

    def generate_imagine_text_image(
        self,
        payload: dict[str, Any],
        prompt: str,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        session = read_imagine_session()
        if not session or not valid_imagine_cookies(session):
            raise StudioError("Select or capture an Imagine account first.", 401)
        count = max(1, min(4, int(payload.get("n") or 1)))
        quality = payload.get("model") in {"grok-imagine-image-quality", "imagine-image-quality"}
        aspect = str(payload.get("aspect_ratio") or "2:3")
        data: list[dict[str, Any]] = []
        raw_events: list[Any] = []
        for index in range(1, count + 1):
            if job_id:
                self.raise_if_cancelled(job_id)
                self.jobs.update(job_id, status="processing", progress=min(85, 5 + index * 15))
            result = self._imagine_text_image_once(prompt, aspect, quality, session, job_id)
            raw_events.append(result.get("event"))
            entry: dict[str, Any] = {
                "mime_type": result.get("mime_type") or "image/jpeg",
                "provider": "imagine",
                "token_source": "imagine",
                "model": imagine_model_name("image"),
                "imagine_post_id": result.get("post_id"),
                "imagine_account_id": session.get("id"),
                "imagine_account_email": session.get("email") or session.get("label"),
                "is_pro": quality,
            }
            if isinstance(result.get("b64_json"), str):
                entry["b64_json"] = result["b64_json"]
            if isinstance(result.get("url"), str):
                entry["url"] = result["url"]
                entry["mime_type"] = (
                    result.get("mime_type")
                    or mimetypes.guess_type(urllib.parse.urlparse(result["url"]).path)[0]
                    or "image/jpeg"
                )
                try:
                    media_post = self.create_imagine_image_media_post(result["url"], prompt=prompt, session=session)
                    media_post_id = str(media_post.get("id") or "")
                    if media_post_id:
                        entry["imagine_image_id"] = entry.get("imagine_post_id")
                        entry["imagine_post_id"] = media_post_id
                        entry["imagine_media_post_registered"] = True
                        entry["imagine_media_post"] = media_post
                        self.write_imagine_media_debug(
                            "image_media_post_registered",
                            {
                                "request_id": result.get("request_id"),
                                "image_id": entry.get("imagine_image_id"),
                                "post_id": media_post_id,
                                "liked": media_post.get("_grok_studio_liked"),
                                "like_error": media_post.get("_grok_studio_like_error"),
                                "media_url": debug_media_url(result["url"]),
                            },
                        )
                except StudioError as exc:
                    entry["imagine_image_id"] = entry.get("imagine_post_id")
                    entry["imagine_media_post_registered"] = False
                    entry["imagine_media_post_error"] = exc.message[:500]
                    self.write_imagine_media_debug(
                        "image_media_post_register_failed",
                        {
                            "request_id": result.get("request_id"),
                            "image_id": entry.get("imagine_image_id"),
                            "media_url": debug_media_url(result["url"]),
                            "error": exc.message[:500],
                        },
                    )
            if not entry.get("b64_json") and not entry.get("url"):
                raise StudioError("Imagine image response did not contain a usable image.", 502)
            data.append(entry)
        return {
            "data": data,
            "provider": "imagine",
            "token_source": "imagine",
            "model": imagine_model_name("image"),
            "raw_events": raw_events[-6:],
        }

    def _imagine_text_image_once(
        self,
        prompt: str,
        aspect: str,
        quality: bool,
        session: dict[str, Any],
        job_id: str | None = None,
    ) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        cookies = valid_imagine_cookies(session)
        if not cookies:
            raise StudioError("Select or capture an Imagine account first.", 401)
        ws = RawWebSocket(
            IMAGINE_WS_URL,
            headers={
                "Cookie": cookie_header_from_cookies(cookies),
                "Origin": IMAGINE_BASE,
                "User-Agent": imagine_user_agent(),
            },
            timeout=min(max(30, self.timeout), 120),
        )
        try:
            reset = {
                "type": "conversation.item.create",
                "timestamp": int(time.time() * 1000),
                "item": {"type": "message", "content": [{"type": "reset"}]},
            }
            create = {
                "type": "conversation.item.create",
                "timestamp": int(time.time() * 1000),
                "item": {
                    "type": "message",
                    "content": [
                        {
                            "type": "input_text",
                            "requestId": request_id,
                            "text": prompt,
                            "properties": {
                                "section_count": 0,
                                "is_kids_mode": False,
                                "enable_nsfw": True,
                                "skip_upsampler": False,
                                "enable_side_by_side": True,
                                "is_initial": False,
                                "aspect_ratio": aspect,
                                "enable_pro": quality,
                            },
                        }
                    ],
                },
            }
            ws.send_json(reset)
            ws.send_json(create)
            deadline = time.monotonic() + 240
            last_event: Any = None
            candidate_urls: list[str] = []
            post_id: str | None = None
            first_candidate_at: float | None = None
            confirm_deadline: float | None = None
            last_rest_probe_at = 0.0
            last_candidate_log_count = 0
            websocket_closed = False

            def add_candidates(urls: list[str], source: str, event: Any | None = None) -> None:
                nonlocal candidate_urls
                new_urls: list[str] = []
                changed = False
                for url in urls:
                    if url not in candidate_urls:
                        candidate_urls.append(url)
                        new_urls.append(url)
                        changed = True
                if changed:
                    candidate_urls = sorted(
                        candidate_urls,
                        key=lambda candidate: media_url_score(candidate, "image"),
                        reverse=True,
                    )
                    self.write_imagine_media_debug(
                        "image_candidate_add",
                        {
                            "request_id": request_id,
                            "post_id": post_id,
                            "source": source,
                            "new_count": len(new_urls),
                            "total_count": len(candidate_urls),
                            "event_shape": debug_event_shape(event),
                            "new_candidates": [debug_media_url(url) for url in new_urls[:12]],
                            "top_candidates": [debug_media_url(url) for url in candidate_urls[:12]],
                        },
                    )

            while time.monotonic() < deadline:
                if job_id:
                    self.raise_if_cancelled(job_id)
                now = time.monotonic()
                if candidate_urls:
                    if first_candidate_at is None:
                        first_candidate_at = now
                        confirm_deadline = now + IMAGINE_IMAGE_CONFIRM_SECONDS
                    if job_id:
                        self.jobs.update(job_id, status="processing", progress=82)
                    if len(candidate_urls) != last_candidate_log_count:
                        last_candidate_log_count = len(candidate_urls)
                        log_event(f"Imagine image candidates found request_id={request_id} count={len(candidate_urls)}")
                    for index, candidate in enumerate(candidate_urls[:6], start=1):
                        if self.probe_imagine_media_url(candidate, "image", session):
                            log_event(f"Imagine image confirmed request_id={request_id} candidates={len(candidate_urls)}")
                            self.write_imagine_media_debug(
                                "image_confirmed",
                                {
                                    "request_id": request_id,
                                    "post_id": post_id,
                                    "candidate": debug_media_url(candidate),
                                    "candidate_count": len(candidate_urls),
                                },
                            )
                            return {"url": candidate, "post_id": post_id, "request_id": request_id, "event": last_event}
                    if now - last_rest_probe_at >= 5:
                        last_rest_probe_at = now
                        add_candidates(self.imagine_image_rest_candidate_urls(request_id, post_id), "rest")
                    if confirm_deadline is not None and now >= confirm_deadline:
                        self.write_imagine_media_debug(
                            "image_confirm_failed",
                            {
                                "request_id": request_id,
                                "post_id": post_id,
                                "candidate_count": len(candidate_urls),
                                "top_candidates": [debug_media_url(url) for url in candidate_urls[:12]],
                                "last_event_shape": debug_event_shape(last_event),
                            },
                        )
                        raise StudioError(
                            "Imagine returned image URL candidates, but none were downloadable yet. Try again in a moment.",
                            502,
                        )

                if websocket_closed:
                    time.sleep(1.5)
                    continue
                readable, _, _ = select.select([ws.socket], [], [], 1.5)
                if not readable:
                    continue
                try:
                    message = ws.recv_text()
                except (OSError, TimeoutError, StudioError) as exc:
                    if isinstance(exc, StudioError) and "WebSocket connection closed" not in exc.message:
                        raise
                    if candidate_urls:
                        websocket_closed = True
                        continue
                    raise StudioError(f"Imagine image WebSocket closed before an image URL arrived. Last event: {last_event}", 502) from exc
                if message is None:
                    if candidate_urls:
                        websocket_closed = True
                        continue
                    break
                try:
                    parsed: Any = json.loads(message)
                except json.JSONDecodeError:
                    parsed = {"message": message}
                last_event = parsed
                progress = event_progress(parsed)
                if progress is not None and job_id:
                    self.jobs.update(job_id, status="processing", progress=max(8, min(88, int(progress))))
                error_text = extract_first_key(parsed, {"error", "errorMessage", "message"})
                if error_text and "moderated" in error_text.lower():
                    raise StudioError(f"Imagine moderated the request: {error_text}", 400)
                found_post_id = extract_first_key(parsed, {"postId", "post_id", "id"})
                if found_post_id:
                    post_id = found_post_id
                self.write_imagine_media_debug(
                    "image_websocket_event",
                    {
                        "request_id": request_id,
                        "post_id": post_id,
                        "event_shape": debug_event_shape(parsed),
                        "fields": debug_event_fields(parsed),
                    },
                )
                blob_payload = extract_image_blob_payload(parsed)
                if blob_payload:
                    final_blob = is_final_image_event(parsed)
                    self.write_imagine_media_debug(
                        "image_blob_confirmed" if final_blob else "image_blob_preview",
                        {
                            "request_id": request_id,
                            "post_id": post_id,
                            "final": final_blob,
                            "progress": event_progress(parsed),
                            "status": event_status_text(parsed),
                            "mime_type": blob_payload.get("mime_type"),
                            "b64_length": len(blob_payload.get("b64_json") or ""),
                            "event_shape": debug_event_shape(parsed),
                            "fields": debug_event_fields(parsed),
                        },
                    )
                    if final_blob:
                        if job_id:
                            self.jobs.update(job_id, status="saving", progress=90)
                        return {
                            **blob_payload,
                            "post_id": post_id,
                            "url": candidate_urls[0] if candidate_urls else None,
                            "request_id": request_id,
                            "event": parsed,
                        }
                add_candidates(
                    extract_media_urls(parsed, "image")
                    + imagine_public_image_candidates_from_ids(extract_values_for_keys(parsed, {"image_id", "id"})),
                    "websocket",
                    parsed,
                )
            raise StudioError(f"Imagine image response did not include an image URL. Last event: {last_event}", 502)
        finally:
            ws.close()

    def start_image(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = require_text(payload, "prompt")
        images = payload.get("images") or []
        if images and (not isinstance(images, list) or len(images) > 3):
            raise StudioError("Image editing accepts 1 to 3 source images.")
        mode = "image-edit" if images else "image-generate"
        job = self.jobs.create(mode, prompt, job_context(payload, mode))
        log_event(
            "queued "
            f"{mode} job={job['id']} prompt_chars={len(prompt)} "
            f"sources={len(images) if isinstance(images, list) else 0} "
            f"count={payload.get('n') or 1}"
        )
        thread = threading.Thread(
            target=self._run_image_job,
            args=(job["id"], payload, mode),
            daemon=True,
        )
        thread.start()
        return job

    def _run_image_job(self, job_id: str, payload: dict[str, Any], mode: str) -> None:
        try:
            self.jobs.update(job_id, status="submitting", progress=1)
            result = self.generate_image(payload, mode, job_id)
            items = result.get("items", [])
            first_item = items[0] if isinstance(items, list) and items else None
            self.jobs.update(job_id, status="done", progress=100, item=first_item, items=items)
        except JobCancelled:
            log_event(f"cancelled image job={job_id}")
            self.jobs.update(
                job_id,
                status="cancelled",
                error="Cancelled locally. The remote xAI request may still finish server-side.",
            )
        except Exception as exc:
            log_event(f"failed image job={job_id}: {exc}")
            self.jobs.update(job_id, status="failed", error=str(exc), progress=0)

    def generate_image(
        self,
        payload: dict[str, Any],
        mode: str | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        prompt = require_text(payload, "prompt")
        images = payload.get("images") or []
        if images and (not isinstance(images, list) or len(images) > 3):
            raise StudioError("Image editing accepts 1 to 3 source images.")
        mode = mode or ("image-edit" if images else "image-generate")
        if self.generation_provider() == "imagine" and not images:
            if job_id:
                self.raise_if_cancelled(job_id)
                self.jobs.update(job_id, status="processing", progress=5)
            result = self.generate_imagine_text_image(payload, prompt, job_id)
            if job_id:
                self.raise_if_cancelled(job_id)
                self.jobs.update(job_id, status="saving", progress=90)
            saved = []
            for index, entry in enumerate(result.get("data", []), start=1):
                if isinstance(entry, dict):
                    saved.append(self._save_image_result(entry, payload, prompt, "imagine-image", index, result))
            return {"items": saved, "raw_count": len(result.get("data", [])), "provider": "imagine"}
        request = compact(
            {
                "model": payload.get("model") or DEFAULT_IMAGE_MODEL,
                "prompt": prompt,
                "n": int(payload.get("n") or 1),
                "aspect_ratio": payload.get("aspect_ratio"),
                "resolution": payload.get("resolution"),
                "response_format": "b64_json",
            }
        )
        if images:
            refs = []
            for image in images:
                ref = image_reference(str(image))
                ref["type"] = "image_url"
                refs.append(ref)
            request["image" if len(refs) == 1 else "images"] = refs[0] if len(refs) == 1 else refs
            endpoint = "/images/edits"
        else:
            endpoint = "/images/generations"

        if job_id:
            self.raise_if_cancelled(job_id)
            self.jobs.update(job_id, status="processing", progress=5)
        result = self.client.post(endpoint, request)
        if job_id:
            self.raise_if_cancelled(job_id)
            self.jobs.update(job_id, status="saving", progress=90)
        saved = []
        for index, entry in enumerate(result.get("data", []), start=1):
            if not isinstance(entry, dict):
                continue
            item = self._save_image_result(entry, payload, prompt, mode, index, result)
            saved.append(item)
        return {"items": saved, "raw_count": len(result.get("data", []))}

    def imagine_video_source(self, payload: dict[str, Any]) -> tuple[str | None, str | None]:
        item_id = str(payload.get("image_item_id") or payload.get("source_item_id") or "").strip()
        if item_id:
            try:
                item = self.library.get_item(item_id)
            except StudioError:
                item = {}
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            imagine_meta = metadata.get("imagine") if isinstance(metadata.get("imagine"), dict) else {}
            post_id = (
                imagine_meta.get("post_id")
                or metadata.get("imagine_post_id")
                or item.get("imagine_post_id")
            )
            media_url = (
                imagine_meta.get("media_url")
                or metadata.get("imagine_media_url")
                or item.get("remote_url")
                or item.get("local_url")
            )
            if isinstance(post_id, str) and post_id:
                return post_id, normalize_media_api_url(media_url if isinstance(media_url, str) else None)
        image = payload.get("image")
        if isinstance(image, str) and image:
            media_url = normalize_media_api_url(image)
            if media_url:
                image_id = extract_uuid_from_text(media_url)
                return image_id, media_url
        return None, None

    def write_media_debug(self, event: str, payload: dict[str, Any]) -> None:
        self.write_imagine_media_debug(event, payload)

    def handoff_image_file(self, payload: dict[str, Any]) -> Path | None:
        image_item_id = payload.get("image_item_id")
        if isinstance(image_item_id, str) and image_item_id:
            try:
                item = self.library.get_item(image_item_id)
                file_path = item.get("file")
                if isinstance(file_path, str) and Path(file_path).exists():
                    return Path(file_path)
            except StudioError:
                pass
        image_value = payload.get("image")
        if isinstance(image_value, str):
            media_path = image_value
            parsed = urllib.parse.urlparse(image_value)
            if parsed.scheme in {"http", "https"} and parsed.path.startswith("/media/"):
                media_path = parsed.path
            if media_path.startswith("/media/"):
                try:
                    path = resolve_media_path(media_path)
                except StudioError:
                    path = None
                if path and path.exists():
                    return path
        if isinstance(image_value, str) and image_value.startswith("data:"):
            try:
                media_bytes, mime = data_uri_to_bytes(image_value)
            except StudioError:
                return None
            path = unique_path(TMP_DIR / f"imagine-video-start-{uuid.uuid4().hex[:8]}{guess_ext(mime, '.jpg')}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(media_bytes)
            return path
        return None

    def compressed_i2v_image_file(self, source_file: Path, request_id: str, target_bytes: int) -> Path | None:
        sips = Path("/usr/bin/sips")
        if not sips.exists():
            self.write_media_debug(
                "official_ui_i2v_source_compress_unavailable",
                {"request_id": request_id, "source_file": str(source_file), "reason": "sips-not-found"},
            )
            return None
        attempts = ((2048, 88), (1920, 85), (1600, 82), (1280, 78))
        try:
            original_size = source_file.stat().st_size
        except OSError:
            original_size = 0
        best_path: Path | None = None
        best_size: int | None = None
        for max_px, quality in attempts:
            output = unique_path(TMP_DIR / f"imagine-i2v-source-{uuid.uuid4().hex[:8]}-{max_px}.jpg")
            output.parent.mkdir(parents=True, exist_ok=True)
            try:
                result = subprocess.run(
                    [
                        str(sips),
                        "-s",
                        "format",
                        "jpeg",
                        "-s",
                        "formatOptions",
                        str(quality),
                        "-Z",
                        str(max_px),
                        str(source_file),
                        "--out",
                        str(output),
                    ],
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                self.write_media_debug(
                    "official_ui_i2v_source_compress_error",
                    {
                        "request_id": request_id,
                        "source_file": str(source_file),
                        "max_px": max_px,
                        "quality": quality,
                        "error": str(exc)[:400],
                    },
                )
                continue
            if result.returncode != 0 or not output.exists():
                self.write_media_debug(
                    "official_ui_i2v_source_compress_error",
                    {
                        "request_id": request_id,
                        "source_file": str(source_file),
                        "max_px": max_px,
                        "quality": quality,
                        "returncode": result.returncode,
                        "stderr": (result.stderr or result.stdout or "")[:500],
                    },
                )
                continue
            try:
                size = output.stat().st_size
            except OSError:
                continue
            if size <= 0:
                continue
            if best_size is None or size < best_size:
                best_path = output
                best_size = size
            self.write_media_debug(
                "official_ui_i2v_source_compressed",
                {
                    "request_id": request_id,
                    "source_file": str(source_file),
                    "output_file": str(output),
                    "original_bytes": original_size,
                    "compressed_bytes": size,
                    "max_px": max_px,
                    "quality": quality,
                    "fits_target": size <= target_bytes,
                },
            )
            if size <= target_bytes:
                return output
        return best_path

    def inline_source_file_for_official_i2v(
        self,
        source_file: Path | None,
        source_kind: str,
        request_id: str,
    ) -> Path | None:
        if not source_file or not source_file.exists() or source_kind != "image":
            return source_file
        try:
            size = source_file.stat().st_size
        except OSError:
            return source_file
        if size <= IMAGINE_I2V_INLINE_IMAGE_BYTES:
            return source_file
        compressed = self.compressed_i2v_image_file(source_file, request_id, IMAGINE_I2V_INLINE_IMAGE_BYTES)
        if compressed and compressed.exists():
            try:
                compressed_size = compressed.stat().st_size
            except OSError:
                compressed_size = 0
            if compressed_size and compressed_size < size:
                return compressed
        if size <= IMAGINE_I2V_MAX_INLINE_IMAGE_BYTES:
            self.write_media_debug(
                "official_ui_i2v_source_inline_original",
                {
                    "request_id": request_id,
                    "source_file": str(source_file),
                    "bytes": size,
                    "reason": "compression-unavailable-or-not-smaller",
                },
            )
            return source_file
        self.write_media_debug(
            "official_ui_i2v_source_too_large",
            {
                "request_id": request_id,
                "source_file": str(source_file),
                "bytes": size,
                "max_inline_bytes": IMAGINE_I2V_MAX_INLINE_IMAGE_BYTES,
            },
        )
        return source_file

    def prepare_official_i2v_ui(
        self,
        prompt: str,
        source_media_url: str | None,
        parent_post_id: str | None,
        model_config: dict[str, Any],
        source_file: Path | None,
        request_id: str,
    ) -> dict[str, Any]:
        inline_source_file = self.inline_source_file_for_official_i2v(source_file, "image", request_id)
        file_name = inline_source_file.name if inline_source_file else "grok-studio-source.jpg"
        mime_type = mimetypes.guess_type(file_name)[0] or "image/jpeg"
        file_b64 = ""
        if inline_source_file and inline_source_file.exists():
            try:
                if inline_source_file.stat().st_size <= IMAGINE_I2V_MAX_INLINE_IMAGE_BYTES:
                    file_b64 = base64.b64encode(inline_source_file.read_bytes()).decode("ascii")
            except OSError:
                file_b64 = ""
        hook_config = {
            "requestId": request_id,
            "prompt": prompt,
            "sourceMediaUrl": source_media_url or "",
            "parentPostId": parent_post_id,
            "modelConfig": model_config,
            "sourceKind": "image",
            "forceVideo": True,
        }
        expression = f"""
(async () => {{
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const config = {json.dumps(hook_config, ensure_ascii=False)};
  const fileName = {json.dumps(file_name)};
  const mimeType = {json.dumps(mime_type)};
  const fallbackB64 = {json.dumps(file_b64)};
  const report = {{
    ok: false,
    href: location.href,
    title: document.title,
    steps: [],
    errors: [],
    inputCount: 0,
    dropCount: 0,
    promptSet: false,
    hookInstalled: false,
    fileAttached: false,
    buttonText: "",
    buttonAria: "",
    click: null
  }};
  const push = (step, detail) => report.steps.push({{ step, detail: detail || "" }});
  const visible = (el) => {{
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 1 && rect.height > 1 && style.visibility !== "hidden" && style.display !== "none";
  }};
  const textOf = (el) => String(el?.innerText || el?.textContent || el?.value || "").trim();
  const ariaOf = (el) => String(el?.getAttribute?.("aria-label") || el?.getAttribute?.("title") || "").trim();
  const isTextEditable = (el) => {{
    if (!el) return false;
    const tag = String(el.tagName || "").toLowerCase();
    return tag === "textarea"
      || (tag === "input" && !/file|checkbox|radio|button|submit|hidden/i.test(String(el.type || "")))
      || el.isContentEditable
      || el.getAttribute("contenteditable") !== null
      || el.getAttribute("role") === "textbox";
  }};
  const setText = (el, value) => {{
    el.focus();
    if (el.isContentEditable || el.getAttribute("contenteditable") !== null || el.getAttribute("role") === "textbox") {{
      try {{
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(el);
        selection.removeAllRanges();
        selection.addRange(range);
      }} catch (_error) {{}}
      let inserted = false;
      try {{
        inserted = document.execCommand("insertText", false, value);
      }} catch (_error) {{}}
      if (!inserted || !textOf(el).includes(String(value).slice(0, Math.min(12, String(value).length)))) {{
        el.textContent = value;
      }}
      el.dispatchEvent(new InputEvent("beforeinput", {{ bubbles: true, cancelable: true, inputType: "insertText", data: value }}));
      el.dispatchEvent(new InputEvent("input", {{ bubbles: true, inputType: "insertText", data: value }}));
      el.dispatchEvent(new Event("change", {{ bubbles: true }}));
      return;
    }}
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set
      || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    if (setter) setter.call(el, value);
    else el.value = value;
    el.dispatchEvent(new InputEvent("input", {{ bubbles: true, inputType: "insertText", data: value }}));
    el.dispatchEvent(new Event("change", {{ bubbles: true }}));
  }};
  const findTextarea = () => {{
    const all = Array.from(document.querySelectorAll(
      "textarea, input:not([type]), input[type='text'], [contenteditable='true'], [contenteditable=''], [role='textbox'], .ProseMirror"
    )).filter((el) => isTextEditable(el));
    return all.find((el) => /make\\s+a\\s+video|ask\\s+grok|ask\\s+anything|prompt|비디오|동영상/i.test(`${{ariaOf(el)}} ${{textOf(el)}}`) && visible(el))
      || all.find((el) => visible(el))
      || all[0]
      || null;
  }};
  const selectVideoMode = async () => {{
    const controls = Array.from(document.querySelectorAll("button, [role='button']"));
    const videoButton = controls.find((el) => visible(el) && /^(비디오|Video)$/i.test(textOf(el) || ariaOf(el)));
    if (!videoButton) {{
      push("video-tab-not-found");
      return false;
    }}
    videoButton.scrollIntoView({{ block: "center", inline: "center" }});
    await sleep(150);
    videoButton.click();
    push("video-tab-clicked", textOf(videoButton) || ariaOf(videoButton));
    await sleep(850);
    return true;
  }};
  const buttonScore = (button, inputEl) => {{
    if (!button || !visible(button)) return -1000;
    if (button.disabled || button.getAttribute("aria-disabled") === "true") return -100;
    const label = `${{ariaOf(button)}} ${{textOf(button)}}`;
    let score = 0;
    if (/make\\s+video/i.test(label)) score += 160;
    if (/send|generate|create|submit|arrow|전송|생성|만들/i.test(label)) score += 70;
    if (/비디오|동영상|생성|만들/i.test(label)) score += 35;
    if (/close|cancel|delete|back|login|sign|save|저장|history|project|template/i.test(label)) score -= 140;
    if (button.type === "submit") score += 25;
    const rect = button.getBoundingClientRect();
    if (inputEl) {{
      const inputRect = inputEl.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const nearX = cx >= inputRect.left - 30 && cx <= inputRect.right + 100;
      const nearY = cy >= inputRect.top - 40 && cy <= inputRect.bottom + 80;
      if (nearX && nearY) score += 95;
      if (nearX && nearY && !label.trim()) score += 45;
      if (nearX && nearY && rect.width <= 72 && rect.height <= 72) score += 25;
    }}
    if (rect.bottom > window.innerHeight - 240) score += 15;
    if (rect.right > window.innerWidth / 2) score += 8;
    return score;
  }};
  const findMakeVideoButton = (inputEl) => {{
    const exact = document.querySelector('button[aria-label="Make video"]');
    if (exact && buttonScore(exact, inputEl) > 0) return exact;
    const buttons = Array.from(document.querySelectorAll("button, [role='button']"));
    return buttons.map((button) => [buttonScore(button, inputEl), button])
      .sort((a, b) => b[0] - a[0])[0]?.[1] || null;
  }};
  const installHook = () => {{
    window.__grokStudioI2VConfig = config;
    window.__grokStudioI2VStartedAt = performance.now();
    window.__grokStudioI2VLastRequest = null;
    window.__grokStudioI2VLastResponse = null;
    window.__grokStudioI2VHookError = "";
    const hookVersion = "v10-i2v-official-ui";
    if (!window.__grokStudioOriginalFetch) {{
      window.__grokStudioOriginalFetch = window.fetch.bind(window);
    }}
    if (window.__grokStudioI2VHookVersion !== hookVersion) {{
      window.fetch = async function(input, init) {{
        const active = window.__grokStudioI2VConfig || {{}};
        let requestArgs = init ? {{ ...init }} : undefined;
        let bodyText = null;
        let isRequest = input instanceof Request;
        const url = String(isRequest ? input.url : input || "");
        let trackedRequest = false;
        let trackedRequestId = "";
        try {{
          if (/\\/rest\\/app-chat\\/conversations\\/new|\\/rest\\/app-chat\\/conversation/i.test(url)) {{
            if (requestArgs && typeof requestArgs.body === "string") {{
              bodyText = requestArgs.body;
            }} else if (isRequest) {{
              bodyText = await input.clone().text();
            }}
            if (bodyText) {{
              const json = JSON.parse(bodyText);
              const message = typeof json.message === "string" ? json.message : String(active.prompt || "");
              const sourceUrl = String(active.sourceMediaUrl || "");
              const hasVideoConfig = !!json.responseMetadata?.modelConfigOverride?.modelMap?.videoGenModelConfig;
              const isVideo = json.modelName === "imagine-video-gen"
                || hasVideoConfig
                || /video/i.test(String(json.modelName || ""))
                || /make\\s+a?\\s*video|비디오|동영상/i.test(message)
                || !!active.forceVideo
                || !!active.parentPostId;
              if (isVideo) {{
                json.modelName = "imagine-video-gen";
                json.responseMetadata = json.responseMetadata || {{}};
                json.responseMetadata.modelConfigOverride = json.responseMetadata.modelConfigOverride || {{}};
                json.responseMetadata.modelConfigOverride.modelMap = json.responseMetadata.modelConfigOverride.modelMap || {{}};
                const map = json.responseMetadata.modelConfigOverride.modelMap;
                const videoConfig = {{
                  ...(map.videoGenModelConfig || {{}}),
                  ...(active.modelConfig || {{}}),
                  isReferenceToVideo: false,
                  isVideoEdit: false
                }};
                if (active.parentPostId) videoConfig.parentPostId = active.parentPostId;
                map.videoGenModelConfig = videoConfig;
                const cleanMessage = !sourceUrl || message.includes(sourceUrl)
                  ? message
                  : `${{sourceUrl}} ${{message || active.prompt || ""}}`;
                json.message = /--mode=custom/.test(cleanMessage) ? cleanMessage : `${{cleanMessage}} --mode=custom`;
                json.enableSideBySide = true;
                json.requestId = String(active.requestId || json.requestId || crypto.randomUUID());
                window.__grokStudioI2VLastRequest = {{
                  at: Date.now(),
                  url,
                  requestId: active.requestId,
                  parentPostId: active.parentPostId,
                  sourceMediaUrl: active.sourceMediaUrl,
                  modelConfig: map.videoGenModelConfig,
                  messageLength: String(json.message || "").length
                }};
                window.__grokStudioI2VLastResponse = null;
                trackedRequest = true;
                trackedRequestId = String(active.requestId || "");
                const newBody = JSON.stringify(json);
                if (isRequest) input = new Request(input, {{ body: newBody }});
                else requestArgs = {{ ...(requestArgs || {{}}), body: newBody }};
              }}
            }}
          }}
        }} catch (error) {{
          window.__grokStudioI2VHookError = String((error && error.message) || error);
        }}
        try {{
          const response = await window.__grokStudioOriginalFetch(input, requestArgs);
          let responseText = "";
          let responseReadError = "";
          if (trackedRequest) {{
            try {{
              responseText = await response.clone().text();
            }} catch (error) {{
              responseReadError = String((error && error.message) || error);
            }}
          }}
          if (trackedRequest) {{
            const record = {{
              at: Date.now(),
              requestId: trackedRequestId,
              url,
              ok: !!response.ok,
              status: response.status,
              statusText: response.statusText || "",
              contentType: response.headers.get("content-type") || "",
              body: "",
              bodyLength: 0,
              errorText: "",
              readError: ""
            }};
            if (responseReadError) {{
              record.readError = responseReadError;
            }} else {{
              const text = responseText || "";
              record.bodyLength = text.length;
              record.body = text.slice(0, 5000);
              try {{
                const parsed = JSON.parse(text);
                const errorValue = parsed?.error?.message
                  || parsed?.errorMessage
                  || parsed?.error
                  || parsed?.message
                  || parsed?.detail
                  || "";
                if (errorValue) record.errorText = String(errorValue).slice(0, 1000);
              }} catch (_jsonError) {{}}
            }}
            window.__grokStudioI2VLastResponse = record;
          }}
          return response;
        }} catch (error) {{
          if (trackedRequest) {{
            window.__grokStudioI2VLastResponse = {{
              at: Date.now(),
              requestId: trackedRequestId,
              url,
              ok: false,
              status: 0,
              statusText: "",
              contentType: "",
              body: "",
              bodyLength: 0,
              errorText: "",
              networkError: String((error && error.message) || error)
            }};
          }}
          throw error;
        }}
      }};
      window.__grokStudioI2VHookVersion = hookVersion;
    }}
    report.hookInstalled = true;
    push("hook-installed");
  }};
  const makeFile = async () => {{
    if (config.sourceMediaUrl) {{
      try {{
        const response = await fetch(config.sourceMediaUrl, {{ credentials: "include", cache: "no-store" }});
        if (response.ok) {{
          const blob = await response.blob();
          if (blob && blob.size) {{
            push("source-url-fetched", `${{blob.type || "unknown"}} ${{blob.size}}`);
            return new File([blob], fileName, {{ type: blob.type || mimeType }});
          }}
        }}
        report.errors.push(`source fetch HTTP ${{response.status}}`);
      }} catch (error) {{
        report.errors.push(`source fetch: ${{String((error && error.message) || error)}}`);
      }}
    }}
    if (fallbackB64) {{
      const chunks = [];
      for (let i = 0; i < fallbackB64.length; i += 32768) {{
        const bin = atob(fallbackB64.slice(i, i + 32768));
        const bytes = new Uint8Array(bin.length);
        for (let j = 0; j < bin.length; j += 1) bytes[j] = bin.charCodeAt(j);
        chunks.push(bytes);
      }}
      push("source-b64-loaded", `${{fallbackB64.length}} chars`);
      return new File(chunks, fileName, {{ type: mimeType }});
    }}
    return null;
  }};
  const attachFile = async (file) => {{
    if (!file) {{
      push("file-not-attached");
      return false;
    }}
    const data = new DataTransfer();
    data.items.add(file);
    const inputs = Array.from(document.querySelectorAll("input[type='file']"));
    report.inputCount = inputs.length;
    for (const input of inputs) {{
      try {{
        input.files = data.files;
      }} catch (_error) {{
        try {{ Object.defineProperty(input, "files", {{ value: data.files, configurable: true }}); }} catch (error) {{ report.errors.push(`input files: ${{error.message || error}}`); }}
      }}
      input.dispatchEvent(new Event("input", {{ bubbles: true }}));
      input.dispatchEvent(new Event("change", {{ bubbles: true }}));
    }}
    const targets = Array.from(new Set([
      findTextarea(),
      document.querySelector("main"),
      document.querySelector("[role='main']"),
      ...Array.from(document.querySelectorAll("[aria-label*='image' i], [aria-label*='upload' i], [aria-label*='attach' i], [data-testid*='upload' i]")),
      document.body
    ].filter(Boolean)));
    for (const target of targets) {{
      try {{
        for (const type of ["dragenter", "dragover", "drop"]) {{
          target.dispatchEvent(new DragEvent(type, {{ bubbles: true, cancelable: true, dataTransfer: data }}));
        }}
        report.dropCount += 1;
      }} catch (error) {{
        report.errors.push(`drop: ${{error.message || error}}`);
      }}
    }}
    push("file-attached", `${{inputs.length}} inputs, ${{report.dropCount}} drops`);
    report.fileAttached = true;
    return true;
  }};
  installHook();
  for (let i = 0; i < 80 && document.readyState === "loading"; i += 1) await sleep(250);
  await selectVideoMode();
  const file = await makeFile();
  await attachFile(file);
  await sleep(1200);
  let textArea = null;
  for (let i = 0; i < 50; i += 1) {{
    textArea = findTextarea();
    if (textArea) break;
    await sleep(300);
  }}
  if (!textArea) {{
    report.reason = "text-input-not-found";
    return report;
  }}
  textArea.focus();
  setText(textArea, config.prompt || "");
  report.promptSet = true;
  push("prompt-set");
  let button = null;
  for (let i = 0; i < 70; i += 1) {{
    button = findMakeVideoButton(textArea);
    if (button && buttonScore(button, textArea) > 0 && !button.disabled && button.getAttribute("aria-disabled") !== "true") break;
    await sleep(400);
  }}
  if (!button || buttonScore(button, textArea) <= 0 || button.disabled || button.getAttribute("aria-disabled") === "true") {{
    report.reason = "make-video-button-not-ready";
    report.bodyText = String(document.body?.innerText || "").slice(0, 1500);
    return report;
  }}
  button.scrollIntoView({{ block: "center", inline: "center" }});
  await sleep(250);
  const rect = button.getBoundingClientRect();
  window.__grokStudioI2VLastButton = button;
  window.__grokStudioI2VClick = () => {{
    const btn = window.__grokStudioI2VLastButton;
    if (!btn) return false;
    btn.click();
    return true;
  }};
  window.__grokStudioI2VSubmitSnapshot = () => {{
    const input = findTextarea();
    if (input && config.prompt) {{
      const existing = textOf(input);
      if (!existing || !existing.includes(String(config.prompt).slice(0, Math.min(12, String(config.prompt).length)))) {{
        setText(input, config.prompt || "");
      }}
    }}
    const btn = findMakeVideoButton(input);
    if (!btn) {{
      return {{
        ok: false,
        reason: "button-not-found",
        lastRequest: window.__grokStudioI2VLastRequest || null,
        lastResponse: window.__grokStudioI2VLastResponse || null,
        hookError: window.__grokStudioI2VHookError || "",
        bodyText: String(document.body?.innerText || "").slice(0, 1500)
      }};
    }}
    btn.scrollIntoView({{ block: "center", inline: "center" }});
    const rectNow = btn.getBoundingClientRect();
    window.__grokStudioI2VLastButton = btn;
    return {{
      ok: buttonScore(btn, input) > 0 && !btn.disabled && btn.getAttribute("aria-disabled") !== "true",
      disabled: !!btn.disabled || btn.getAttribute("aria-disabled") === "true",
      score: buttonScore(btn, input),
      buttonText: textOf(btn).slice(0, 120),
      buttonAria: ariaOf(btn).slice(0, 120),
      lastRequest: window.__grokStudioI2VLastRequest || null,
      lastResponse: window.__grokStudioI2VLastResponse || null,
      hookError: window.__grokStudioI2VHookError || "",
      click: {{
        x: Math.max(1, Math.min(window.innerWidth - 1, rectNow.left + rectNow.width / 2)),
        y: Math.max(1, Math.min(window.innerHeight - 1, rectNow.top + rectNow.height / 2))
      }}
    }};
  }};
  report.ok = true;
  report.buttonText = textOf(button).slice(0, 120);
  report.buttonAria = ariaOf(button).slice(0, 120);
  report.click = {{
    x: Math.max(1, Math.min(window.innerWidth - 1, rect.left + rect.width / 2)),
    y: Math.max(1, Math.min(window.innerHeight - 1, rect.top + rect.height / 2))
  }};
  return report;
}})()
"""
        value = cdp_evaluate(expression, timeout=60)
        return value if isinstance(value, dict) else {"ok": False, "reason": "non-dict-prepare-result"}

    def submit_prepared_official_i2v_ui(
        self,
        request_id: str,
        prepare: dict[str, Any],
        event_prefix: str,
    ) -> dict[str, Any]:
        attempts: list[dict[str, Any]] = []
        click = prepare.get("click") if isinstance(prepare.get("click"), dict) else {}
        for attempt in range(1, 4):
            if not click:
                snapshot = cdp_evaluate(
                    "window.__grokStudioI2VSubmitSnapshot && window.__grokStudioI2VSubmitSnapshot()",
                    timeout=8,
                )
                if isinstance(snapshot, dict):
                    attempts.append({"attempt": attempt, "snapshot": snapshot})
                    click = snapshot.get("click") if isinstance(snapshot.get("click"), dict) else {}
            clicked = False
            if click:
                try:
                    cdp_click_point(float(click.get("x")), float(click.get("y")))
                    clicked = True
                except Exception as exc:
                    attempts.append({"attempt": attempt, "cdp_click_error": str(exc)[:500]})
            if not clicked:
                try:
                    fallback_clicked = cdp_evaluate(
                        "window.__grokStudioI2VClick && window.__grokStudioI2VClick()",
                        timeout=8,
                    )
                    attempts.append({"attempt": attempt, "fallback_clicked": bool(fallback_clicked)})
                except StudioError as exc:
                    attempts.append({"attempt": attempt, "fallback_click_error": exc.message[:500]})

            verify_expression = f"""
(async () => {{
  const requestId = {json.dumps(request_id)};
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const started = Date.now();
  let sawRequest = null;
  for (let i = 0; i < 24; i += 1) {{
    const last = window.__grokStudioI2VLastRequest || null;
    const response = window.__grokStudioI2VLastResponse || null;
    if (last && last.requestId === requestId && Number(last.at || 0) >= started - 4000) sawRequest = last;
    if (response && response.requestId === requestId && Number(response.at || 0) >= started - 4000) {{
      const errorText = String(response.errorText || response.networkError || response.readError || "");
      const failed = response.ok === false || !!errorText;
      return {{
        ok: !failed,
        responseFailed: failed,
        waitedMs: Date.now() - started,
        lastRequest: sawRequest || last,
        lastResponse: response,
        hookError: window.__grokStudioI2VHookError || ""
      }};
    }}
    await sleep(500);
  }}
  const snapshot = window.__grokStudioI2VSubmitSnapshot ? window.__grokStudioI2VSubmitSnapshot() : null;
  if (sawRequest) {{
    return {{
      ok: true,
      responsePending: true,
      waitedMs: Date.now() - started,
      lastRequest: sawRequest,
      lastResponse: window.__grokStudioI2VLastResponse || null,
      hookError: window.__grokStudioI2VHookError || "",
      snapshot
    }};
  }}
  return {{
    ok: false,
    waitedMs: Date.now() - started,
    lastRequest: window.__grokStudioI2VLastRequest || null,
    lastResponse: window.__grokStudioI2VLastResponse || null,
    hookError: window.__grokStudioI2VHookError || "",
    snapshot,
    bodyText: String(document.body?.innerText || "").slice(0, 1500)
  }};
}})()
"""
            verify = cdp_evaluate(verify_expression, timeout=18)
            verify = verify if isinstance(verify, dict) else {"ok": False, "reason": "non-dict-verify"}
            attempts.append({"attempt": attempt, "verify": verify})
            if verify.get("responseFailed"):
                response = verify.get("lastResponse") if isinstance(verify.get("lastResponse"), dict) else {}
                status = response.get("status")
                status_text = str(response.get("statusText") or "")
                error_text = str(response.get("errorText") or response.get("networkError") or response.get("readError") or "")
                body = str(response.get("body") or "")
                detail = error_text or body[:1200] or "no response body"
                self.write_media_debug(
                    f"{event_prefix}_submit_response_failed",
                    {
                        "request_id": request_id,
                        "attempt": attempt,
                        "response": response,
                        "attempts": attempts,
                    },
                )
                raise StudioError(
                    f"Imagine official page server response failed: {status or 0} {status_text}. {detail[:1200]}",
                    int(status) if isinstance(status, int) and status >= 400 else 502,
                )
            if verify.get("ok"):
                self.write_media_debug(
                    f"{event_prefix}_submit_verified",
                    {
                        "request_id": request_id,
                        "attempt": attempt,
                        "verify": verify,
                    },
                )
                return verify
            snapshot = verify.get("snapshot") if isinstance(verify.get("snapshot"), dict) else {}
            click = snapshot.get("click") if isinstance(snapshot.get("click"), dict) else {}

        self.write_media_debug(
            f"{event_prefix}_submit_failed",
            {
                "request_id": request_id,
                "attempts": attempts,
            },
        )
        raise StudioError(
            "Imagine official page did not start video generation after submit. "
            "The source media may be attached, but no Imagine generation request was sent.",
            502,
        )

    def is_current_page_generated_video_url(self, url: str, scan: dict[str, Any]) -> bool:
        location = scan.get("location") if isinstance(scan.get("location"), str) else ""
        if "/imagine/post/" not in location:
            return False
        post_id = extract_uuid_from_text(location)
        if not post_id:
            return False
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower()
        path = urllib.parse.unquote(parsed.path).lower()
        return (
            host == "assets.grok.com"
            and f"/generated/{post_id.lower()}/generated_video" in path
            and path.endswith(media_extensions("video"))
        )

    def scan_chrome_video_page(
        self,
        request_id: str,
        ignore_urls: set[str] | None = None,
        baseline_only: bool = False,
    ) -> dict[str, Any] | None:
        expression = f"""
(async () => {{
  const maxBlobBytes = {MAX_BODY};
  const urls = [];
  const blobUrls = [];
  const blobErrors = [];
  const add = (value) => {{
    if (!value || typeof value !== "string") return;
    let clean = value.trim();
    if (!clean) return;
    try {{
      clean = new URL(clean, location.href).href;
    }} catch (_error) {{}}
    if (clean.startsWith("blob:")) {{
      blobUrls.push(clean);
    }} else if (/^https?:\\/\\//i.test(clean)) {{
      urls.push(clean);
    }}
  }};
  const attrs = ["src", "href", "poster", "data-src", "data-url", "data-media-url", "data-video-url"];
  document
    .querySelectorAll("video, source, a, [src], [href], [poster], [data-src], [data-url], [data-media-url], [data-video-url]")
    .forEach((el) => {{
      if (el.currentSrc) add(el.currentSrc);
      for (const attr of attrs) add(el.getAttribute(attr));
    }});
  for (const entry of performance.getEntriesByType("resource")) add(entry.name);
  const videos = Array.from(document.querySelectorAll("video")).map((video) => ({{
    src: video.getAttribute("src") || "",
    currentSrc: video.currentSrc || "",
    readyState: video.readyState,
    networkState: video.networkState,
    duration: Number.isFinite(video.duration) ? video.duration : null,
    width: video.videoWidth || 0,
    height: video.videoHeight || 0
  }}));
  const progressCandidates = [];
  const addProgressText = (text) => {{
    if (!text || typeof text !== "string") return;
    for (const match of text.matchAll(/(?:^|[^0-9])([0-9]{{1,3}})\\s*%/g)) {{
      const value = Number(match[1]);
      if (Number.isFinite(value) && value > 0 && value < 100) progressCandidates.push(value);
    }}
  }};
  const isVisible = (el) => {{
    const style = window.getComputedStyle(el);
    if (!style || style.visibility === "hidden" || style.display === "none" || Number(style.opacity || 1) === 0) return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }};
  document.querySelectorAll("body *").forEach((el) => {{
    if (!isVisible(el)) return;
    const text = (el.innerText || el.textContent || "").trim();
    if (text && text.length <= 140) addProgressText(text);
  }});
  if (!progressCandidates.length) addProgressText((document.body && document.body.innerText) || "");
  const progress = progressCandidates.length ? Math.max(...progressCandidates) : null;
  let blobPayload = null;
  for (const url of Array.from(new Set(blobUrls))) {{
    try {{
      const response = await fetch(url);
      const blob = await response.blob();
      if (!blob || !blob.size || blob.size > maxBlobBytes) continue;
      const dataUri = await new Promise((resolve, reject) => {{
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(reader.error || new Error("blob read failed"));
        reader.readAsDataURL(blob);
      }});
      blobPayload = {{
        url,
        mime_type: blob.type || "video/mp4",
        size: blob.size,
        data_uri: dataUri
      }};
      break;
    }} catch (error) {{
      blobErrors.push(String((error && error.message) || error));
    }}
  }}
  return {{
    title: document.title,
    location: location.href,
    urls: Array.from(new Set(urls)).slice(-250),
    blob_urls: Array.from(new Set(blobUrls)).slice(-20),
    blob: blobPayload,
    blob_errors: blobErrors.slice(-5),
    videos,
    progress,
    progress_candidates: Array.from(new Set(progressCandidates)).sort((a, b) => b - a).slice(0, 8),
    at: Date.now()
  }};
}})()
"""
        try:
            value = cdp_evaluate(expression, timeout=12)
        except StudioError as exc:
            self.write_media_debug(
                "handoff_page_scan_error",
                {
                    "request_id": request_id,
                    "error": exc.message[:500],
                },
            )
            return None
        if not isinstance(value, dict):
            return None
        debug_value = dict(value)
        raw_debug_urls = debug_value.get("urls")
        if isinstance(raw_debug_urls, list):
            debug_value["url_count"] = len(raw_debug_urls)
            debug_value["urls"] = [debug_media_url(str(url)) for url in raw_debug_urls[-40:] if isinstance(url, str)]
        blob_debug = debug_value.get("blob")
        if isinstance(blob_debug, dict):
            debug_value["blob"] = {
                key: (f"<{len(val)} chars>" if key == "data_uri" and isinstance(val, str) else val)
                for key, val in blob_debug.items()
            }
        urls = extract_media_urls(value, "video")
        if ignore_urls:
            urls = [url for url in urls if url not in ignore_urls or self.is_current_page_generated_video_url(url, value)]
        self.write_media_debug(
            "handoff_page_scan_baseline" if baseline_only else "handoff_page_scan",
            {
                "request_id": request_id,
                "candidate_count": len(urls),
                "progress": value.get("progress"),
                "progress_candidates": value.get("progress_candidates"),
                "candidates": [debug_media_url(url) for url in urls[:12]],
                "scan": debug_value,
            },
        )
        if baseline_only:
            return {"baseline_urls": urls, "scan": debug_value}
        session = read_imagine_session()
        if urls:
            confirmed_urls: list[str] = []
            for index, url in enumerate(urls[:8], start=1):
                if self.probe_imagine_media_url(url, "video", session):
                    confirmed_urls.append(url)
            if not confirmed_urls:
                return None
            return {
                "scan": debug_value,
                "video": {"url": confirmed_urls[0], "candidate_urls": confirmed_urls},
                "provider": "imagine",
                "model": imagine_model_name("video"),
            }
        blob = value.get("blob") if isinstance(value.get("blob"), dict) else {}
        data_uri = blob.get("data_uri") if isinstance(blob, dict) else None
        if isinstance(data_uri, str) and data_uri.startswith("data:video/"):
            return {
                "scan": debug_value,
                "video": {
                    "url": str(blob.get("url") or f"imagine-official-page:{request_id}"),
                    "data_uri": data_uri,
                    "mime_type": str(blob.get("mime_type") or "video/mp4"),
                },
                "provider": "imagine",
                "model": imagine_model_name("video"),
            }
        progress = value.get("progress")
        if isinstance(progress, (int, float)) and progress > 0:
            return {
                "scan": debug_value,
                "progress": max(1, min(99, int(progress))),
                "provider": "imagine",
                "model": imagine_model_name("video"),
            }
        return None

    def watch_chrome_for_video(self, request_id: str, job_id: str | None) -> dict[str, Any]:
        target = find_imagine_cdp_target(IMAGINE_DEBUG_PORT)
        ws_url = str(target.get("webSocketDebuggerUrl") or "")
        ws = RawWebSocket(ws_url, timeout=5)
        started = time.monotonic()
        deadline = started + IMAGINE_VIDEO_HANDOFF_SECONDS
        hard_deadline = started + max(IMAGINE_VIDEO_HANDOFF_SECONDS, IMAGINE_VIDEO_MAX_WAIT_SECONDS)
        next_scan = 0.0
        baseline_urls: set[str] = set()
        session = read_imagine_session()
        official_progress: int | None = None
        official_progress_seen_at: float | None = None
        official_progress_changed_at: float | None = None

        def note_official_progress(progress: Any, now: float) -> None:
            nonlocal deadline, official_progress, official_progress_seen_at, official_progress_changed_at
            if not isinstance(progress, (int, float)):
                return
            value = max(1, min(99, int(progress)))
            if official_progress_seen_at is None:
                official_progress_seen_at = now
            if value != official_progress:
                official_progress = value
                official_progress_changed_at = now
                log_event(f"Imagine official page progress request_id={request_id} progress={value}")
            deadline = min(hard_deadline, max(deadline, now + max(30.0, IMAGINE_VIDEO_PROGRESS_GRACE_SECONDS)))
            if job_id:
                self.jobs.update(job_id, status="processing", progress=value, request_id=request_id)

        try:
            sequence = 1
            for method in ("Network.enable", "Runtime.enable"):
                ws.send_json({"id": sequence, "method": method})
                sequence += 1
            baseline_deadline = time.monotonic() + max(0.0, IMAGINE_VIDEO_BASELINE_SECONDS)
            while time.monotonic() < baseline_deadline:
                if job_id:
                    self.raise_if_cancelled(job_id)
                    self.jobs.update(job_id, status="processing", progress=10, request_id=request_id)
                baseline = self.scan_chrome_video_page(request_id, baseline_only=True)
                if isinstance(baseline, dict):
                    for url in baseline.get("baseline_urls") or []:
                        if isinstance(url, str):
                            baseline_urls.add(url)
                    scan = baseline.get("scan") if isinstance(baseline.get("scan"), dict) else {}
                    note_official_progress(scan.get("progress"), time.monotonic())
                time.sleep(1)
            while time.monotonic() < min(deadline, hard_deadline):
                now = time.monotonic()
                if job_id:
                    self.raise_if_cancelled(job_id)
                    if official_progress is None:
                        elapsed = now - started
                        span = max(1.0, IMAGINE_VIDEO_HANDOFF_SECONDS)
                        self.jobs.update(job_id, status="processing", progress=min(88, 12 + int(elapsed * 60 / span)), request_id=request_id)
                if now >= next_scan:
                    scanned = self.scan_chrome_video_page(request_id, baseline_urls)
                    if isinstance(scanned, dict):
                        note_official_progress(scanned.get("progress"), now)
                    if scanned and isinstance(scanned.get("video"), dict):
                        log_event(f"Imagine official handoff captured video from page scan request_id={request_id}")
                        return scanned
                    next_scan = now + max(0.5, IMAGINE_VIDEO_PAGE_SCAN_SECONDS)
                wait_deadline = min(deadline, hard_deadline)
                wait = max(0.1, min(1.0, next_scan - time.monotonic(), wait_deadline - time.monotonic()))
                readable, _, _ = select.select([ws.socket], [], [], wait)
                if not readable:
                    continue
                try:
                    message = ws.recv_text()
                except (OSError, TimeoutError, StudioError):
                    continue
                if message is None:
                    break
                try:
                    parsed: Any = json.loads(message)
                except json.JSONDecodeError:
                    parsed = {"message": message}
                method = parsed.get("method") if isinstance(parsed, dict) else ""
                if method not in {
                    "Network.responseReceived",
                    "Network.webSocketFrameReceived",
                    "Network.webSocketFrameSent",
                    "Network.loadingFinished",
                    "Runtime.consoleAPICalled",
                }:
                    continue
                video_urls = [url for url in extract_media_urls(parsed, "video") if url not in baseline_urls]
                confirmed_urls: list[str] = []
                for index, url in enumerate(video_urls[:6], start=1):
                    if self.probe_imagine_media_url(url, "video", session):
                        confirmed_urls.append(url)
                if confirmed_urls:
                    log_event(f"Imagine official handoff captured video request_id={request_id}")
                    return {
                        "event": parsed,
                        "video": {"url": confirmed_urls[0], "candidate_urls": confirmed_urls},
                        "provider": "imagine",
                        "model": imagine_model_name("video"),
                    }
        finally:
            ws.close()
        if official_progress is not None:
            stale_seconds = int(time.monotonic() - (official_progress_changed_at or official_progress_seen_at or started))
            raise StudioError(
                f"Timed out waiting for the Imagine official page video result. Official page was still at {official_progress}% for about {stale_seconds}s.",
                504,
            )
        raise StudioError("Timed out waiting for the Imagine official page video result. If the video is visible in Imagine, keep that window open and try once more.", 504)

    def _save_imagine_video_data_result(
        self,
        data_uri: str,
        mime_type: str,
        source_url: str,
        payload: dict[str, Any],
        prompt: str,
        mode: str,
        request_id: str,
        raw: dict[str, Any],
        session: dict[str, Any],
        parent_post_id: str | None,
    ) -> dict[str, Any]:
        media_bytes, parsed_mime = data_uri_to_bytes(data_uri)
        mime = parsed_mime or mime_type or "video/mp4"
        item_id = uuid.uuid4().hex
        stem = f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{mode}-{item_id[:8]}"
        video_dir = self.library.gallery_output_dir(payload.get("gallery_folder_id"), "Video")
        path = unique_path(video_dir / f"{stem}{guess_ext(mime, '.mp4')}")
        path.write_bytes(media_bytes)
        metadata_payload = {
            "provider": "imagine",
            "token_source": "imagine",
            "request_id": request_id,
            "video_url": source_url,
            "parent_post_id": parent_post_id,
            "raw": scrub_inline_media_for_metadata(raw),
        }
        metadata_path = self.write_metadata(item_id, metadata_payload)
        group_id = str(payload.get("group_id") or payload.get("parent_id") or item_id)
        item = {
            "id": item_id,
            "type": "video",
            "mode": "imagine-video",
            "title": "Video",
            "prompt": prompt,
            "category": payload.get("category") or "Video",
            "tags": normalize_tags(payload.get("tags")),
            "created_at": utc_now(),
            "local_url": self.library.media_url(path),
            "file": str(path),
            "mime": mime,
            "remote_url": source_url,
            "request_id": request_id,
            "provider": "imagine",
            "token_source": "imagine",
            "metadata_file": str(metadata_path),
            "metadata": {
                "group_id": group_id,
                "parent_id": payload.get("parent_id") or payload.get("image_item_id"),
                "gallery_folder_id": payload.get("gallery_folder_id"),
                "provider": "imagine",
                "token_source": "imagine",
                "model": imagine_model_name("video"),
                "duration": payload.get("duration"),
                "aspect_ratio": payload.get("aspect_ratio"),
                "resolution": payload.get("resolution"),
                "start_image": source_reference_metadata(payload.get("image")),
                "imagine": compact(
                    {
                        "parent_post_id": parent_post_id,
                        "account_id": session.get("id"),
                        "account_email": session.get("email") or session.get("label"),
                        "generated": True,
                    }
                ),
            },
        }
        return self.library.add_item(item)

    def official_page_auto_image_to_video(
        self,
        payload: dict[str, Any],
        prompt: str,
        request_id: str,
        resolution: str,
        duration: int,
        parent_post_id: str | None,
        model_config: dict[str, Any],
        job_id: str | None,
        source_media_url: str | None,
        session: dict[str, Any],
    ) -> dict[str, Any]:
        if job_id:
            self.jobs.update(job_id, status="processing", progress=8, request_id=request_id)
            self.raise_if_cancelled(job_id)
        self.open_imagine_chrome_page(IMAGINE_BASE + "/imagine")
        time.sleep(2.0)
        source_file = self.handoff_image_file(payload)
        if not source_file and not source_media_url:
            self.close_imagine_chrome_when_idle(job_id)
            raise StudioError("Select a local image result or upload a source image for Imagine image-to-video.", 400)
        try:
            prepare = self.prepare_official_i2v_ui(
                prompt,
                source_media_url,
                parent_post_id,
                model_config,
                source_file,
                request_id,
            )
        except Exception:
            self.close_imagine_chrome_when_idle(job_id)
            raise
        debug_prepare = dict(prepare)
        if isinstance(debug_prepare.get("bodyText"), str):
            debug_prepare["bodyText"] = debug_prepare["bodyText"][:500]
        self.write_media_debug(
            "official_ui_i2v_prepare",
            {
                "request_id": request_id,
                "parent_post_id": parent_post_id,
                "source_media_url": debug_media_url(source_media_url or ""),
                "source_file": str(source_file) if source_file else "",
                "prepare": debug_prepare,
            },
        )
        if not prepare.get("ok"):
            self.close_imagine_chrome_when_idle(job_id)
            raise StudioError(
                "Could not prepare Imagine official page image-to-video UI: "
                + str(prepare.get("reason") or prepare.get("errors") or "unknown"),
                502,
            )
        if not prepare.get("fileAttached") and not source_media_url:
            self.close_imagine_chrome_when_idle(job_id)
            raise StudioError(
                "Could not attach the selected local image to Imagine image-to-video. "
                "Try a smaller image or select an Imagine-generated source image.",
                502,
            )
        try:
            submit = self.submit_prepared_official_i2v_ui(request_id, prepare, "official_ui_i2v")
            self.write_media_debug(
                "official_ui_i2v_clicked",
                {
                    "request_id": request_id,
                    "parent_post_id": parent_post_id,
                    "submit": submit,
                },
            )
            raw = self.watch_chrome_for_video(request_id, job_id)
            video = raw.get("video") if isinstance(raw.get("video"), dict) else {}
            data_uri = video.get("data_uri") if isinstance(video, dict) else None
            if isinstance(data_uri, str) and data_uri.startswith("data:video/"):
                return self._save_imagine_video_data_result(
                    data_uri,
                    str(video.get("mime_type") or "video/mp4"),
                    str(video.get("url") or f"imagine-official-page:{request_id}"),
                    payload,
                    prompt,
                    mode="video-generate",
                    request_id=request_id,
                    raw=raw,
                    session=session,
                    parent_post_id=parent_post_id,
                )
            video_url = extract_media_url(raw, "video")
            if not video_url:
                raise StudioError("Imagine official page did not expose a video URL after auto-submit.", 502)
            return self._save_imagine_video_result(video_url, payload, prompt, "video-generate", request_id, raw, session, parent_post_id)
        finally:
            self.close_imagine_chrome_when_idle(job_id)

    def generate_imagine_video(
        self,
        payload: dict[str, Any],
        prompt: str,
        mode: str,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        if mode != "video-generate":
            raise StudioError("Imagine video currently supports new video generation only.", 400)
        session = read_imagine_session()
        if not session or not valid_imagine_cookies(session):
            raise StudioError("Select or capture an Imagine account first.", 401)
        resolution = str(payload.get("resolution") or "720p")
        if resolution not in {"480p", "720p"}:
            resolution = "720p"
        try:
            duration = int(payload.get("duration") or 6)
        except (TypeError, ValueError):
            duration = 6
        duration = max(1, min(15, duration))
        parent_post_id, source_media_url = self.imagine_video_source(payload)
        source_file = self.handoff_image_file(payload)
        if not parent_post_id and not source_file:
            self.write_imagine_media_debug(
                "video_source_missing",
                {
                    "payload_has_image": bool(payload.get("image")),
                    "image_item_id": str(payload.get("image_item_id") or ""),
                    "preview_url": debug_media_url(str(payload.get("preview_url") or "")) if payload.get("preview_url") else None,
                },
            )
            raise StudioError("Select a local image result or upload a source image for Imagine image-to-video.", 400)
        model_config: dict[str, Any] = {
            "aspectRatio": str(payload.get("aspect_ratio") or "16:9"),
            "videoLength": duration,
            "isVideoEdit": False,
            "resolutionName": resolution,
        }
        if parent_post_id:
            model_config["parentPostId"] = parent_post_id
        if source_media_url:
            model_config["isReferenceToVideo"] = True
            model_config["imageReferences"] = [source_media_url]
        request_id = str(uuid.uuid4())
        request = {
            "temporary": True,
            "modelName": imagine_model_name("video"),
            "message": f"{prompt} --mode=custom",
            "enableSideBySide": True,
            "responseMetadata": {
                "experiments": [],
                "modelConfigOverride": {
                    "modelMap": {
                        "videoGenModelConfig": model_config,
                    }
                },
            },
            "requestId": request_id,
        }
        if job_id:
            self.raise_if_cancelled(job_id)
            self.jobs.update(job_id, status="processing", progress=5, request_id=request_id)
        self.write_imagine_media_debug(
            "video_submit",
            {
                "request_id": request_id,
                "parent_post_id": parent_post_id,
                "source_media_url": debug_media_url(source_media_url or "") if source_media_url else None,
                "model_config": model_config,
                "cookies": imagine_cookie_presence(valid_imagine_cookies(session)),
            },
        )
        return self.official_page_auto_image_to_video(
            payload,
            prompt,
            request_id,
            resolution,
            duration,
            parent_post_id,
            model_config,
            job_id,
            source_media_url,
            session,
        )

    def best_imagine_video_url(self, value: Any, session: dict[str, Any]) -> str | None:
        urls = extract_media_urls(value, "video")
        posts = self.extract_media_posts(value)
        for post in posts:
            post_id = str(post.get("id") or "")
            for key in ("hd1080MediaUrl", "hdMediaUrl", "mediaUrl"):
                url = normalize_media_api_url(post.get(key))
                if isinstance(url, str) and url not in urls:
                    urls.append(url)
            for image_url in self.media_post_image_urls(post):
                predicted = predicted_imagine_video_url(image_url, post_id)
                if predicted and predicted not in urls:
                    urls.append(predicted)
        urls = [url for url in urls if is_possible_video_url_candidate(url)]
        urls.sort(key=lambda candidate: media_url_score(candidate, "video"), reverse=True)
        for url in urls[:10]:
            if self.probe_imagine_media_url(url, "video", session):
                return url
        return urls[0] if urls else None

    def _save_imagine_video_result(
        self,
        video_url: str,
        payload: dict[str, Any],
        prompt: str,
        mode: str,
        request_id: str,
        raw: dict[str, Any],
        session: dict[str, Any],
        parent_post_id: str | None,
    ) -> dict[str, Any]:
        media_post_id = extract_first_key(raw, {"mediaPostId", "media_post_id", "postId", "post_id", "id"})
        media_post_error = None
        try:
            media_post = self.create_imagine_video_media_post(video_url, prompt=prompt, session=session)
            media_post_id = str(media_post.get("id") or media_post_id or "")
        except StudioError as exc:
            media_post_error = exc.message[:500]
        media_bytes, mime = self.download_imagine_media(video_url, "video")
        item_id = uuid.uuid4().hex
        stem = f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{mode}-{item_id[:8]}"
        video_dir = self.library.gallery_output_dir(payload.get("gallery_folder_id"), "Video")
        path = unique_path(video_dir / f"{stem}{guess_ext(mime, '.mp4')}")
        path.write_bytes(media_bytes)
        metadata_payload = {
            "provider": "imagine",
            "token_source": "imagine",
            "request_id": request_id,
            "video_url": video_url,
            "parent_post_id": parent_post_id,
            "media_post_id": media_post_id,
            "media_post_error": media_post_error,
            "raw": scrub_inline_media_for_metadata(raw),
        }
        metadata_path = self.write_metadata(item_id, metadata_payload)
        group_id = str(payload.get("group_id") or payload.get("parent_id") or item_id)
        item = {
            "id": item_id,
            "type": "video",
            "mode": "imagine-video",
            "title": "Video",
            "prompt": prompt,
            "category": payload.get("category") or "Video",
            "tags": normalize_tags(payload.get("tags")),
            "created_at": utc_now(),
            "local_url": self.library.media_url(path),
            "file": str(path),
            "mime": mime,
            "remote_url": video_url,
            "request_id": request_id,
            "provider": "imagine",
            "token_source": "imagine",
            "metadata_file": str(metadata_path),
            "metadata": {
                "group_id": group_id,
                "parent_id": payload.get("parent_id") or payload.get("image_item_id"),
                "gallery_folder_id": payload.get("gallery_folder_id"),
                "provider": "imagine",
                "token_source": "imagine",
                "model": imagine_model_name("video"),
                "duration": payload.get("duration"),
                "aspect_ratio": payload.get("aspect_ratio"),
                "resolution": payload.get("resolution"),
                "start_image": source_reference_metadata(payload.get("image")),
                "imagine": compact(
                    {
                        "post_id": media_post_id,
                        "media_url": video_url,
                        "parent_post_id": parent_post_id,
                        "account_id": session.get("id"),
                        "account_email": session.get("email") or session.get("label"),
                        "generated": True,
                        "media_post_registered": bool(media_post_id and not media_post_error),
                        "media_post_error": media_post_error,
                    }
                ),
                "imagine_video_post_id": media_post_id,
                "imagine_video_media_url": video_url,
            },
        }
        return self.library.add_item(item)

    def _save_image_result(
        self,
        entry: dict[str, Any],
        payload: dict[str, Any],
        prompt: str,
        mode: str,
        index: int,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        item_id = uuid.uuid4().hex
        stem = f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{mode}-{index}-{item_id[:8]}"

        if isinstance(entry.get("b64_json"), str):
            media_bytes = base64.b64decode(entry["b64_json"])
            ext = guess_ext(entry.get("mime_type"), ".jpg")
            mime = entry.get("mime_type") or mimetypes.guess_type("x" + ext)[0] or "image/jpeg"
        elif isinstance(entry.get("url"), str):
            if str(entry.get("provider") or result.get("provider") or "").lower() == "imagine":
                media_bytes, mime = self.download_imagine_media(entry["url"], "image")
            else:
                media_bytes, mime = self.download(entry["url"])
            ext = guess_ext(mime, ".jpg")
        else:
            raise StudioError("Image response did not contain a usable image.")

        image_dir = self.library.gallery_output_dir(payload.get("gallery_folder_id"), "Image")
        path = unique_path(image_dir / f"{stem}{ext}")
        path.write_bytes(media_bytes)
        metadata_path = self.write_metadata(item_id, result)
        group_id = str(payload.get("group_id") or payload.get("parent_id") or item_id)
        provider = str(entry.get("provider") or result.get("provider") or payload.get("provider") or "build").lower()
        if provider not in {"build", "imagine"}:
            provider = "build"
        token_source = str(entry.get("token_source") or result.get("token_source") or provider).lower()
        if token_source not in {"build", "imagine"}:
            token_source = provider
        model = entry.get("model") or result.get("model") or payload.get("model") or DEFAULT_IMAGE_MODEL
        item = {
            "id": item_id,
            "type": "image",
            "mode": mode,
            "title": safe_name(prompt[:48], "Image").replace("-", " "),
            "prompt": prompt,
            "category": payload.get("category") or "Image",
            "tags": normalize_tags(payload.get("tags")),
            "created_at": utc_now(),
            "local_url": self.library.media_url(path),
            "file": str(path),
            "mime": mime,
            "provider": provider,
            "token_source": token_source,
            "metadata_file": str(metadata_path),
            "metadata": {
                "group_id": group_id,
                "parent_id": payload.get("parent_id"),
                "gallery_folder_id": payload.get("gallery_folder_id"),
                "provider": provider,
                "token_source": token_source,
                "model": model,
                "aspect_ratio": payload.get("aspect_ratio"),
                "resolution": payload.get("resolution"),
                "source_images": source_references_metadata(payload.get("images") or []),
            },
        }
        if provider == "imagine":
            item["metadata"].update(
                compact(
                    {
                        "imagine_post_id": entry.get("imagine_post_id"),
                        "imagine_image_id": entry.get("imagine_image_id"),
                        "imagine_media_url": entry.get("url"),
                        "imagine_media_post_registered": entry.get("imagine_media_post_registered"),
                        "imagine_media_post_error": entry.get("imagine_media_post_error"),
                        "imagine_account_id": entry.get("imagine_account_id"),
                        "imagine_account_email": entry.get("imagine_account_email"),
                        "is_pro": entry.get("is_pro"),
                        "source": "imagine-generated",
                        "imagine": compact(
                            {
                                "post_id": entry.get("imagine_post_id"),
                                "image_id": entry.get("imagine_image_id"),
                                "media_url": entry.get("url"),
                                "media_post_registered": entry.get("imagine_media_post_registered"),
                                "media_post_error": entry.get("imagine_media_post_error"),
                                "account_id": entry.get("imagine_account_id"),
                                "account_email": entry.get("imagine_account_email"),
                                "generated": True,
                            }
                        ),
                    }
                )
            )
        return self.library.add_item(item)

    def start_video(self, payload: dict[str, Any], mode: str) -> dict[str, Any]:
        prompt = require_text(payload, "prompt")
        job = self.jobs.create(mode, prompt, job_context(payload, mode))
        log_event(
            "queued "
            f"{mode} job={job['id']} prompt_chars={len(prompt)} "
            f"image={'yes' if payload.get('image') else 'no'} "
            f"refs={len(payload.get('reference_images') or [])} "
            f"duration={payload.get('duration') or 'default'}"
        )
        thread = threading.Thread(
            target=self._run_video_job,
            args=(job["id"], payload, mode),
            daemon=True,
        )
        thread.start()
        return job

    def _run_video_job(self, job_id: str, payload: dict[str, Any], mode: str) -> None:
        try:
            self.jobs.update(job_id, status="submitting", progress=1)
            prompt = require_text(payload, "prompt")
            if self.generation_provider() == "imagine" and mode == "video-generate":
                log_event(f"submitting Imagine {mode} job={job_id}")
                item = self.generate_imagine_video(payload, prompt, mode, job_id)
                log_event(f"saved Imagine video job={job_id} file={item.get('file')}")
                self.jobs.update(job_id, status="done", progress=100, item=item)
                return
            request = self._video_payload(payload, mode)
            self.raise_if_cancelled(job_id)
            endpoint = {
                "video-generate": "/videos/generations",
                "video-extend": "/videos/extensions",
                "video-edit": "/videos/edits",
            }[mode]
            log_event(f"submitting {mode} job={job_id} endpoint={endpoint}")
            initial = self.client.post(endpoint, request)
            self.raise_if_cancelled(job_id)
            request_id = initial.get("request_id")
            if not isinstance(request_id, str):
                raise StudioError(f"Video response did not include request_id: {initial}", 502)
            log_event(f"xAI accepted job={job_id} request_id={request_id}")
            self.jobs.update(job_id, status="processing", progress=5, request_id=request_id)

            result = self.poll_video(job_id, request_id)
            self.raise_if_cancelled(job_id)
            item = self._save_video_result(result, payload, prompt, mode, request_id)
            log_event(f"saved video job={job_id} file={item.get('file')}")
            self.jobs.update(job_id, status="done", progress=100, item=item)
        except JobCancelled:
            log_event(f"cancelled video job={job_id}")
            self.jobs.update(
                job_id,
                status="cancelled",
                error="Cancelled locally. The remote xAI request may still finish server-side.",
            )
        except Exception as exc:
            log_event(f"failed video job={job_id}: {exc}")
            self.jobs.update(job_id, status="failed", error=str(exc), progress=0)

    def _video_payload(self, payload: dict[str, Any], mode: str) -> dict[str, Any]:
        prompt = require_text(payload, "prompt")
        request = compact(
            {
                "model": payload.get("model") or DEFAULT_VIDEO_MODEL,
                "prompt": prompt,
                "duration": int(payload["duration"]) if payload.get("duration") else None,
                "aspect_ratio": payload.get("aspect_ratio") if mode == "video-generate" else None,
                "resolution": payload.get("resolution") if mode == "video-generate" else None,
            }
        )

        if mode == "video-generate":
            image = payload.get("image")
            refs = payload.get("reference_images") or []
            if image and refs:
                raise StudioError("Use a start image or reference images, not both.")
            if image:
                request["image"] = image_reference(str(image))
            if refs:
                if not isinstance(refs, list) or len(refs) > 7:
                    raise StudioError("Reference-to-video accepts up to 7 images.")
                request["reference_images"] = [image_reference(str(ref)) for ref in refs]
        else:
            request["video"] = self.video_reference(payload)
        return request

    def video_reference(self, payload: dict[str, Any]) -> dict[str, str]:
        selected_id = payload.get("source_item_id")
        source_video = payload.get("video")
        trim_end = parse_trim_end(payload.get("source_trim_end"))
        trim_quality = trim_quality_settings(payload.get("source_trim_quality"))
        if selected_id:
            item = self.library.get_item(str(selected_id))
            file_path = item.get("file")
            if trim_end and isinstance(file_path, str):
                return {"url": trim_video_to_data_uri(Path(file_path), trim_end, trim_quality)}
            remote_url = item.get("remote_url")
            if isinstance(remote_url, str) and remote_url.startswith("http"):
                return {"url": remote_url}
            if isinstance(file_path, str):
                return {"url": file_to_data_uri(Path(file_path), "video/mp4")}
        if isinstance(source_video, str) and source_video:
            if trim_end:
                return {"url": trim_data_uri_video(source_video, trim_end, trim_quality)}
            return {"url": source_video}
        raise StudioError("Select a local video or upload a source video.")

    def poll_video(self, job_id: str, request_id: str) -> dict[str, Any]:
        started = time.monotonic()
        while True:
            self.raise_if_cancelled(job_id)
            result = self.client.get(f"/videos/{urllib.parse.quote(request_id)}")
            status = result.get("status")
            progress = result.get("progress")
            if isinstance(progress, int):
                self.jobs.update(job_id, status=status or "processing", progress=progress)
            if status == "done":
                return result
            if status in {"failed", "expired", "cancelled"}:
                raise StudioError(json.dumps(result, ensure_ascii=False, indent=2), 502)
            if time.monotonic() - started > 900:
                raise StudioError(f"Timed out waiting for video request {request_id}", 504)
            time.sleep(5)

    def raise_if_cancelled(self, job_id: str) -> None:
        if self.jobs.is_cancelled(job_id):
            raise JobCancelled()

    def _save_video_result(
        self,
        result: dict[str, Any],
        payload: dict[str, Any],
        prompt: str,
        mode: str,
        request_id: str,
    ) -> dict[str, Any]:
        video = result.get("video") if isinstance(result.get("video"), dict) else {}
        url = video.get("url") if isinstance(video, dict) else None
        if not isinstance(url, str):
            raise StudioError("Video response did not contain a video URL.", 502)

        media_bytes, mime = self.download(url)
        item_id = uuid.uuid4().hex
        stem = f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{mode}-{item_id[:8]}"
        video_dir = self.library.gallery_output_dir(payload.get("gallery_folder_id"), "Video")
        path = unique_path(video_dir / f"{stem}{guess_ext(mime, '.mp4')}")
        path.write_bytes(media_bytes)
        metadata_path = self.write_metadata(item_id, result)
        group_id = str(payload.get("group_id") or payload.get("parent_id") or item_id)
        item = {
            "id": item_id,
            "type": "video",
            "mode": mode,
            "title": "Video",
            "prompt": prompt,
            "category": payload.get("category") or "Video",
            "tags": normalize_tags(payload.get("tags")),
            "created_at": utc_now(),
            "local_url": self.library.media_url(path),
            "file": str(path),
            "mime": mime,
            "remote_url": url,
            "request_id": request_id,
            "metadata_file": str(metadata_path),
            "metadata": {
                "group_id": group_id,
                "parent_id": payload.get("parent_id"),
                "gallery_folder_id": payload.get("gallery_folder_id"),
                "provider": "build",
                "token_source": "build",
                "model": payload.get("model") or DEFAULT_VIDEO_MODEL,
                "duration": video.get("duration") or payload.get("duration"),
                "aspect_ratio": payload.get("aspect_ratio"),
                "resolution": payload.get("resolution"),
                "start_image": source_reference_metadata(payload.get("image")),
                "reference_images": source_references_metadata(payload.get("reference_images") or []),
            },
        }
        return self.library.add_item(item)

    def download(self, url: str) -> tuple[bytes, str]:
        req = urllib.request.Request(url, headers={"User-Agent": "grok-studio/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=https_context()) as response:
                return response.read(), response.headers.get("Content-Type") or "application/octet-stream"
        except urllib.error.URLError as exc:
            raise StudioError(f"Could not download xAI media URL: {format_network_error(exc)}", 502) from exc

    def write_metadata(self, item_id: str, result: dict[str, Any]) -> Path:
        path = self.library.metadata_dir / f"{item_id}.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return path


def require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StudioError(f"{key} is required.")
    return value.strip()


def parse_analyze_result(value: str) -> tuple[str, str]:
    text = value.strip().replace("\r\n", "\n")
    text = re.sub(r"^```(?:text|markdown)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r"(?im)^\s*[*#_`]*English\s*:?\s*[*#_`]*\s*$", "English", text)
    text = re.sub(r"(?im)^\s*[*#_`]*Korean\s*:?\s*[*#_`]*\s*$", "Korean", text)
    match = re.search(r"(?is)^\s*English\s+(.*?)\s+Korean\s+(.*?)\s*$", text)
    if not match:
        return text.strip(), ""
    return match.group(1).strip(), match.group(2).strip()


def normalize_tags(value: Any) -> list[str]:
    if isinstance(value, str):
        parts = re.split(r"[,#]", value)
    elif isinstance(value, list):
        parts = [str(part) for part in value]
    else:
        parts = []
    tags = []
    for part in parts:
        tag = part.strip()
        if tag and tag not in tags:
            tags.append(tag)
    return tags[:12]


def summarize_detail(detail: dict[str, Any]) -> str:
    parts = []
    for key in ("promptLength", "imageFiles", "startImageFiles", "referenceImageFiles", "sourceVideoFiles"):
        value = detail.get(key)
        if isinstance(value, list):
            total = sum(item.get("size", 0) for item in value if isinstance(item, dict))
            parts.append(f"{key}={len(value)}/{total}B")
        elif value is not None:
            parts.append(f"{key}={value}")
    return " ".join(parts) or "-"


def delete_item_files(item: dict[str, Any]) -> None:
    file_path = item.get("file")
    metadata_path = item.get("metadata_file")
    delete_file = safe_unlink if item.get("type") == "prompt" else safe_move_to_trash
    if isinstance(file_path, str):
        for root in deletion_roots():
            delete_file(file_path, root)
    if isinstance(metadata_path, str):
        for root in deletion_roots():
            delete_file(metadata_path, root)


def deletion_roots() -> list[Path]:
    roots = [DATA_DIR, MEDIA_DIR, META_DIR, TMP_DIR]
    external = external_library_root()
    if external is not None:
        roots.append(external)
        roots.append(external / EXTERNAL_META_DIR_NAME)
    return roots


def image_reference(value: str) -> dict[str, str]:
    if value.startswith("/media/"):
        return {"url": file_to_data_uri(resolve_media_path(value), "image/png")}
    return {"url": value}


def source_reference_metadata(value: Any) -> dict[str, str] | None:
    if not isinstance(value, str) or not value:
        return None
    if value.startswith("/media/") or value.startswith("http://") or value.startswith("https://"):
        return {"url": value}
    return None


def source_references_metadata(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    return [ref for ref in (source_reference_metadata(value) for value in values) if ref]


def job_context(payload: dict[str, Any], mode: str) -> dict[str, Any]:
    return compact(
        {
            "mode": mode,
            "group_id": payload.get("group_id"),
            "parent_id": payload.get("parent_id"),
            "preview_url": payload.get("preview_url"),
            "preview_type": payload.get("preview_type"),
            "gallery_folder_id": payload.get("gallery_folder_id"),
        }
    )


def parse_trim_end(value: Any) -> float | None:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if not (0.25 < seconds < 60 * 60):
        return None
    return round(seconds, 3)


def trim_quality_settings(value: Any) -> dict[str, str]:
    quality = str(value or "high").strip().lower()
    crf_by_quality = {
        "high": "16",
        "medium": "18",
        "low": "20",
    }
    return {
        "quality": quality if quality in crf_by_quality else "high",
        "crf": crf_by_quality.get(quality, "16"),
        "preset": "medium",
    }


def ffmpeg_binary() -> str:
    configured = os.environ.get("GROK_STUDIO_FFMPEG")
    if configured:
        path = Path(configured).expanduser()
        if path.exists():
            return str(path)
    found = shutil.which("ffmpeg")
    if found:
        return found
    for candidate in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        path = Path(candidate)
        if path.exists():
            return str(path)
    if os.name == "nt":
        message = "Extending from a paused point requires ffmpeg. Install ffmpeg and add it to Windows PATH."
    else:
        message = "Extending from a paused point requires ffmpeg. Install it with Homebrew: brew install ffmpeg"
    raise StudioError(message, 500)


def trim_data_uri_video(value: str, end_seconds: float, quality: dict[str, str]) -> str:
    media_bytes, mime = data_uri_to_bytes(value)
    source = unique_path(TMP_DIR / f"source-{uuid.uuid4().hex[:8]}{guess_ext(mime, '.mp4')}")
    source.write_bytes(media_bytes)
    try:
        return trim_video_to_data_uri(source, end_seconds, quality)
    finally:
        safe_unlink(str(source), TMP_DIR)


def trim_video_to_data_uri(path: Path, end_seconds: float, quality: dict[str, str]) -> str:
    if not path.is_file():
        raise StudioError(f"Local file is missing: {path}", 404)
    log_event(
        "trimming source video "
        f"end={end_seconds:.3f}s quality={quality['quality']} crf={quality['crf']} preset={quality['preset']}"
    )
    output = unique_path(TMP_DIR / f"trim-{uuid.uuid4().hex[:8]}.mp4")
    command = [
        ffmpeg_binary(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-t",
        f"{end_seconds:.3f}",
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        quality["preset"],
        "-crf",
        quality["crf"],
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output),
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise StudioError(f"Could not trim source video: {exc}", 500) from exc
    if result.returncode != 0:
        safe_unlink(str(output), TMP_DIR)
        detail = result.stderr.strip() or "ffmpeg failed"
        raise StudioError(f"Could not trim source video: {detail}", 500)
    try:
        return file_to_data_uri(output, "video/mp4")
    finally:
        safe_unlink(str(output), TMP_DIR)


def safe_unlink(path_text: str, root: Path) -> None:
    try:
        path = Path(path_text).expanduser().resolve()
        root_resolved = root.resolve()
    except OSError:
        return
    if path != root_resolved and root_resolved not in path.parents:
        log_event(f"refused to delete outside {root_resolved}: {path}")
        return
    try:
        if path.is_file():
            path.unlink()
            log_event(f"deleted local file {path}")
    except OSError as exc:
        log_event(f"could not delete {path}: {exc}")


def safe_move_to_trash(path_text: str, root: Path) -> None:
    try:
        path = Path(path_text).expanduser().resolve()
        root_resolved = root.resolve()
    except OSError:
        return
    if path != root_resolved and root_resolved not in path.parents:
        log_event(f"refused to move outside {root_resolved} to Trash: {path}")
        return
    if not path.exists():
        return
    if not path.is_file() and not path.is_dir():
        raise StudioError(f"Trash move target is not a file or folder: {path}", 400)
    try:
        moved = move_file_to_platform_trash(path)
    except StudioError:
        raise
    except (OSError, shutil.Error, subprocess.SubprocessError) as exc:
        raise StudioError(f"Could not move to Trash: {exc}", 500) from exc
    if moved is None:
        log_event(f"moved local path to {platform_trash_name()} {path}")
    else:
        log_event(f"moved local path to {platform_trash_name()} {path} -> {moved}")


def move_file_to_platform_trash(path: Path) -> Path | None:
    if os.name == "nt":
        move_file_to_windows_recycle_bin(path)
        return None
    if sys.platform == "darwin":
        move_file_to_macos_trash(path)
        return None
    trash_dir = linux_trash_files_dir()
    trash_dir.mkdir(parents=True, exist_ok=True)
    target = unique_path(trash_dir / path.name)
    shutil.move(str(path), str(target))
    return target


def platform_trash_name() -> str:
    if os.name == "nt":
        return "Recycle Bin"
    return "Trash"


def move_file_to_macos_trash(path: Path) -> None:
    script = (
        "tell application \"Finder\"\n"
        f"delete (POSIX file {applescript_string(str(path))} as alias)\n"
        "end tell"
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "Finder Trash move failed"
        raise StudioError(f"Could not move file to Trash: {detail}", 500)


def linux_trash_files_dir() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME")
    return (Path(data_home).expanduser() if data_home else Path.home() / ".local" / "share") / "Trash" / "files"


def move_file_to_windows_recycle_bin(path: Path) -> None:
    import ctypes
    from ctypes import wintypes

    FO_DELETE = 0x0003
    FOF_NOCONFIRMATION = 0x0010
    FOF_ALLOWUNDO = 0x0040

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", wintypes.USHORT),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", wintypes.LPVOID),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    shell32 = ctypes.windll.shell32
    source = str(path) + "\0\0"
    operation = SHFILEOPSTRUCTW(
        None,
        FO_DELETE,
        source,
        None,
        FOF_ALLOWUNDO | FOF_NOCONFIRMATION,
        False,
        None,
        None,
    )
    result = shell32.SHFileOperationW(ctypes.byref(operation))
    if result:
        raise StudioError(f"Could not move to Recycle Bin: Windows shell error {result}", 500)
    if operation.fAnyOperationsAborted:
        raise StudioError("Recycle Bin move was cancelled.", 400)


def media_url(path: Path) -> str:
    resolved = path.resolve()
    for root in media_roots():
        try:
            rel = resolved.relative_to(root.resolve())
            return "/media/" + urllib.parse.quote(str(rel).replace(os.sep, "/"))
        except ValueError:
            continue
    raise StudioError(f"Media path is outside the library: {path}", 500)


def resolve_media_path(url_path: str) -> Path:
    rel = urllib.parse.unquote(url_path.removeprefix("/media/"))
    for root in media_roots():
        candidate = (root / rel).resolve()
        root_resolved = root.resolve()
        if root_resolved not in candidate.parents and candidate != root_resolved:
            continue
        if candidate.is_file():
            return candidate
    raise StudioError("Media not found.", 404)


def media_roots() -> list[Path]:
    roots = [MEDIA_DIR, DATA_DIR]
    external = external_library_root()
    if external is not None:
        roots.extend([external, external / "Image", external / "Video", external / "Upload Image"])
    return roots


def open_media_folder() -> dict[str, Any]:
    ensure_dirs()
    root = external_library_root() or MEDIA_DIR
    try:
        if os.name == "nt":
            os.startfile(str(root))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(root)])
        else:
            subprocess.Popen(["xdg-open", str(root)])
    except OSError as exc:
        raise StudioError(f"Could not open media folder: {exc}", 500) from exc
    return {"ok": True, "path": str(root)}


def applescript_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def choose_folder_in_windows_explorer(current: str | None = None) -> str | None:
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        raise StudioError("Windows PowerShell is required to select a library folder.", 500)
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); "
        "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$dialog.Description = 'Select a Library folder for Grok Studio Lab'; "
        "$dialog.ShowNewFolderButton = $true; "
        "$current = $env:GROK_STUDIO_PICKER_CURRENT; "
        "if ($current -and (Test-Path -LiteralPath $current -PathType Container)) "
        "{ $dialog.SelectedPath = $current }; "
        "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) "
        "{ [Console]::Write($dialog.SelectedPath) }"
    )
    env = os.environ.copy()
    env["GROK_STUDIO_PICKER_CURRENT"] = str(current or "")
    try:
        result = subprocess.run(
            [powershell, "-NoProfile", "-STA", "-Command", script],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise StudioError(f"Could not open Windows folder picker: {exc}", 500) from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "Windows folder picker failed"
        raise StudioError(f"Could not choose library folder: {detail}", 500)
    selected = result.stdout.strip()
    return selected or None


def choose_folder_in_finder(current: str | None = None) -> str | None:
    prompt = "Select a Library folder for Grok Studio Lab"
    current_path = Path(current or "").expanduser() if current else None
    if current_path and current_path.is_dir():
        script = (
            f'set chosenFolder to choose folder with prompt {applescript_string(prompt)} '
            f'default location POSIX file {applescript_string(str(current_path))}\n'
            "return POSIX path of chosenFolder"
        )
    else:
        script = (
            f"set chosenFolder to choose folder with prompt {applescript_string(prompt)}\n"
            "return POSIX path of chosenFolder"
        )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise StudioError(f"Could not open Finder folder picker: {exc}", 500) from exc
    if result.returncode == 0:
        selected = result.stdout.strip()
        return selected or None
    if "User canceled" in result.stderr or "(-128)" in result.stderr:
        return None
    detail = result.stderr.strip() or result.stdout.strip() or "Finder folder picker failed"
    raise StudioError(f"Could not choose library folder: {detail}", 500)


def choose_library_folder(current: str | None = None) -> str | None:
    if os.name == "nt":
        return choose_folder_in_windows_explorer(current)
    if sys.platform == "darwin":
        return choose_folder_in_finder(current)
    raise StudioError("Native folder selection is supported on Windows and macOS.", 500)


def make_handler(app: StudioApp) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "GrokStudio/1.0"

        def log_message(self, fmt: str, *args: Any) -> None:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def do_GET(self) -> None:
            try:
                self.route_get()
            except StudioError as exc:
                self.send_json({"error": exc.message}, exc.status)
            except Exception as exc:
                self.send_json({"error": str(exc)}, 500)

        def do_POST(self) -> None:
            try:
                self.route_post()
            except StudioError as exc:
                self.send_json({"error": exc.message}, exc.status)
            except Exception as exc:
                self.send_json({"error": str(exc)}, 500)

        def route_get(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if path in {"/", "/index.html"}:
                self.send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            elif path == "/editor.html":
                self.send_file(STATIC_DIR / "editor.html", "text/html; charset=utf-8")
            elif path == "/assets/app.css":
                self.send_file(STATIC_DIR / "app.css", "text/css; charset=utf-8")
            elif path == "/assets/app.js":
                self.send_file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
            elif path.startswith("/assets/"):
                asset_name = urllib.parse.unquote(path.removeprefix("/assets/"))
                if not asset_name or "\\" in asset_name:
                    raise StudioError("Asset not found.", 404)
                asset_path = (STATIC_DIR / asset_name).resolve()
                static_root = STATIC_DIR.resolve()
                if static_root not in asset_path.parents and asset_path != static_root:
                    raise StudioError("Asset not found.", 404)
                self.send_file(asset_path, mimetypes.guess_type(asset_path.name)[0] or "application/octet-stream")
            elif path == "/api/state":
                self.send_json(app.state())
            elif path == "/api/system-fonts":
                self.send_json({"fonts": system_font_families()})
            elif path == "/api/account-usage":
                self.send_json({"usage": app.account_usage(False)})
            elif path == "/api/accounts":
                self.send_json(app.accounts())
            elif path == "/api/imagine/session":
                self.send_json({"imagine": imagine_session_summary(), "generation_provider": app.generation_provider()})
            elif path == "/api/imagine/remote/media":
                self.send_imagine_remote_media(parsed)
            elif path == "/api/jobs":
                self.send_json({"jobs": app.jobs.all()})
            elif path.startswith("/api/jobs/"):
                self.send_json({"job": app.jobs.get(path.rsplit("/", 1)[-1])})
            elif path.startswith("/media/"):
                media_path = resolve_media_path(path)
                self.send_file(media_path, mimetypes.guess_type(media_path.name)[0] or "application/octet-stream")
            elif path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
            else:
                raise StudioError("Not found.", 404)

        def route_post(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            length = int(self.headers.get("Content-Length") or 0)
            log_event(f"POST {path} body={length} bytes")
            payload = self.read_json()
            if path == "/api/client-event":
                event = payload.get("event") or "unknown"
                detail = payload.get("detail") if isinstance(payload.get("detail"), dict) else {}
                log_event(f"client event={event} mode={payload.get('mode')} detail={summarize_detail(detail)}")
                self.send_json({"ok": True})
            elif path == "/api/heartbeat":
                self.send_json(app.heartbeat())
            elif path == "/api/shutdown":
                self.send_json(app.request_shutdown(self.server, payload))
            elif path == "/api/categories":
                categories = app.library.add_category(require_text(payload, "name"))
                self.send_json({"categories": categories})
            elif path == "/api/gallery/folders":
                folder = app.library.add_gallery_folder(
                    require_text(payload, "name"),
                    str(payload.get("parent_id") or "").strip() or None,
                )
                self.send_json({"folder": folder, "state": app.state()})
            elif path == "/api/gallery/folders/delete":
                self.send_json(app.library.delete_gallery_folder(require_text(payload, "folder_id")))
            elif path == "/api/gallery/folders/rename":
                folder = app.library.rename_gallery_folder(
                    require_text(payload, "folder_id"),
                    require_text(payload, "name"),
                )
                self.send_json({"folder": folder, "state": app.state()})
            elif path == "/api/gallery/folders/layout":
                self.send_json(app.library.update_gallery_folder_layout(
                    payload.get("folders"),
                    payload.get("sort_mode") if "sort_mode" in payload else None,
                ))
            elif path == "/api/prompts":
                self.send_json({"item": app.save_prompt(payload)})
            elif path == "/api/analyze":
                self.send_json(app.analyze_image(payload))
            elif path == "/api/translate":
                self.send_json(app.translate_prompt(payload))
            elif path == "/api/uploads/images":
                self.send_json(app.save_uploaded_images(payload))
            elif path == "/api/image-editor/save":
                self.send_json(app.save_image_edit(payload))
            elif path == "/api/uploads/images/delete":
                self.send_json(app.delete_uploaded_image(payload))
            elif path == "/api/image":
                self.send_json({"job": app.start_image(payload)})
            elif path == "/api/video":
                self.send_json({"job": app.start_video(payload, "video-generate")})
            elif path == "/api/video/extend":
                self.send_json({"job": app.start_video(payload, "video-extend")})
            elif path == "/api/video/edit":
                self.send_json({"job": app.start_video(payload, "video-edit")})
            elif path.startswith("/api/jobs/") and path.endswith("/cancel"):
                job_id = path.split("/")[3]
                self.send_json({"job": app.jobs.cancel(job_id)})
            elif path.startswith("/api/jobs/") and path.endswith("/dismiss"):
                job_id = path.split("/")[3]
                self.send_json({"job": app.jobs.dismiss(job_id)})
            elif path == "/api/items/delete":
                ids = payload.get("ids")
                if not isinstance(ids, list):
                    raise StudioError("ids must be a list.")
                self.send_json(app.library.delete_items([str(item_id) for item_id in ids]))
            elif path == "/api/items/move-to-gallery":
                ids = payload.get("ids")
                if not isinstance(ids, list):
                    raise StudioError("ids must be a list.")
                self.send_json(app.library.move_items_to_gallery(
                    [str(item_id) for item_id in ids],
                    require_text(payload, "folder_id"),
                ))
            elif path == "/api/open-media-folder":
                self.send_json(open_media_folder())
            elif path == "/api/library-folder":
                self.send_json(app.set_library_folder(payload))
            elif path == "/api/choose-library-folder":
                self.send_json(app.choose_library_folder(payload))
            elif path == "/api/account-usage/refresh":
                self.send_json({"usage": app.account_usage(True)})
            elif path == "/api/account-usage/import":
                self.send_json({"usage": app.import_account_usage(payload)})
            elif path == "/api/accounts/register":
                self.send_json(app.register_account(payload))
            elif path == "/api/accounts/select":
                account_id = require_text(payload, "id")
                self.send_json(app.set_active_account(account_id))
            elif path == "/api/accounts/delete":
                account_id = require_text(payload, "id")
                self.send_json(app.delete_account(account_id))
            elif path == "/api/accounts/reorder":
                self.send_json(app.reorder_accounts(payload))
            elif path == "/api/accounts/tier":
                self.send_json(app.update_account_tier(payload))
            elif path == "/api/generation-provider":
                app.set_generation_provider(require_text(payload, "provider"))
                self.send_json(app.accounts())
            elif path == "/api/imagine/login/start":
                self.send_json(app.start_imagine_login(payload))
            elif path == "/api/imagine/usage-page":
                self.send_json(app.open_imagine_usage_page(payload))
            elif path == "/api/imagine/remote/list":
                self.send_json(app.list_imagine_remote_library(payload))
            elif path == "/api/imagine/remote/import-to-gallery":
                self.send_json(app.import_imagine_remote_to_gallery(payload))
            elif path == "/api/imagine/login/capture":
                self.send_json(app.capture_imagine_login())
            elif path == "/api/imagine/select":
                self.send_json(app.select_imagine_account(str(payload.get("id") or "").strip() or None))
            elif path == "/api/imagine/accounts/status":
                self.send_json(app.imagine_account_statuses(payload))
            elif path == "/api/imagine/logout":
                self.send_json(app.clear_imagine_login())
            elif path == "/api/imagine/delete":
                self.send_json(app.delete_imagine_account(require_text(payload, "id")))
            elif path == "/api/imagine/reorder":
                payload["provider"] = "imagine"
                self.send_json(app.reorder_accounts(payload))
            elif path.startswith("/api/items/") and path.endswith("/update"):
                item_id = path.split("/")[3]
                self.send_json({"item": app.library.update_item(item_id, payload)})
            else:
                raise StudioError("Not found.", 404)

        def read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise StudioError("Request body is too large.", 413)
            raw = self.rfile.read(length)
            if not raw:
                return {}
            try:
                data = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise StudioError("Invalid JSON body.") from exc
            if not isinstance(data, dict):
                raise StudioError("JSON body must be an object.")
            return data

        def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def send_imagine_remote_media(self, parsed: urllib.parse.ParseResult) -> None:
            query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            url = str((query.get("url") or [""])[0]).strip()
            kind = str((query.get("kind") or [""])[0]).strip().lower()
            if kind not in {"image", "video"}:
                raise StudioError("Invalid Imagine media kind.", 400)
            source = normalize_media_api_url(url)
            if not source or not source.startswith(("http://", "https://")):
                raise StudioError("Invalid Imagine media URL.", 400)
            headers = app.imagine_media_headers(kind)
            range_header = self.headers.get("Range")
            if range_header:
                headers["Range"] = range_header
            request = urllib.request.Request(source, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(request, timeout=min(max(5, app.timeout), 30), context=https_context()) as response:
                    status = response.status if response.status in {200, 206} else 200
                    content_type = response.headers.get("Content-Type") or ("video/mp4" if kind == "video" else "image/jpeg")
                    self.send_response(status)
                    self.send_header("Content-Type", content_type)
                    length = response.headers.get("Content-Length")
                    if length:
                        self.send_header("Content-Length", length)
                    content_range = response.headers.get("Content-Range")
                    if content_range:
                        self.send_header("Content-Range", content_range)
                    self.send_header("Accept-Ranges", response.headers.get("Accept-Ranges") or "bytes")
                    self.send_header("Cache-Control", "private, max-age=3600, immutable")
                    etag = response.headers.get("ETag")
                    if etag:
                        self.send_header("ETag", etag)
                    last_modified = response.headers.get("Last-Modified")
                    if last_modified:
                        self.send_header("Last-Modified", last_modified)
                    self.end_headers()
                    while True:
                        chunk = response.read(1024 * 256)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
            except urllib.error.HTTPError as exc:
                raise StudioError(f"Could not load Imagine media: HTTP {exc.code} {exc.reason}", exc.code) from exc
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                raise StudioError(f"Could not load Imagine media: {format_network_error(exc)}", 502) from exc

        def send_file(self, path: Path, content_type: str) -> None:
            if not path.is_file():
                raise StudioError("Not found.", 404)
            size = path.stat().st_size
            range_header = self.headers.get("Range")
            if range_header and range_header.startswith("bytes="):
                start_text, _, end_text = range_header.removeprefix("bytes=").partition("-")
                start = int(start_text or 0)
                end = int(end_text) if end_text else size - 1
                end = min(end, size - 1)
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
                length = end - start + 1
                self.send_response(206)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(length))
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                with path.open("rb") as file:
                    file.seek(start)
                    self.wfile.write(file.read(length))
                return

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            with path.open("rb") as file:
                while True:
                    chunk = file.read(1024 * 512)
                    if not chunk:
                        break
                    self.wfile.write(chunk)

    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Grok Studio as a local web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--auth-file", default=DEFAULT_AUTH_FILE)
    parser.add_argument("--base-url", default=API_BASE)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--open", action="store_true", help="Open the browser after starting.")
    parser.add_argument("--check", action="store_true", help="Print local config and exit.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ensure_dirs()
    app = StudioApp(args.auth_file, args.base_url, args.timeout)
    if args.check:
        print(json.dumps(app.state(), ensure_ascii=False, indent=2))
        return 0

    url = f"http://{args.host}:{args.port}"
    try:
        server = ThreadingHTTPServer((args.host, args.port), make_handler(app))
    except OSError as exc:
        if exc.errno != errno.EADDRINUSE and getattr(exc, "winerror", None) != 10048:
            raise
        log_event(f"port {args.port} is busy; asking previous local server to shut down")
        request_previous_shutdown(url)
        time.sleep(1.6)
        server = ThreadingHTTPServer((args.host, args.port), make_handler(app))
    print(f"{APP_NAME} running at {url}")
    print(f"Local library: {app.library.info()['root']}")
    if args.host != "127.0.0.1":
        print("Warning: non-local host binding can expose the studio on your network.")
    if args.open:
        token = secrets.token_hex(2)
        threading.Timer(0.4, lambda: webbrowser.open(url + f"/?t={token}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Grok Studio.")
    finally:
        server.server_close()
    return 0


def request_previous_shutdown(url: str) -> None:
    payload = json.dumps({"event": "restart-cleanup", "at": utc_now()}).encode("utf-8")
    request = urllib.request.Request(
        url.rstrip("/") + "/api/shutdown",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(request, timeout=1.2).read()
    except Exception as exc:
        log_event(f"previous server shutdown request did not complete: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
