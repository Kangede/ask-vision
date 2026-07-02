#!/usr/bin/env python3
"""Generic OpenAI/Anthropic-compatible multimodal helper for ask-vision."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import json
import mimetypes
import os
from pathlib import Path
import sys
import time
from typing import Any
from urllib import error, parse, request


CONFIG_ENV = "ASK_VISION_CONFIG"
PROVIDER_ENV = "ASK_VISION_PROVIDER"
BASE_URL_ENV = "ASK_VISION_BASE_URL"
API_KEY_ENV = "ASK_VISION_API_KEY"
MODEL_ENV = "ASK_VISION_MODEL"
ANTHROPIC_VERSION_ENV = "ASK_VISION_ANTHROPIC_VERSION"
DEFAULT_ANTHROPIC_VERSION = "2023-06-01"


class ApiError(Exception):
    def __init__(self, status: int | None, url: str, body: str):
        self.status = status
        self.url = url
        self.body = body
        super().__init__(f"API request failed: status={status} url={url}")


@dataclass
class Media:
    source: str
    url: str
    mime: str
    filename: str
    raw_data: bytes | None
    base64_data: str | None
    is_url: bool


def emit(payload: dict[str, Any], code: int = 0) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(code)


def default_config_path() -> Path:
    override = os.environ.get(CONFIG_ENV)
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    return base / "ask-vision" / "config.json"


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        emit({"ok": False, "error": f"Could not read config: {exc}", "config_path": str(path)}, 2)
    return data if isinstance(data, dict) else {}


def save_config(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def parse_extra_headers(values: list[str] | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    for value in values or []:
        if ":" not in value:
            emit({"ok": False, "error": f"Header must be in 'Name: Value' form: {value}"}, 2)
        name, header_value = value.split(":", 1)
        headers[name.strip()] = header_value.strip()
    return headers


def require_value(name: str, value: str | None) -> str:
    if not value:
        emit({"ok": False, "error": f"Missing required value: {name}"}, 2)
    return value


def merged_setting(args: argparse.Namespace, key: str, env_name: str, config: dict[str, Any]) -> str | None:
    value = getattr(args, key, None)
    return value or os.environ.get(env_name) or config.get(key)


def provider_list(provider: str | None) -> list[str]:
    value = (provider or "auto").lower()
    if value == "auto":
        return ["openai", "anthropic"]
    if value not in {"openai", "anthropic"}:
        emit({"ok": False, "error": f"Unsupported provider: {provider}"}, 2)
    return [value]


def strip_known_endpoint(raw_url: str) -> str:
    parsed = parse.urlparse(raw_url.strip())
    if not parsed.scheme or not parsed.netloc:
        emit({"ok": False, "error": f"API URL must include scheme and host: {raw_url}"}, 2)
    path = parsed.path.rstrip("/")
    for suffix in ("/chat/completions", "/responses", "/messages", "/models"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
            break
    return parse.urlunparse(parsed._replace(path=path.rstrip("/"), params="", query="", fragment="")).rstrip("/")


def candidate_base_urls(raw_url: str) -> list[str]:
    base = strip_known_endpoint(raw_url)
    candidates = [base] if base.rstrip("/").endswith("/v1") else [base.rstrip("/") + "/v1", base]
    deduped: list[str] = []
    for item in candidates:
        if item not in deduped:
            deduped.append(item)
    return deduped


def http_json(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
    timeout: int = 90,
) -> dict[str, Any]:
    request_headers = {
        "Accept": "application/json",
        **headers,
    }
    body = None
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise ApiError(exc.code, url, raw[:4000]) from exc
    except error.URLError as exc:
        raise ApiError(None, url, str(exc)) from exc
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ApiError(None, url, f"Non-JSON response: {raw[:1000]}") from exc
    return decoded


def headers_for_provider(
    provider: str,
    api_key: str,
    anthropic_version: str,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    if provider == "anthropic":
        headers = {
            "x-api-key": api_key,
            "anthropic-version": anthropic_version,
        }
    else:
        headers = {"Authorization": f"Bearer {api_key}"}
    headers.update(extra_headers or {})
    return headers


def extract_models(data: dict[str, Any]) -> list[str]:
    raw_models: Any = data.get("data")
    if raw_models is None:
        raw_models = data.get("models")
    if raw_models is None and isinstance(data.get("result"), list):
        raw_models = data["result"]
    if not isinstance(raw_models, list):
        return []
    models: list[str] = []
    for item in raw_models:
        if isinstance(item, str):
            models.append(item)
        elif isinstance(item, dict):
            model_id = item.get("id") or item.get("name") or item.get("model")
            if isinstance(model_id, str):
                models.append(model_id)
    return sorted(dict.fromkeys(models))


def likely_multimodal(models: list[str]) -> list[str]:
    hints = (
        "vision",
        "visual",
        "vl",
        "omni",
        "4o",
        "multimodal",
        "claude",
        "sonnet",
        "opus",
        "haiku",
        "gemini",
        "qwen-vl",
        "llava",
    )
    preferred = [model for model in models if any(hint in model.lower() for hint in hints)]
    return preferred or models


def model_pages_url(base: str, after_id: str | None = None) -> str:
    url = base.rstrip("/") + "/models"
    query = {"limit": "100"}
    if after_id:
        query["after_id"] = after_id
    return url + "?" + parse.urlencode(query)


def list_models_for_provider(
    provider: str,
    base_url: str,
    api_key: str,
    anthropic_version: str,
    timeout: int,
    extra_headers: dict[str, str],
) -> tuple[str, list[str], list[dict[str, Any]], dict[str, Any] | None]:
    errors: list[dict[str, Any]] = []
    for base in candidate_base_urls(base_url):
        headers = headers_for_provider(provider, api_key, anthropic_version, extra_headers)
        all_models: list[str] = []
        raw_first_page: dict[str, Any] | None = None
        after_id: str | None = None
        try:
            while True:
                url = model_pages_url(base, after_id) if provider == "anthropic" else base.rstrip("/") + "/models"
                data = http_json("GET", url, headers=headers, timeout=timeout)
                raw_first_page = raw_first_page or data
                all_models.extend(extract_models(data))
                if provider != "anthropic" or not data.get("has_more"):
                    break
                after_id = data.get("last_id")
                if not isinstance(after_id, str) or not after_id:
                    break
        except ApiError as exc:
            errors.append({"provider": provider, "status": exc.status, "url": exc.url, "body": exc.body})
            continue
        return base, sorted(dict.fromkeys(all_models)), errors, raw_first_page
    return "", [], errors, None


def cmd_config_path(args: argparse.Namespace) -> None:
    path = Path(args.config).expanduser() if args.config else default_config_path()
    emit({"ok": True, "config_path": str(path), "exists": path.exists()})


def cmd_clear_config(args: argparse.Namespace) -> None:
    path = Path(args.config).expanduser() if args.config else default_config_path()
    if path.exists():
        path.unlink()
    emit({"ok": True, "config_path": str(path), "cleared": True})


def cmd_configure(args: argparse.Namespace) -> None:
    path = Path(args.config).expanduser() if args.config else default_config_path()
    provider = (args.provider or "auto").lower()
    if provider not in {"auto", "openai", "anthropic"}:
        emit({"ok": False, "error": f"Unsupported provider: {provider}"}, 2)
    base_url = require_value("base_url", args.base_url)
    api_key = require_value("api_key", args.api_key)
    model = require_value("model", args.model)
    data = {
        "provider": provider,
        "base_url": strip_known_endpoint(base_url),
        "api_key": api_key,
        "model": model,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if args.anthropic_version:
        data["anthropic_version"] = args.anthropic_version
    save_config(path, data)
    emit({"ok": True, "config_path": str(path), "provider": provider, "base_url": data["base_url"], "model": model})


def cmd_models(args: argparse.Namespace) -> None:
    path = Path(args.config).expanduser() if args.config else default_config_path()
    config = load_config(path)
    provider = merged_setting(args, "provider", PROVIDER_ENV, config) or "auto"
    base_url = require_value("base_url", merged_setting(args, "base_url", BASE_URL_ENV, config))
    api_key = require_value("api_key", merged_setting(args, "api_key", API_KEY_ENV, config))
    anthropic_version = merged_setting(args, "anthropic_version", ANTHROPIC_VERSION_ENV, config) or DEFAULT_ANTHROPIC_VERSION
    extra_headers = parse_extra_headers(args.header)
    all_errors: list[dict[str, Any]] = []
    for candidate_provider in provider_list(provider):
        base, models, errors, raw = list_models_for_provider(
            candidate_provider,
            base_url,
            api_key,
            anthropic_version,
            args.timeout,
            extra_headers,
        )
        all_errors.extend(errors)
        if base:
            result: dict[str, Any] = {
                "ok": True,
                "provider": candidate_provider,
                "base_url": base,
                "models": models,
                "likely_multimodal": likely_multimodal(models),
                "count": len(models),
            }
            if args.raw:
                result["raw"] = raw
            emit(result)
    emit({"ok": False, "error": "Could not list models", "errors": all_errors}, 1)


def is_url(value: str) -> bool:
    parsed = parse.urlparse(value)
    return parsed.scheme in {"http", "https", "data"}


def parse_data_url(value: str) -> tuple[str, str, str]:
    header, _, data = value.partition(",")
    if not header.startswith("data:") or not data:
        emit({"ok": False, "error": "Invalid data URL"}, 2)
    media_type = header[5:].split(";", 1)[0] or "application/octet-stream"
    return media_type, data, "media"


def read_media(source: str, max_inline_mb: float) -> Media:
    if source.startswith("data:"):
        mime, encoded, filename = parse_data_url(source)
        return Media(source, source, mime, filename, None, encoded, True)
    if is_url(source):
        parsed = parse.urlparse(source)
        filename = Path(parsed.path).name or "media"
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return Media(source, source, mime, filename, None, None, True)

    path = Path(source).expanduser()
    if not path.exists():
        emit({"ok": False, "error": f"Media file not found: {path}"}, 2)
    size = path.stat().st_size
    max_bytes = int(max_inline_mb * 1024 * 1024)
    if size > max_bytes:
        emit(
            {
                "ok": False,
                "error": "Media file is too large to inline",
                "path": str(path),
                "size_bytes": size,
                "max_inline_mb": max_inline_mb,
                "suggestion": "Use an accessible URL, a compressed file, or a shorter clip.",
            },
            2,
        )
    raw = path.read_bytes()
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(raw).decode("ascii")
    data_url = f"data:{mime};base64,{encoded}"
    return Media(source, data_url, mime, path.name, raw, encoded, False)


def openai_media_item(media: Media, detail: str) -> dict[str, Any]:
    if media.mime.startswith("image/"):
        image_url: dict[str, Any] = {"url": media.url}
        if detail:
            image_url["detail"] = detail
        return {"type": "image_url", "image_url": image_url}
    if media.mime.startswith("audio/"):
        if media.base64_data:
            audio_format = Path(media.filename).suffix.lower().lstrip(".") or media.mime.split("/", 1)[1]
            return {"type": "input_audio", "input_audio": {"data": media.base64_data, "format": audio_format}}
        return {"type": "audio_url", "audio_url": {"url": media.url}}
    if media.mime.startswith("video/"):
        return {"type": "video_url", "video_url": {"url": media.url}}
    return {"type": "file", "file": {"file_data": media.url, "filename": media.filename}}


def anthropic_source(media: Media) -> dict[str, Any]:
    if media.source.startswith("data:") or not media.is_url:
        return {
            "type": "base64",
            "media_type": media.mime,
            "data": require_value("base64 media data", media.base64_data),
        }
    return {"type": "url", "url": media.url}


def anthropic_media_item(media: Media) -> dict[str, Any]:
    if media.mime.startswith("image/"):
        return {"type": "image", "source": anthropic_source(media)}
    return {"type": "document", "source": anthropic_source(media)}


def load_prompt(args: argparse.Namespace) -> str:
    parts: list[str] = []
    if args.prompt:
        parts.append(args.prompt)
    if args.prompt_file:
        parts.append(Path(args.prompt_file).expanduser().read_text(encoding="utf-8"))
    if args.prompt_stdin:
        parts.append(sys.stdin.read())
    if not parts:
        emit({"ok": False, "error": "Provide --prompt, --prompt-file, or --prompt-stdin"}, 2)
    return "\n\n".join(part.strip("\n") for part in parts if part is not None).strip()


def extract_openai_answer(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str):
                        chunks.append(text)
            return "\n".join(chunks)
    return ""


def extract_anthropic_answer(data: dict[str, Any]) -> str:
    content = data.get("content")
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                chunks.append(item["text"])
        return "\n".join(chunks)
    return ""


def build_openai_payload(args: argparse.Namespace, model: str, prompt: str, media: list[Media]) -> dict[str, Any]:
    content = [openai_media_item(item, args.detail) for item in media]
    content.append({"type": "text", "text": prompt})
    messages: list[dict[str, Any]] = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": content})
    payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": args.temperature}
    if args.max_tokens:
        payload["max_tokens"] = args.max_tokens
    return payload


def build_anthropic_payload(args: argparse.Namespace, model: str, prompt: str, media: list[Media]) -> dict[str, Any]:
    content = [anthropic_media_item(item) for item in media]
    content.append({"type": "text", "text": prompt})
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": args.max_tokens or 2048,
        "temperature": args.temperature,
        "messages": [{"role": "user", "content": content}],
    }
    if args.system:
        payload["system"] = args.system
    return payload


def cmd_ask(args: argparse.Namespace) -> None:
    path = Path(args.config).expanduser() if args.config else default_config_path()
    config = load_config(path)
    provider = merged_setting(args, "provider", PROVIDER_ENV, config) or "auto"
    base_url = require_value("base_url", merged_setting(args, "base_url", BASE_URL_ENV, config))
    api_key = "" if args.dry_run else require_value("api_key", merged_setting(args, "api_key", API_KEY_ENV, config))
    model = require_value("model", merged_setting(args, "model", MODEL_ENV, config))
    anthropic_version = merged_setting(args, "anthropic_version", ANTHROPIC_VERSION_ENV, config) or DEFAULT_ANTHROPIC_VERSION
    prompt = load_prompt(args)
    media = [read_media(source, args.max_inline_mb) for source in args.media or []]
    extra_headers = parse_extra_headers(args.header)

    all_errors: list[dict[str, Any]] = []
    for candidate_provider in provider_list(provider):
        for base in candidate_base_urls(base_url):
            if candidate_provider == "anthropic":
                endpoint = base.rstrip("/") + "/messages"
                payload = build_anthropic_payload(args, model, prompt, media)
                headers = headers_for_provider(candidate_provider, api_key, anthropic_version, extra_headers)
                answer_extractor = extract_anthropic_answer
            else:
                endpoint = base.rstrip("/") + "/chat/completions"
                payload = build_openai_payload(args, model, prompt, media)
                headers = headers_for_provider(candidate_provider, api_key, anthropic_version, extra_headers)
                answer_extractor = extract_openai_answer

            if args.dry_run:
                emit({"ok": True, "dry_run": True, "provider": candidate_provider, "endpoint": endpoint, "payload": payload})

            try:
                data = http_json("POST", endpoint, headers=headers, payload=payload, timeout=args.timeout)
            except ApiError as exc:
                all_errors.append({"provider": candidate_provider, "status": exc.status, "url": exc.url, "body": exc.body})
                continue

            result: dict[str, Any] = {
                "ok": True,
                "provider": candidate_provider,
                "base_url": base,
                "model": model,
                "answer": answer_extractor(data),
                "usage": data.get("usage"),
            }
            if args.raw:
                result["raw"] = data
            emit(result)
    emit({"ok": False, "error": "Could not get a multimodal response", "errors": all_errors}, 1)


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", help="Config JSON path. Defaults to an OS-specific ask-vision config path.")
    common.add_argument("--provider", choices=["auto", "openai", "anthropic"], help="API compatibility style.")
    common.add_argument("--base-url", help="API root, /v1 endpoint, or a known endpoint URL.")
    common.add_argument("--api-key", help="API key. The script never prints this value.")
    common.add_argument("--anthropic-version", help=f"Anthropic API version. Defaults to {DEFAULT_ANTHROPIC_VERSION}.")
    common.add_argument("--header", action="append", help="Extra HTTP header in 'Name: Value' form. Repeat as needed.")
    common.add_argument("--timeout", type=int, default=90, help="HTTP timeout in seconds.")

    parser = argparse.ArgumentParser(description="Ask an OpenAI-compatible or Anthropic-compatible multimodal model about media.")
    sub = parser.add_subparsers(dest="command", required=True)

    config_path = sub.add_parser("config-path")
    config_path.add_argument("--config")
    config_path.set_defaults(func=cmd_config_path)

    clear = sub.add_parser("clear-config")
    clear.add_argument("--config")
    clear.set_defaults(func=cmd_clear_config)

    configure = sub.add_parser("configure", parents=[common])
    configure.add_argument("--model", required=True)
    configure.set_defaults(func=cmd_configure)

    models = sub.add_parser("models", parents=[common])
    models.add_argument("--raw", action="store_true", help="Include raw provider response.")
    models.set_defaults(func=cmd_models)

    ask = sub.add_parser("ask", parents=[common])
    ask.add_argument("--model", help="Override configured model.")
    ask.add_argument("--prompt", help="Inline prompt.")
    ask.add_argument("--prompt-file", help="UTF-8 prompt file.")
    ask.add_argument("--prompt-stdin", action="store_true", help="Read prompt text from standard input.")
    ask.add_argument("--media", action="append", help="Local media path, HTTP(S) URL, or data URL. Repeat for multiple media files.")
    ask.add_argument("--system", help="Optional system message.")
    ask.add_argument("--detail", default="auto", choices=["auto", "low", "high"], help="Image detail hint for providers that support it.")
    ask.add_argument("--max-inline-mb", type=float, default=25.0, help="Maximum local media size to inline as base64.")
    ask.add_argument("--max-tokens", type=int, default=2048)
    ask.add_argument("--temperature", type=float, default=0.0)
    ask.add_argument("--dry-run", action="store_true", help="Build and print the request payload without calling the API.")
    ask.add_argument("--raw", action="store_true", help="Include raw provider response.")
    ask.set_defaults(func=cmd_ask)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
