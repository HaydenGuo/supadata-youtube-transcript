# Supadata YouTube Transcript

A standalone Codex Skill for fetching and saving a single YouTube video's captions through the official Supadata Python SDK.

## Features

- Uses the official Supadata Python SDK; no YouTube scraping or alternate transcript provider.
- Opens a local browser page for API key entry on first run. After saving, the page closes automatically (or switches to a blank page if the browser blocks closing it).
- Browser entry avoids copying the key into chat, terminal commands, or environment files by hand. The page is served only on the local machine, then clears the input and closes after saving; the key stays outside the repository.
- Retrieves existing captions by default (`native` mode). AI transcription modes require explicit user agreement.
- Saves timestamped SRT, plain text, or JSON.
- Supadata supports timestamped subtitle segments and 100+ languages, with AI fallback when native captions are unavailable. This Skill defaults to native captions so AI processing is not triggered without consent.

## Requirements

- Python 3.10 or newer
- A Supadata API key
- The official [Supadata Python SDK](https://github.com/supadata-ai/py) (`supadata`)
- A Codex environment that supports Skills

Install the dependency with `python -m pip install -r requirements.txt`.

## Install

Clone this repository into the Codex skills directory:

```powershell
git clone https://github.com/HaydenGuo/supadata-youtube-transcript.git `
  "$env:USERPROFILE\.codex\skills\supadata-youtube-transcript"
```

On macOS/Linux:

```sh
git clone https://github.com/HaydenGuo/supadata-youtube-transcript.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/supadata-youtube-transcript"
```

Restart Codex or start a new task so it discovers the Skill.

## Use

Invoke `$supadata-youtube-transcript` with a YouTube video URL. The helper opens the local setup page if the key has not been configured, saves it outside the Skill directory, then continues the original request.

To run the helper directly:

```powershell
python -m pip install -r .\requirements.txt
python .\scripts\get_transcript.py `
  --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" `
  --mode native `
  --format srt `
  --output ".\dQw4w9WgXcQ.srt"
```

Configuration locations:

- Windows: `%APPDATA%\supadata-youtube-transcript\.env`
- macOS/Linux: `${XDG_CONFIG_HOME:-~/.config}/supadata-youtube-transcript/.env`

## License

MIT. See [LICENSE](LICENSE).

## Supadata features and pricing

Supadata's YouTube transcript service returns timestamped subtitle segments, supports 100+ languages, and uses one API and official SDK across supported video platforms. It does not require a separate YouTube Data API key or OAuth flow. If native captions are missing, its API can generate a transcript with AI; that mode can consume additional credits, so this Skill uses native captions by default and requires agreement before switching. See the [Supadata YouTube transcript overview](https://supadata.ai/youtube-transcript-api) and [transcript documentation](https://docs.supadata.ai/get-transcript).

Supadata currently advertises 100 free requests per month without a credit card, and discounted annual plan variants. Monthly plan prices and promotions can change; check the [official pricing page](https://supadata.ai/pricing) for current terms. A transcript request costs one credit; AI-generated transcripts are billed by video minute according to Supadata's pricing page.

## Security

The browser setup page is served only from `127.0.0.1`, uses a one-time random token, disables caching, and does not log request bodies. The key is entered into that local page, stored outside the cloned repository, cleared from the form, and the page closes after save when the browser allows it. On Windows, the setup script attempts to restrict the config file ACL to the current user. Never commit the local configuration file or share the API key in chat.
