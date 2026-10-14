#!/usr/bin/env python3
"""Collect the Supadata API key through a loopback-only browser form."""

from __future__ import annotations

import html
import json
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def config_path() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "supadata-youtube-transcript" / ".env"


def apply_windows_acl(path: Path) -> bool:
    if os.name != "nt":
        return True
    username = os.environ.get("USERNAME")
    if not username:
        return False
    try:
        result = subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{username}:(F)"],
            capture_output=True,
            text=True,
            encoding="mbcs",
            errors="replace",
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def save_key(api_key: str) -> tuple[Path, bool]:
    value = api_key.strip()
    if not value or "\r" in value or "\n" in value:
        raise ValueError("API key is empty or has an invalid format.")
    destination = config_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try:
            destination.parent.chmod(0o700)
        except OSError:
            pass
    fd, temp_name = tempfile.mkstemp(prefix=".supadata-", suffix=".tmp", dir=destination.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write("SUPADATA_API_KEY=" + json.dumps(value, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != "nt":
            temp_path.chmod(0o600)
        os.replace(temp_path, destination)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
    if os.name != "nt":
        try:
            destination.chmod(0o600)
        except OSError:
            pass
    return destination, apply_windows_acl(destination)


def setup_html(token: str, nonce: str, destination: Path) -> str:
    shown_path = html.escape(str(destination))
    token_literal = json.dumps(token)
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Supadata 字幕 Skill 配置</title>
<style>
body{{font:16px/1.55 "Segoe UI","Microsoft YaHei",sans-serif;background:#f3f6f4;color:#17231b;margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;box-sizing:border-box}}
main{{width:min(100%,520px);box-sizing:border-box;background:white;border:1px solid #d2ddd5;border-radius:12px;padding:32px;box-shadow:0 16px 45px #18362018}}
h1{{font-size:25px;margin:0 0 8px}} p{{color:#52645a}} label{{display:block;font-weight:650;margin:22px 0 8px}}
input{{box-sizing:border-box;width:100%;padding:12px;border:1px solid #b8c8bd;border-radius:7px;font:inherit}}
button{{margin-top:18px;width:100%;padding:12px;border:0;border-radius:7px;background:#176c49;color:white;font:inherit;font-weight:700;cursor:pointer}}
#status{{min-height:24px;margin-top:14px}} .success{{color:#176c49}} .error{{color:#a33131}}
.path{{font-size:13px;overflow-wrap:anywhere;background:#f4f7f5;padding:10px;border-radius:6px}}
</style></head><body><main><h1>Supadata 字幕 Skill</h1>
<p>请粘贴 Supadata API Key。密钥将保存在本机配置文件，不会写入 Skill 目录或 GitHub 仓库。</p>
<form id="form"><label for="apiKey">API Key</label><input id="apiKey" name="apiKey" type="password" autocomplete="new-password" required autofocus spellcheck="false">
<button type="submit">安全保存并继续</button><div id="status" role="status" aria-live="polite"></div></form>
<p class="path">本机配置文件：{shown_path}</p></main>
<script nonce="{nonce}">
const token={token_literal};const form=document.querySelector('#form');const status=document.querySelector('#status');
form.addEventListener('submit',async event=>{{event.preventDefault();const button=form.querySelector('button');button.disabled=true;status.className='';status.textContent='正在保存…';
try{{const response=await fetch('/save?token='+encodeURIComponent(token),{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{apiKey:document.querySelector('#apiKey').value}})}});const result=await response.json();if(!response.ok)throw new Error(result.error||'保存失败');document.querySelector('#apiKey').value='';form.querySelectorAll('input,button').forEach(item=>item.disabled=true);status.className='success';status.textContent='已保存，正在关闭配置页…';setTimeout(()=>{{window.close();setTimeout(()=>window.location.replace('about:blank'),150);}},350);}}
catch(error){{button.disabled=false;status.className='error';status.textContent=error.message;}}}});
</script></body></html>'''


def run_setup(timeout_seconds: int = 600) -> Path:
    token = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(18)
    destination = config_path()
    state = {"saved": False, "acl_ok": True}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            # Default access logging can leak the one-time setup token in the URL.
            return

        def _headers(self, content_type: str) -> None:
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", f"default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-{nonce}'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/" or parse_qs(parsed.query).get("token", [""])[0] != token:
                self.send_response(404)
                self._headers("text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Not found")
                return
            body = setup_html(token, nonce, destination).encode("utf-8")
            self.send_response(200)
            self._headers("text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            origin = self.headers.get("Origin", "")
            if origin != f"http://127.0.0.1:{self.server.server_port}" or parse_qs(parsed.query).get("token", [""])[0] != token:
                self.send_response(403)
                self._headers("application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(b'{"error":"Invalid local setup request."}')
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 16_384:
                    raise ValueError("Request size is invalid.")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict) or not isinstance(payload.get("apiKey"), str):
                    raise ValueError("API key is required.")
                _, acl_ok = save_key(payload["apiKey"])
                state["saved"] = True
                state["acl_ok"] = acl_ok
                response = json.dumps({"ok": True}).encode("utf-8")
                self.send_response(200)
            except (UnicodeDecodeError, json.JSONDecodeError, OSError, ValueError) as exc:
                response = json.dumps({"error": str(exc)}).encode("utf-8")
                self.send_response(400)
            self._headers("application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
            if state["saved"]:
                threading.Thread(target=self.server.shutdown, daemon=True).start()

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 1
    url = f"http://127.0.0.1:{server.server_port}/?token={token}"
    print(f"SUPADATA_SETUP_URL={url}", flush=True)
    print("SUPADATA_SETUP_BROWSER_OPENED=" + ("1" if webbrowser.open(url) else "0"), flush=True)
    deadline = time.monotonic() + timeout_seconds
    try:
        while not state["saved"] and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if not state["saved"]:
        raise RuntimeError("Browser key entry timed out.")
    if not state["acl_ok"]:
        print("warning: the configuration file was saved, but Windows ACL tightening failed.", file=sys.stderr)
    print(f"SUPADATA_CONFIG_SAVED={destination}", flush=True)
    return destination


if __name__ == "__main__":
    try:
        run_setup()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
