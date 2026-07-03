---
name: ask-vision
description: Ask an external multimodal model when the current text model or agent cannot inspect media directly. Use for visual recognition, OCR, screenshots, diagrams, UI inspection, chart/table extraction, layout analysis, image understanding, audio or video understanding, media transcription, or any task where an agent needs observations from images, audio, video, PDFs, screenshots, or other media through OpenAI-compatible or Anthropic-compatible APIs.
---

# Ask Vision

Use this skill as a generic bridge from a text-only model or agent to a user-configured multimodal model. It is not tied to any specific agent runtime. Claude, Codex, OpenClaw, Hermes, shell-based agents, or other systems can use the same workflow if they can run the helper script or make equivalent API calls.

## Workflow

1. Determine exactly what media-grounded answer is needed: OCR text, objects, UI state, chart values, transcript, timestamps, visible layout, ambiguity notes, or another observation.
2. Check the helper config:

   ```bash
   python scripts/vision_gateway.py config-path
   ```

3. On first use, missing config, `401`, `403`, expired key, or unusable endpoint, ask the user for:
   - provider style: `openai`, `anthropic`, or `auto`
   - API base URL or endpoint
   - API key
   - model name only if model discovery cannot provide a clear choice

   Do not echo API keys in user-facing text. If the host agent has a structured user-prompt or choice tool, use it; otherwise ask in chat.

4. Prefer model discovery before asking for a model name:

   ```bash
   python scripts/vision_gateway.py models --provider auto --base-url <api-url> --api-key <api-key>
   ```

   Read `references/model-capabilities.md` when the discovered model names are unfamiliar or when choosing among multiple candidates. Treat that list only as a candidate-sorting reference, not as ground truth. The actual provider documentation, the exact `/v1/models` response, and a real media request result take precedence. Prefer models classified as likely multimodal/vision-capable, avoid known text-only/generation/embedding models for visual recognition, and ask the user when several plausible models remain. If discovery fails, ask the user to manually provide a model name or explain why the endpoint/key appears unusable.

5. Save a working config unless the user says not to persist it:

   ```bash
   python scripts/vision_gateway.py configure --provider <openai|anthropic|auto> --base-url <api-url> --api-key <api-key> --model <model>
   ```

6. Ask the multimodal model with a specific prompt and one or more media inputs:

   ```bash
   python scripts/vision_gateway.py ask --prompt "Inspect the image and extract all visible text." --media <path-or-url>
   ```

   For long generated prompts, avoid making a temporary file by using stdin:

   ```bash
   printf '%s' "<prompt text>" | python scripts/vision_gateway.py ask --prompt-stdin --media <path-or-url>
   ```

   Use `--prompt-file <path>` only when the prompt already lives in a file or the host agent prefers file-based handoff. The helper defaults to `--prompt-encoding auto` for prompt files and stdin, which tries UTF-8, BOM/obvious UTF-16, the terminal locale, GB18030, cp1252, ISO-8859-1, and mac_roman. If a host runtime knows the encoding, pass it explicitly, for example `--prompt-encoding utf-16-le`. If a shell mangles Unicode before Python receives it, use `--prompt-base64 <utf8-base64>` as an ASCII-safe prompt handoff.

7. Treat provider errors as signal. If the model reports unsupported media or the API rejects a content block, explain the limitation and ask for a different provider/model, a URL, a converted artifact, or a smaller clip. If the error is auth-related, re-ask for endpoint/key.

## Media Inputs

Pass each media item with `--media`. The value may be:

- a local file path visible to the running agent process
- an `http` or `https` URL reachable by the model provider
- a `data:` URL when the provider accepts inline data

When a user uploads an attachment to an agent, first resolve how that runtime exposes the upload. If it provides a filesystem path, pass that path; the helper reads the file and inlines it as base64 when appropriate. If the upload is only available as an opaque chat attachment with no path or downloadable URL, the external model cannot read it through this script; ask the user or host runtime for an accessible path/URL or export the attachment first.

The helper supports multiple `--media` flags. It handles images directly for OpenAI-compatible and Anthropic-compatible APIs. It attempts audio, video, PDFs, and other files where the provider format has a plausible content block; unsupported formats should be handled from the API error rather than guessed silently.

## Prompting

Give the external model the media task, not a generic "what is this?" request. Include:

- the user's goal and any necessary context
- the exact output needed, such as OCR, object list, transcript, table, JSON, or visible UI state
- instructions to separate direct observation from inference
- a request to mark unreadable, inaudible, ambiguous, or unsupported regions instead of inventing details

Useful pattern:

```text
You are the media analysis component for a text-only agent.
Inspect the attached media using only observable evidence.
Task: <specific task>
Return concise findings, quote visible/readable text exactly when possible, and flag uncertainty.
```

For OCR/table extraction, request Markdown or JSON. For UI screenshots, request layout hierarchy, labels, states, and errors. For audio/video, request timestamps and ask the model to state whether the submitted media type is actually supported.

## Helper Script

`scripts/vision_gateway.py` uses Python standard library only.

Common commands:

```bash
python scripts/vision_gateway.py config-path
python scripts/vision_gateway.py models --provider auto --base-url <api-url> --api-key <api-key>
python scripts/vision_gateway.py configure --provider anthropic --base-url https://api.anthropic.com --api-key <api-key> --model <model>
python scripts/vision_gateway.py ask --prompt "Describe this image." --media image.png
python scripts/vision_gateway.py ask --prompt-base64 <utf8-base64-prompt> --media image.png
python scripts/vision_gateway.py ask --prompt-stdin --media image.png
python scripts/vision_gateway.py clear-config
```

Output JSON is ASCII-escaped so legacy Windows terminals such as GBK/CP936 PowerShell and non-UTF-8 Unix pipes do not fail when the model returns Unicode text.

The `models` command returns `likely_multimodal`, `likely_text_only`, and `unknown` lists. Treat these as selection hints, not proof: provider aliases change often, gateway deployments vary, and a small test request is the best confirmation when the user permits it.

Settings are read from CLI flags, then environment variables, then the config file:

- `ASK_VISION_PROVIDER`
- `ASK_VISION_BASE_URL`
- `ASK_VISION_API_KEY`
- `ASK_VISION_MODEL`
- `ASK_VISION_ANTHROPIC_VERSION`
- `ASK_VISION_PROMPT_ENCODING`
- `ASK_VISION_CONFIG`

The default config path is OS-generic: `%APPDATA%\ask-vision\config.json` on Windows, `$XDG_CONFIG_HOME/ask-vision/config.json` when available, or `~/.config/ask-vision/config.json`.
