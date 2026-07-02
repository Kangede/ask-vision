# Ask Vision

Ask Vision is a generic agent skill that lets a text-only model ask an external
multimodal model about images, screenshots, diagrams, audio, video, PDFs, or
other media.

It is designed to be usable by any agent runtime that can read a skill folder
and run a Python script, including Claude-style skills, Codex-style skills,
OpenClaw, Hermes, shell-based agents, and other custom agents.

## What It Does

- Uses an external vision or multimodal model as a media-analysis helper.
- Supports OpenAI-compatible and Anthropic-compatible APIs.
- Discovers available models from `/v1/models` when possible.
- Accepts prompts from CLI text, stdin, or a prompt file.
- Accepts media as a local path, public URL, or `data:` URL.
- Reads local media files and sends them as structured API media content.
- Keeps API credentials out of prompts and user-facing output.

## Files

- `SKILL.md` - the skill instructions for agents.
- `scripts/vision_gateway.py` - the provider-compatible helper script.
- `agents/openai.yaml` - optional UI metadata for environments that support it.

## Requirements

- Python 3.10 or newer.
- No third-party Python packages are required.
- An API key for an OpenAI-compatible or Anthropic-compatible multimodal model.

## Configure

List the default config path:

```bash
python scripts/vision_gateway.py config-path
```

Discover models:

```bash
python scripts/vision_gateway.py models \
  --provider auto \
  --base-url https://api.example.com \
  --api-key "$API_KEY"
```

Save a config:

```bash
python scripts/vision_gateway.py configure \
  --provider openai \
  --base-url https://api.example.com \
  --api-key "$API_KEY" \
  --model vision-model-name
```

For Anthropic:

```bash
python scripts/vision_gateway.py configure \
  --provider anthropic \
  --base-url https://api.anthropic.com \
  --api-key "$ANTHROPIC_API_KEY" \
  --model claude-model-name
```

The helper reads settings from CLI flags, then environment variables, then the
config file:

- `ASK_VISION_PROVIDER`
- `ASK_VISION_BASE_URL`
- `ASK_VISION_API_KEY`
- `ASK_VISION_MODEL`
- `ASK_VISION_ANTHROPIC_VERSION`
- `ASK_VISION_CONFIG`

## Ask About Media

Inline prompt:

```bash
python scripts/vision_gateway.py ask \
  --prompt "Extract all visible text from this screenshot." \
  --media screenshot.png
```

Prompt from stdin:

```bash
printf '%s' "Describe the UI state and visible errors." | \
  python scripts/vision_gateway.py ask --prompt-stdin --media screenshot.png
```

Prompt from file:

```bash
python scripts/vision_gateway.py ask \
  --prompt-file prompt.txt \
  --media diagram.png
```

Multiple media inputs:

```bash
python scripts/vision_gateway.py ask \
  --prompt "Compare these two screenshots." \
  --media before.png \
  --media after.png
```

Public URL:

```bash
python scripts/vision_gateway.py ask \
  --prompt "Describe this image." \
  --media https://example.com/image.png
```

## Local Files vs URLs

For local file paths, the helper reads the file in the agent's environment and
embeds it into the API request as structured media content. For image files,
OpenAI-compatible APIs receive an `image_url` data URL, while
Anthropic-compatible APIs receive an `image` block with a base64 source.

For public URLs, the helper does not download the media. It passes the URL to
the provider, and the provider must be able to fetch it. URLs that require
browser login state, cookies, localhost access, or private network access will
usually fail.

Large audio or video files are often better passed as provider-accessible URLs
or shortened clips, because inline API request bodies have size limits.

## Validate

Check Python syntax:

```bash
python -m py_compile scripts/vision_gateway.py
```

Build a request without calling an API:

```bash
python scripts/vision_gateway.py ask \
  --dry-run \
  --provider anthropic \
  --base-url https://api.anthropic.com \
  --model claude-model-name \
  --prompt "Describe this image." \
  --media https://example.com/image.png
```
