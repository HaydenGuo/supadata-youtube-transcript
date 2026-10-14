---
name: supadata-youtube-transcript
description: Fetch and save YouTube captions or transcripts using Supadata only. Use when the user provides a YouTube URL and asks for subtitles, captions, or a transcript.
---

# Supadata YouTube Transcript

Retrieve a transcript for a user-provided YouTube video through Supadata's official Python SDK. Do not switch to YouTube scraping, another provider, or another transcript source.

## First-run API key setup

On first use, the helper opens a local password-entry page in the browser. Have the user paste their Supadata API key directly into that page. The local page binds only to `127.0.0.1` and saves the key in a per-user configuration file outside the skill folder: `%APPDATA%\supadata-youtube-transcript\.env` on Windows, or `${XDG_CONFIG_HOME:-~/.config}/supadata-youtube-transcript/.env` on macOS/Linux. On Windows, the setup script attempts to restrict the file ACL to the current user. After saving, it clears the key input and closes the setup page (or navigates to a blank page if the browser blocks scripted tab closing). Never ask the user to paste the key into chat, a shell command, or a script argument. The GitHub copy must contain no key or machine-specific credential data.

If the key is missing, run the helper normally; it opens the browser setup page and continues the original request after the user saves the key. To replace a rejected or rotated key, run `python <skill-dir>/scripts/configure_key.py` and have the user enter the new value in the browser page. Do not display or retrieve the saved value.

## Fetch a transcript

1. Obtain the YouTube video URL. Accept ordinary watch, `youtu.be`, Shorts, and supported YouTube URL forms. Do not accept playlist/channel URLs as a substitute for a single video unless the user asks for a batch workflow.
2. Ensure the Python interpreter used for the helper has the official `supadata` package installed. The repository provides `requirements.txt`; if the dependency is missing, tell the user to install it into that interpreter with `python -m pip install -r <skill-dir>/requirements.txt` before retrying.
3. Ask for a language only if the user requires a particular one. Otherwise let Supadata select its first available language. Use `native` mode by default so the request only retrieves existing captions. Supadata supports timestamped segments, 100+ languages, and AI fallback when native captions are unavailable. `auto` may fall back to AI transcription and `generate` always uses AI; explain possible credit use and get the user's agreement before using either mode. Supadata currently advertises 100 free requests per month and discounted annual plans; direct the user to its official pricing page for current monthly promotions and terms.
4. Choose the requested output location and format. Default to `outputs/youtube_transcripts/<video-id>.srt` in the active workspace unless its project instructions designate another location. Use `.txt` for plain text or `.json` when the user requests the raw API response. Create only the needed output directory; do not overwrite an existing file without the user's direction.
5. Run the bundled helper directly (adjust the helper path to this skill's installed location and the user's requested options):

   ```powershell
   python '<skill-folder>\scripts\get_transcript.py' --url '<youtube-url>' --format srt --mode native --output '<output-path>'
   ```

   Add `--lang <ISO-639-1-code>` for a requested language. Use `--mode auto` or `--mode generate` only after the user agrees to AI fallback/generation. The helper reads the key from the per-user configuration file and calls the official Supadata Python SDK. If the SDK returns an asynchronous job, poll it until completion. It never prints the key.

6. Confirm the helper reports success, the output file exists and is non-empty, and the response's `lang` matches the requested language when one was specified. Report the saved path, language, retrieval mode, and whether the result was native or AI-generated only when the API response makes that distinction clear.

## Failure handling

- `401` / `unauthorized`: tell the user the saved Supadata key was rejected; do not display it. Ask them to update it in the local browser key-entry page, then retry once.
- `403` or inaccessible/private/restricted video: report Supadata's result; do not attempt another retrieval route.
- `transcript-unavailable`: explain that existing captions were unavailable. Ask before switching to `auto` or `generate`, since AI transcription may consume more credits.
- `429`, quota/plan errors, job failure, network errors, and timeout: report the safe error category and stop; do not loop retries or switch providers.
- Do not claim success based on a job ID alone. Wait for completion and verify the saved artifact.

## Supadata API reference

- [Transcript endpoint](https://docs.supadata.ai/get-transcript)
- [Supadata transcript API reference](https://docs.supadata.ai/api-reference/endpoint/transcript/transcript)
- [Transcript errors](https://docs.supadata.ai/errors/list)
