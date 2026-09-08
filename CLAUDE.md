# CLAUDE.md

This file provides guidance to Claude Code or Codex when working with code in this repository.

## Project Overview

This is a PySide6-based desktop application that drafts emails using AI language models. The application provides a GUI where users can input email parameters (content, scenario, desired outcome, tone, sender, receiver, relationship) and generate professionally formatted emails via external LLM APIs.

## Architecture

**Single-file application**: The entire application logic is contained in `email_drafter_gui.py` with two main components:

1. **API Integration Layer** (`call_large_model`, `draft_email`):
   - Supports SiliconFlow (Qwen), the official DeepSeek API, and one user-defined OpenAI-compatible endpoint
   - Model selection determines which OpenAI-compatible API endpoint and locally saved key to use
   - Returns markdown-formatted email drafts with subject and body

2. **PySide6 GUI** (`EmailDrafterGUI` class):
   - Split-pane layout: left side for inputs, right side for output
   - Input fields: content (required), scenario, desired outcome, tone, sender, receiver, relationship, additional requirements, model selector
   - Default editable prompts implement the workflow in `SKILL.md`: situation diagnosis, scenario selection, CTA design, tone calibration, and quality review
   - Output displays: separate subject and content areas with HTML rendering
   - Parses markdown response to extract subject line and body

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
python email_drafter_gui.py
```

**Dependencies**:
- PySide6
- openai
- markdown

Use the activated project virtual environment for running, testing, and building.

## Local Settings

- API keys are entered through the Settings dialog and saved with `QSettings` in the current user's application settings.
- Custom API settings support an editable display name, model ID, base URL, and optional API key for local servers.
- The system prompt and user prompt template can be customized from the Prompts tab.
- No provider API keys are bundled in the source or packaged application.

## Code Patterns

- The application uses PySide6
- Email drafts are returned in markdown format with the pattern: `**Subject**: [subject]\n\n[body]`
- The GUI uses regex to parse the subject line from the response
- Markdown is converted to HTML for display in QTextEdit widgets
- Default values are provided for all optional fields (tone="neutral", sender="Sender", etc.)
