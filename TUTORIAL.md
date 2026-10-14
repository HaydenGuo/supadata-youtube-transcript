# A Practical Tutorial: Download YouTube Subtitles with Supadata's Python SDK

YouTube subtitles are useful when you want to research a talk, search a long interview, quote a video accurately, create notes, or feed spoken content into a local analysis workflow. Getting those captions into a dependable file can be awkward: videos expose different caption tracks, languages vary, and some videos have no native captions at all. Supadata provides one transcript API and official SDK for requesting timestamped transcript segments, while this small Codex Skill turns the response into an SRT, text, or JSON file.

This tutorial walks through the complete workflow: install the project, enter the API key through a local browser page, call the Supadata Python SDK, and save subtitles. The examples default to `native` mode, which requests existing captions. Supadata also supports AI transcription when native captions are unavailable, but generated audio transcription uses additional credits, so the Skill requires agreement before using an AI mode.

## Why use Supadata for YouTube subtitles?

The response is structured into caption segments with text, an offset, a duration, and language information. Those timestamps make the result useful for SRT exports, searchable notes, quote lookup, and video editing. Supadata advertises support for more than 100 languages and provides language detection, so a caller can omit a preferred language or request one with a language code. If a video has no native captions, Supadata can also generate a transcript with AI through its transcript service. The same SDK style and response structure make it possible to keep the rest of an application simple while choosing native retrieval or an explicitly approved AI mode.

The service is not limited to YouTube, but this repository intentionally focuses on a single YouTube video. It does not scrape YouTube pages or require a separate YouTube Data API key or OAuth flow. Instead, the application authenticates to Supadata with a Supadata API key. The official Python SDK handles the request and response objects, and this repository adds the practical pieces around it: local key setup, safe defaults, asynchronous job polling, and subtitle file output.

Read the [official YouTube transcript overview](https://supadata.ai/youtube-transcript-api) and [transcript API documentation](https://docs.supadata.ai/get-transcript) for service behavior and supported options.

## Install the Skill and its SDK dependency

Clone this repository into your Codex skills folder, or download it and place the folder there manually. On Windows, the default Codex skills directory is `%USERPROFILE%\.codex\skills`; on macOS or Linux, use `${CODEX_HOME:-~/.codex}/skills`. The installed folder should be named `supadata-youtube-transcript` so Codex can find its `SKILL.md` entrypoint.

The scripts use Python 3.10 or newer and Supadata's official Python package. From the project folder, install the dependency into the same Python environment you will use to run the script:

```sh
python -m pip install -r requirements.txt
```

The dependency file constrains the package to the compatible Supadata SDK 1.x series. The [official SDK repository](https://github.com/supadata-ai/py) contains its full API reference and additional examples.

## Enter your API key in the browser

On first use, run the setup script:

```sh
python scripts/configure_key.py
```

The script opens a password-style form in your browser and serves it only from `127.0.0.1` on your computer. Paste the Supadata API key into that page and save it. The form clears the key and closes automatically after saving; if a browser prevents a tab from closing itself, it navigates to a blank page instead. The key is stored in a per-user configuration file outside the repository, not in the project, the terminal command, or this tutorial. On Windows the setup script also attempts to restrict that file's permissions to your account. This keeps the usual workflow convenient and reduces the chance of accidentally committing or sharing a key.

Never put a real API key into source code, a public issue, a chat message, or a committed `.env` file. If the key is rejected or rotated, run the setup script again and replace it through the local browser page.

## Call the SDK directly

For an application that already has its own secret manager, the core SDK call is short. Store the key using your application's private configuration mechanism, then pass it to the client. This example uses an environment variable only to keep the sample independent from the Skill's browser configuration; it is not needed when using this repository's helper.

```python
import os
import time

from supadata import Supadata, SupadataError

client = Supadata(api_key=os.environ["SUPADATA_API_KEY"])
video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

try:
    transcript = client.transcript(
        url=video_url,
        lang="en",       # Optional; omit to let Supadata choose a language.
        text=False,       # Keep timestamped segments for subtitle output.
        mode="native",   # Request existing captions only.
    )

    if hasattr(transcript, "job_id"):
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            job = client.transcript.get_job_status(transcript.job_id)
            if job.status == "completed":
                transcript = job.result
                break
            if job.status == "failed":
                raise RuntimeError("Supadata could not complete this transcript job.")
            time.sleep(2)
        else:
            raise TimeoutError("Transcript job did not finish before the timeout.")

    print(f"Language: {transcript.lang}")
    for segment in transcript.content:
        start_seconds = segment.offset / 1000
        end_seconds = (segment.offset + segment.duration) / 1000
        print(f"{start_seconds:.3f}-{end_seconds:.3f}\t{segment.text}")
except SupadataError as error:
    # Print the stable error code, not request headers or secret values.
    print(f"Supadata request failed: {error.error}")
```

Most captioned videos return a transcript immediately. Some requests can be asynchronous; in that case, the SDK returns a job ID and `get_job_status` is used until the job completes. Do not treat the job ID itself as the transcript. The example waits for a completed result, handles a failed job, and stops after a bounded timeout rather than polling forever.

Each timestamp is measured in milliseconds. The example converts the offsets for readable console output, while the repository helper formats segments as valid SRT timestamps. For large workflows, consider caching results because published video transcripts normally do not need to be fetched repeatedly. Follow the service's current rate limits and terms.

## Save a subtitle file with the bundled helper

For a ready-to-use file, use the bundled helper. It reads the key from the local browser configuration, calls the official SDK, waits for asynchronous processing when needed, and writes the chosen output format. The destination must not already exist; this avoids silently replacing another transcript.

```sh
python scripts/get_transcript.py \
  --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
  --mode native \
  --format srt \
  --output "./transcripts/dQw4w9WgXcQ.srt"
```

Use `--format txt` for plain text or `--format json` for structured data. Add `--lang zh` or another ISO language code only when you want to prefer a particular language. If that caption language is unavailable, Supadata may return its selected available language; check the reported `language` field and the content before relying on the result.

## Choose a retrieval mode and understand credits

The default `native` mode retrieves existing captions and is the safest choice when you want the video's supplied subtitle track. `auto` can fall back to AI transcription when there are no captions. `generate` explicitly asks for a generated transcript. AI speech recognition can take longer and costs more than retrieving an existing transcript. Before running either AI mode, explain the potential credit use and obtain agreement from the person requesting the transcript.

Supadata's pricing page currently lists 100 free requests each month without a credit card and says one transcript request costs one credit. AI-generated transcription is listed at two credits per generated minute. Plans, rates, and promotions may change, so verify the [current official pricing page](https://supadata.ai/pricing) before estimating costs. Unused monthly credits do not roll over according to the current pricing FAQ.

## Try the project

Start with a short, public video that has captions, use `native` mode, and inspect the SRT timestamps and language. Then try a preferred language or a text export. Only test AI fallback when the content has no native captions and you have agreed to its additional credit use. This progression makes it easy to see what the service returns while keeping costs predictable.

If this tutorial helped, you can [try Supadata with my referral link](https://supadata.ai/r/GW08810R). This is a referral link; I may receive benefits under Supadata's current referral program if you sign up through it. Please check Supadata's terms for current eligibility and reward details.

---

This tutorial is part of [Supadata YouTube Transcript](https://github.com/HaydenGuo/supadata-youtube-transcript), a standalone Codex Skill using Supadata's official Python SDK.
