# CLAUDE.md

This file provides guidance to Claude Code or Codex when working with code in this repository.

## Project Overview

This is a PySide6-based desktop application that drafts emails using AI language models. The application provides a GUI where users can input email parameters (content, optional previous-email context, scenario, desired outcome, tone, sender, receiver, relationship) and generate professionally formatted emails via external LLM APIs.

## Architecture

The application lives in the `email_drafter` package. `main.py` is the desktop launcher and the PyInstaller entry point; `python -m email_drafter` uses the same startup function.

- **`kernel.py`**: Provider configuration, settings keys, default prompts, prompt rendering and migration, token estimates, API payload construction, and response/draft parsing. Uses only the Python standard library; it must not import the GUI or Qt. `load_prompt_setting` accepts a settings object exposing `value(...)` without depending on `QSettings` itself.
- **`network.py`**: `ModelRequestClient` owns `QNetworkAccessManager`, the active request, cancellation, and response handling. It emits `succeeded`, `failed`, `cancelled`, and `finished` signals and never displays widgets or message boxes.
- **`gui/main_window.py`**: `EmailDrafterGUI` owns the compose form, editable output, refinement controls, local settings, and UI state. It builds prompts through the kernel and delegates HTTP requests to `ModelRequestClient`.
- **`gui/settings_dialog.py`**: `SettingsDialog` manages local API credentials, custom endpoints, and editable prompts.
- **`gui/widgets.py`**: Shared combo-box styling, scrolling helpers, and source/PyInstaller resource lookup.
- **`app.py`**: Creates the Qt application and opens provider settings when required.

Keep dependencies flowing from the GUI to the kernel/network layer. Import business logic from `email_drafter.kernel`, not from the launcher. Reuse the existing regression suite when refactoring; add cases only for behavior that needs new coverage.

## Building and Distribution

**Prerequisites**: Create a virtual environment with Python 3.10 or newer and install the development dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

**Build executable with PyInstaller**:
```bash
pyinstaller --clean -y EmailDrafter.spec
```

The spec file is configured to:
- Create a macOS `.app` bundle
- Use PyInstaller's supported onedir app-bundle layout (not the deprecated onefile `.app` combination)
- Exclude unnecessary modules (numpy, PIL, tkinter, etc.) to reduce size
- Use UPX compression
- Include the `email_drafter.icns` icon (converted from `.ico` for macOS compatibility)
- Run in windowed mode (no console)

**Output locations**:
- `build/` - temporary build files
- `dist/EmailDrafter.app` - final macOS application bundle

## Running the Application

**Run from source**:
```bash
python main.py
```

**Dependencies**:
- PySide6
- markdown

Use the activated project virtual environment for running, testing, and building.

## Local Settings

- API keys are entered through the Settings dialog and saved with `QSettings` in the current user's application settings.
- Multiple custom model profiles are stored under `custom_api/models` as JSON. Each has a stable ID, display name, model ID, base URL, and optional API key for local servers. The kernel reads legacy single-model settings until the collection is saved; saving removes the legacy keys, so deleted models do not reappear.
- Settings edits stay in memory until Save; Cancel must not change persisted model profiles. The main model selector uses profile IDs, never display names, for routing requests.
- Compose and settings-field explanations are provided by the shared `make_field_label` helper in `gui/widgets.py`. Keep titles concise; put usage instructions, optional-key guidance, and prompt placeholders in hover help.
- The system prompt and user prompt template can be customized from the Prompts tab.
- No provider API keys are bundled in the source or packaged application.

## Code Patterns

- The application uses PySide6
- Email drafts are returned in markdown format with the pattern: `**Subject**: [subject]\n\n[body]`
- The kernel parses the subject line and Markdown body with `split_email_draft`
- Markdown is converted to HTML for display in QTextEdit widgets
- Default values are provided for all optional fields (tone="neutral", sender="Sender", etc.)
