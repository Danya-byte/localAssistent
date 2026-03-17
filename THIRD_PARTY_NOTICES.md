# Third-Party Notices

This project redistributes or depends on third-party software. The entries below
identify the main bundled/runtime components and their upstream sources.

## llama.cpp

- Project: `llama.cpp`
- Upstream: <https://github.com/ggml-org/llama.cpp>
- Copyright: `llama.cpp` contributors
- License: MIT
- Usage: Bundled local inference runtime (`llama-server.exe` and required DLLs)

## PySide6 / Qt

- Project: `PySide6`
- Upstream: <https://doc.qt.io/qtforpython-6/>
- Copyright: The Qt Company Ltd. and contributors
- License: LGPLv3 / GPL-compatible Qt terms, depending on distribution terms
- Usage: Desktop UI framework

## Qwen Open-Weight Models

- Project: `Qwen` / `Qwen2.5` / `Qwen3`
- Upstream: <https://github.com/QwenLM/Qwen>
- Model sources: official Qwen repositories on Hugging Face / ModelScope
- License: Apache 2.0 for the cited open-weight model families
- Usage: Curated downloadable local model catalog

## Runtime Bundle Provenance

- Runtime source: verified Windows `llama.cpp` release bundle selected by the
  maintainers for this application release
- Bundled files: only `llama-server.exe`, required runtime DLLs, and runtime
  notices/provenance files required for redistribution

See release documentation and release checksums for the exact runtime version and
artifact hashes shipped with each tagged release.
