# Model Capability Hints

Use this file when `/v1/models` returns multiple candidates or unfamiliar model names. Do not rely on this list alone. It is only a heuristic candidate-sorting reference, not an authority. Provider aliases change often, deployments can disable media inputs, and gateway vendors may expose custom names. Always prefer the actual provider documentation, the exact model metadata returned by the endpoint, and the result of a real media request. When more than one plausible model remains, ask the user or run a small visual test request if allowed.

Last reviewed: 2026-07-03.

## Selection Rules

1. Prefer exact known vision/multimodal names over generic family names.
2. Prefer names containing `vision`, `visual`, `vl`, `vlm`, `omni`, `multimodal`, or explicit image/video support.
3. Avoid names containing `embed`, `embedding`, `rerank`, `moderation`, `tts`, `asr`, `transcribe`, `image-generation`, `video-generation`, `coder`, or `math` unless the provider documentation explicitly says that model accepts images/video/audio as input.
4. Do not assume a generation model can understand media. Text-to-image, image-to-image, video-generation, OCR-only, ASR-only, and TTS-only models are not general visual recognition chat models.
5. Treat provider-specific endpoints as final truth. A model that is vision-capable in one hosted service may be text-only through another gateway.
6. If the API rejects an image/audio/video request, update the working assumption immediately: the live endpoint result overrides this static list.

## Likely Vision Or Multimodal

### OpenAI-compatible names

- `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano`
- `gpt-5*` general multimodal family aliases when the provider documents image input
- `gpt-4o`, `gpt-4o-mini`
- `gpt-4.1*`
- `gpt-4-turbo` variants with vision support
- `o3`, `o4-mini` variants when the provider documents image input

### Anthropic Claude

- Current Claude 5/4/3.x model aliases that document image input
- `claude-fable-*`
- `claude-opus-*`
- `claude-sonnet-*`
- `claude-haiku-*`

Avoid old `claude-2*` and `claude-instant*` for image input.

### Google Gemini

- `gemini-3.5-flash`
- `gemini-3.1-pro`
- `gemini-3-flash`
- `gemini-2.5-pro`
- `gemini-2.5-flash`
- `gemini-2.5-flash-lite`
- `gemini-2.5-flash-live-preview`
- Older `gemini-1.5-*` deployments when still offered with multimodal input

### Mistral

- `pixtral-large-2411`
- `pixtral-12b-2409`
- Recent Mistral chat models that the provider marks as vision-capable, such as `mistral-large-2512`, `mistral-medium-2508`, `mistral-small-2506`, `ministral-14b-2512`, `ministral-8b-2512`, `ministral-3b-2512`

### xAI

- `grok-4.3`
- `grok-4.3-latest`
- `grok-latest` when it resolves to a vision-capable Grok 4.3 model

### Meta Llama

- `Llama-4-Scout`
- `Llama-4-Maverick`
- `Llama-3.2-Vision-11B`
- `Llama-3.2-Vision-90B`

Generic Llama 1/2/3/3.1/3.3 and Code Llama models are usually text-only.

### Qwen / Alibaba

- `Qwen3.6-*`, `Qwen-3.6-*`, `Qwen/Qwen3.6-*`, and served or quantized aliases with suffixes such as AWQ/GPTQ/GGUF/bnb when the provider exposes them as image-text-to-text or multimodal. This includes `Qwen/Qwen3.6-35B-A3B`; its official model card marks it as image-text-to-text and a causal language model with a vision encoder.
- `Qwen3.6-Plus` and other hosted Qwen3.6 aliases when the platform documents multimodal or visual input for that deployment.
- `Qwen3.5-*` native multimodal variants when the platform documents image/video input.
- `Qwen3-VL-*`
- `Qwen3-Omni-*`
- `Qwen2.5-VL-*`
- `Qwen2.5-Omni-*`
- `Qwen2-VL-*`
- `Qwen-VL`, `Qwen-VL-Chat`, `qwen-vl-plus`, `qwen-vl-max`
- `QvQ-*` visual reasoning variants

Do not assume every generic `qwen3*` alias is visual. Treat Qwen3.6-family names as high-priority vision candidates because many variants and quantized deployments keep the family prefix, but still verify the exact endpoint. `qwen-coder`, `qwen-math`, and many base/instruct text models are not suitable for this skill unless the provider explicitly enables media input.

### Z.AI / GLM / Zhipu

- `glm-5v-turbo`
- `glm-4.6v`
- `glm-4.5v`
- `glm-ocr` for OCR-specific tasks
- `autoglm-phone-multilingual` for phone/GUI-focused multimodal tasks when available

`glm-5.2` is a strong text/coding model, but official Z.AI docs list its input modality as `Text`; choose `glm-5v-turbo` for image/video/file understanding.

### Cohere

- `command-a-plus-05-2026` when the provider documents vision input
- `command-a-vision-07-2025`
- `aya-vision`

Embedding and reranking models are not general visual chat models.

### Amazon Nova / Bedrock

- `amazon.nova-premier-v1:0`
- `amazon.nova-pro-v1:0`
- `amazon.nova-lite-v1:0`

`amazon.nova-micro-v1:0` is text-only.

### Other common open or hosted VLM families

- `llava*`
- `InternVL*`
- `MiniCPM-V*`
- `MiniCPM-o*`
- `Molmo*`
- `Idefics*`
- `Florence*` when exposed for vision-language tasks
- `Kimi-VL*`
- `Kimi-VL-Thinking*`
- `MiniMax-VL-01`

## Likely Text-Only Or Not Suitable

These names should normally be avoided for visual recognition unless the provider explicitly documents media input for that exact deployment:

- `gpt-3.5-turbo`, `text-davinci-*`, `davinci`, `babbage`, `curie`, `ada`
- `claude-2*`, `claude-instant*`
- `text-bison`, `chat-bison`, PaLM-family text models
- `codestral*`, `devstral*`, `magistral*`, `leanstral*`, `mistral-embed`, `mistral-moderation*`
- `grok-build-*`
- `Llama-1`, `Llama-2`, generic `Llama-3`, `Llama-3.1`, `Llama-3.3`, `Code-Llama`
- `qwen-coder*`, `qwen3-coder*`, `qwen-math*`, generic `qwq*`, generic `qwen3*` text/base/instruct variants without multimodal documentation or Qwen3.5/Qwen3.6 multimodal deployment support
- `glm-5.2`, `glm-5.1`, `glm-5`, `glm-5-turbo`, `glm-4.7`, `glm-4.6`, `glm-4.5` when not suffixed with `v`
- `deepseek-chat`, `deepseek-reasoner`, `deepseek-v*` unless a future DeepSeek endpoint explicitly documents image input
- `command-r*`, `command-a-reasoning-*`, `command-a-translate-*`
- `embed*`, `embedding*`, `rerank*`, `moderation*`
- `whisper*`, `asr*`, `tts*`, speech-only models
- `dall-e*`, `imagen*`, `sora*`, `veo*`, `cogview*`, `cogvideo*`, `vidu*`, image/video generation-only models

## Sources To Recheck

- OpenAI model documentation: https://developers.openai.com/api/docs/models
- Anthropic model and vision documentation: https://platform.claude.com/docs/en/about-claude/models/overview and https://platform.claude.com/docs/en/build-with-claude/vision
- Google Gemini models: https://ai.google.dev/gemini-api/docs/models
- Mistral model and vision docs: https://docs.mistral.ai/models/overview and https://docs.mistral.ai/studio-api/conversations/vision
- xAI model docs: https://docs.x.ai/docs/models
- Qwen official pages and model cards: https://qwen.ai/blog and https://huggingface.co/Qwen
- Z.AI docs: https://docs.z.ai/
- Meta Llama announcements/model cards: https://ai.meta.com/
