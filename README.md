# Local Assistant

Lightweight Windows-first desktop assistant built with Python and `PySide6`.

The current product flow is local-first through `llama.cpp` and open-source Qwen GGUF models. The app manages a curated local model catalog, supports one-click model download, and asks for explicit approval before any external action.

Assistant actions are separated from model inference. If the model asks to open a page, read/write a file, or run an allowed command, the app shows a blocking approval card. Nothing is executed until the user explicitly clicks allow.

## Current features

- Liquid-glass Qt desktop UI with conversation history
- RU/EN interface with manual in-app switch
- Curated local Qwen model catalog with lightweight and powerful options
- Background local model downloads with floating progress status
- Streaming responses
- Persistent SQLite storage for chats, settings, and pending actions
- Action approval flow for web, file, and command operations
- Export conversation to Markdown or JSON
- Portable build and Windows installer
- Release checksums and release manifest for installer/runtime verification

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

### 3. Prepare local runtime

Open the Profile page in the app and:

1. Choose a local model
2. Press `Install`
3. Wait for the download to finish
4. The app starts the bundled local runtime automatically
5. Press `Refresh` only if the app asks you to retry the local runtime status

## Tests

```powershell
.\scripts\test.ps1
```

Coverage gate:

```powershell
.\scripts\coverage.ps1
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

Verify release artifacts:

```powershell
.\scripts\verify_release.ps1
```

This produces:

- `dist\LocalAssistant\` portable bundle
- `dist\LocalAssistantSetup.exe` installer
- `release\LocalAssistant-manifest.json` trusted release manifest
- `release\LocalAssistantSetup.sha256.txt` installer checksum
- `release\LocalAssistant-win64.zip` archive with the installer inside
- `release\LocalAssistant-win64.sha256.txt` ZIP checksum

## GitHub automation

- `CI` workflow runs compile checks, the full test suite, a strict `100%` coverage gate, portable build, and a headless startup smoke check on every push and pull request.
- `Release` workflow runs on tags like `v0.2.0`, but it cannot publish artifacts unless compile checks, tests, the `100%` coverage gate, build, smoke, and package steps all pass.

## Community files

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
- [`SECURITY.md`](SECURITY.md)
- [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

## Architecture

- `src/local_assistant/providers/`: local runtime adapter and registry
- `src/local_assistant/actions/`: action parsing and safe execution
- `src/local_assistant/services/chat_service.py`: orchestration for chat, local models, actions, and exports
- `src/local_assistant/storage.py`: SQLite persistence
- `src/local_assistant/ui/main_window.py`: desktop shell, localization, approval flow

## Data location

By default the app stores data in `%APPDATA%\LocalAssistant`.

Override with:

```powershell
$env:LOCAL_ASSISTANT_HOME = "C:\path\to\custom-home"
```

Logs are written to `%APPDATA%\LocalAssistant\logs\app.log` by default.

## Update recovery

- If the app cannot repair or self-update, open `%APPDATA%\LocalAssistant\logs\app.log` and review the latest installer or manifest error.
- The chat UI and local model flow should continue working even when a trusted release manifest is unavailable.
- Public releases must include `LocalAssistantSetup.exe`, `LocalAssistantPatch.zip`, and `LocalAssistant-manifest.json` as one verified set.
