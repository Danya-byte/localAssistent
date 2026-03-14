# Local Assistant

Lightweight Windows-first desktop assistant built with Python and `PySide6`.

The app is provider-agnostic: the UI is not tied to one model family or one runtime. A user can switch provider, model, and interface language in the app. In the current implementation the built-in adapters are:

- `Ollama` for local models
- `OpenAI-compatible` endpoints for hosted or self-hosted APIs

Assistant actions are separated from model inference. If the model asks to open a page, read/write a file, or run an allowed command, the app shows a blocking approval card. Nothing is executed until the user explicitly clicks allow.

## Current features

- Liquid-glass Qt desktop UI with conversation history
- RU/EN interface with manual in-app switch
- Provider + model selection
- Streaming responses
- Persistent SQLite storage for chats, settings, and pending actions
- Action approval flow for web, file, and command operations
- Export conversation to Markdown or JSON
- Portable build, liquid-glass installer, and ZIP release packaging for Windows

## Local development

### 1. Create the environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
```

### 2. Run the app

```powershell
python -m local_assistant
```

Or:

```powershell
.\scripts\run.ps1
```

### 3. Configure a provider

Option A, local runtime with Ollama:

```powershell
ollama serve
ollama pull qwen2.5:7b
```

Option B, OpenAI-compatible endpoint:

Set `Base URL` and optional `API Key` in the application settings.

## Tests

```powershell
python -m unittest discover -s tests -t .
```

## Build

Portable build:

```powershell
.\scripts\build.ps1
```

Packaged app smoke test:

```powershell
.\scripts\smoke.ps1
```

Full release package:

1. Install Inno Setup 6
2. Run:

```powershell
.\scripts\package.ps1
```

This produces:

- `dist\LocalAssistant\` portable bundle
- `dist\LocalAssistantSetup.exe` liquid-glass installer
- `release\LocalAssistant-win64.zip` archive with the installer inside

## GitHub automation

- `CI` workflow runs tests, portable build, and a headless startup smoke check on every push and pull request.
- `Release` workflow runs on tags like `v0.1.0`, builds the installer and ZIP release, and publishes release artifacts to GitHub.

## Community files

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
- [`SECURITY.md`](SECURITY.md)

## Architecture

- `src/local_assistant/providers/`: provider adapters and registry
- `src/local_assistant/actions/`: action parsing and safe execution
- `src/local_assistant/services/chat_service.py`: orchestration for chat, actions, and exports
- `src/local_assistant/storage.py`: SQLite persistence
- `src/local_assistant/ui/main_window.py`: desktop shell, localization, approval flow

## Data location

By default the app stores data in `%APPDATA%\LocalAssistant`.

Override with:

```powershell
$env:LOCAL_ASSISTANT_HOME = "C:\path\to\custom-home"
```
