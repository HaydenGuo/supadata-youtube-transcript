#!/usr/bin/env python3
"""Fetch a YouTube transcript via the Supadata API without exposing its key."""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from supadata import Supadata, SupadataError

from configure_key import config_path, run_setup


POLL_INTERVAL_SECONDS = 2
MAX_POLL_SECONDS = 1800


class SafeApiError(Exception):
    """An API failure safe to report without request headers or secrets."""


def video_id_from_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    video_id = ""
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Provide a valid URL for one YouTube video.")
    if host in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/").split("/")[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith(("/shorts/", "/embed/", "/live/")):
            parts = parsed.path.strip("/").split("/")
            video_id = parts[1] if len(parts) > 1 else ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id):
        raise ValueError("Provide a valid URL for one YouTube video.")
    return video_id


def load_api_key() -> str:
    # An explicitly injected environment value remains useful for isolated runners.
    api_key = os.environ.get("SUPADATA_API_KEY", "").strip()
    if api_key:
        return api_key

    path = config_path()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        run_setup()
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        raise SafeApiError("Could not read the local Supadata configuration file.") from None

    for line in lines:
        match = re.match(r"^\s*SUPADATA_API_KEY\s*=\s*(.*?)\s*$", line)
        if not match:
            continue
        raw_value = match.group(1)
        try:
            value = json.loads(raw_value) if raw_value.startswith('"') else raw_value.strip("'")
        except json.JSONDecodeError:
            raise SafeApiError("The local Supadata configuration file is malformed.") from None
        if isinstance(value, str) and value.strip():
            return value.strip()
    run_setup()
    return load_api_key()


def as_payload(transcript: object) -> dict:
    if is_dataclass(transcript):
        return asdict(transcript)
    raise SafeApiError("Supadata returned an unexpected transcript format.")


def safe_sdk_error(error: SupadataError) -> SafeApiError:
    code = getattr(error, "error", None)
    safe_codes = {"unauthorized", "transcript-unavailable", "limit-exceeded", "upgrade-required"}
    if isinstance(code, str) and code in safe_codes:
        return SafeApiError(f"Supadata reported {code}.")
    return SafeApiError("Supadata rejected the transcript request.")


def fetch_transcript(url: str, api_key: str, lang: str | None, mode: str) -> dict:
    client = Supadata(api_key=api_key)
    try:
        result = client.transcript(url=url, lang=lang, text=False, mode=mode)
        if hasattr(result, "content"):
            return as_payload(result)
        job_id = getattr(result, "job_id", None)
        if not isinstance(job_id, str) or not job_id:
            raise SafeApiError("Supadata returned an asynchronous response without a job ID.")

        deadline = time.monotonic() + MAX_POLL_SECONDS
        while time.monotonic() < deadline:
            time.sleep(POLL_INTERVAL_SECONDS)
            job = client.transcript.get_job_status(job_id)
            if job.status == "completed" and job.result is not None:
                return as_payload(job.result)
            if job.status == "failed":
                raise SafeApiError("Supadata reported that transcript processing failed.")
            if job.status not in {"queued", "active"}:
                raise SafeApiError("Supadata returned an unknown transcript job status.")
        raise SafeApiError("Supadata transcript job timed out before completion.")
    except SupadataError as error:
        raise safe_sdk_error(error) from None
    except requests.RequestException:
        raise SafeApiError("Could not connect to the Supadata API.") from None


def format_timestamp(milliseconds: int) -> str:
    milliseconds = max(0, milliseconds)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def to_srt(payload: dict) -> str:
    chunks = payload.get("content")
    if not isinstance(chunks, list) or not chunks:
        raise SafeApiError("Supadata returned no timestamped caption chunks.")
    lines: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        if not isinstance(chunk, dict) or not isinstance(chunk.get("text"), str):
            continue
        try:
            start = int(chunk["offset"])
            duration = int(chunk["duration"])
        except (KeyError, TypeError, ValueError):
            continue
        end = max(start, start + duration)
        text = chunk["text"].replace("\r", " ").replace("\n", " ").strip()
        if not text:
            continue
        lines.extend(
            [
                str(index),
                f"{format_timestamp(start)} --> {format_timestamp(end)}",
                text,
                "",
            ]
        )
    if not lines:
        raise SafeApiError("Supadata returned no usable timestamped caption chunks.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch a YouTube transcript using Supadata.")
    parser.add_argument("--url", required=True, help="URL of one YouTube video")
    parser.add_argument("--lang", help="Preferred ISO 639-1 language code")
    parser.add_argument("--mode", choices=("native", "auto", "generate"), default="native")
    parser.add_argument("--format", choices=("srt", "txt", "json"), default="srt")
    parser.add_argument("--output", required=True, help="Destination file path")
    args = parser.parse_args()

    try:
        video_id = video_id_from_url(args.url)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    output = Path(args.output).expanduser()
    if output.exists():
        print("error: destination already exists; choose another path to avoid overwriting it.", file=sys.stderr)
        return 2

    try:
        api_key = load_api_key()
    except (SafeApiError, OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
        message = str(exc) if isinstance(exc, SafeApiError) else "Browser key setup did not complete."
        print(f"error: {message}", file=sys.stderr)
        return 2

    try:
        payload = fetch_transcript(args.url, api_key, args.lang, args.mode)
        if args.format == "srt":
            content = to_srt(payload)
        elif args.format == "txt":
            text = payload.get("content")
            if isinstance(text, list):
                text = "\n".join(
                    chunk.get("text", "")
                    for chunk in text
                    if isinstance(chunk, dict) and isinstance(chunk.get("text"), str)
                )
            if not isinstance(text, str) or not text.strip():
                raise SafeApiError("Supadata returned no transcript text.")
            content = text
        else:
            content = json.dumps(payload, ensure_ascii=False, indent=2)
    except SafeApiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content.rstrip() + "\n", encoding="utf-8")
    except OSError:
        print("error: could not write the transcript to the requested output path.", file=sys.stderr)
        return 1

    language = payload.get("lang") or "unspecified"
    print(f"status: success\nvideo_id: {video_id}\nlanguage: {language}\nmode: {args.mode}\noutput: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
