# AI Email Drafter

A modern desktop application that turns a short brief into a polished professional email using an OpenAI-compatible API.

## Features

- Qwen 3.6 35B through SiliconFlow
- DeepSeek V4 Flash through the official DeepSeek API
- User-defined OpenAI-compatible endpoints
- Responsive background requests with immediate cancellation
- Skill-aware guidance for meetings, follow-ups, outreach, apologies, escalations, negotiations, and other business scenarios
- Editable system and user prompts with live token estimates
- API keys and preferences stored locally with `QSettings`
- Markdown rendering and one-click email copying

## Requirements

- Python 3.10 or newer
- A SiliconFlow or DeepSeek API key, or an OpenAI-compatible custom endpoint

## Run from source

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python email_drafter_gui.py
```

On first launch, the Settings window opens so you can configure an API provider. Keys are not included in the source code.

## Models and API endpoints

| Selection | API endpoint | Model ID |
| --- | --- | --- |
| Qwen 3.6 35B | SiliconFlow | `Qwen/Qwen3.6-35B-A3B` |
| DeepSeek V4 Flash | DeepSeek official API | `deepseek-v4-flash` |
| Custom API | User configured | User configured |

Custom providers must support the OpenAI Chat Completions interface. A local server can omit the API key if it does not require authentication.

Requests use Qt's asynchronous network stack, so the interface remains responsive while a draft is generated. The Generate button becomes a Cancel button until the request finishes.

## Prompt customization

The default prompts implement the strategy summarized from [SKILL.md](SKILL.md), including scenario diagnosis, relationship-aware tone, clear calls to action, concise structure, and a final quality checklist. Both prompts can be edited or restored from Settings.

The displayed token counts are estimates because each provider and model may tokenize the same text differently.

## Build the macOS application

```bash
python -m pip install -r requirements-dev.txt
pyinstaller --clean -y EmailDrafter.spec
```

## Test

```bash
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```

## Privacy and security

- Email content and prompts are sent only to the API provider selected in the app.
- API keys are saved in the operating system's local `QSettings` storage and are never committed by this project.
- `QSettings` is local storage, not an encrypted credential vault. Avoid using this app on an untrusted shared account.
