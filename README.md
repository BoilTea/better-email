<div align="center">

# Better Email

Turn a short brief—or an email thread—into a polished message you can edit, refine, and copy.

[![CI](https://github.com/BoilTea/better-email/actions/workflows/ci.yml/badge.svg)](https://github.com/BoilTea/better-email/actions/workflows/ci.yml)

Desktop-first · Bring your own API provider · No mailbox access required

</div>

![Better Email compose workspace with an editable generated email](docs/images/email-drafter-main.png)

**Better Email** is a lightweight PySide6 desktop app for writing professional email without handing an application access to your inbox. Describe what you need, add optional recipient or conversation context, and generate an editable subject and body through your chosen OpenAI-compatible provider.

## Highlights

- **Context-aware drafting:** provide the tone, relationship, scenario, desired outcome, constraints, and an optional previous email or thread.
- **Editable results:** revise the generated subject and body directly before copying them.
- **Fast refinements:** make a draft shorter, warmer, more formal, proofread it, or enter a custom change request.
- **Provider choice:** use Qwen through SiliconFlow, DeepSeek through its official API, or add multiple custom models with independent OpenAI-compatible endpoints and keys.
- **Responsive requests:** generation runs in the background and can be cancelled without freezing the interface.
- **Custom writing guidance:** edit the system and user prompts, see estimated token counts, or restore the bundled email-writing defaults.

## Quick start

### 1. Install

Python 3.10 or newer is required.

```bash
git clone https://github.com/BoilTea/better-email.git
cd better-email
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows, activate the environment with `.venv\Scripts\activate`.

### 2. Run

```bash
python main.py
```

You can also launch it with `python -m email_drafter`.

### 3. Configure a provider

Open **Settings**, enter an API key or custom endpoint, then select the provider from the **AI Model** menu. No keys are included in the repository.

Under **Custom models**, click **+ Add** to create a model, use the selector to edit another, or click **Delete** to remove one. Each model has its own display name, model ID, base URL, and optional API key. Click **Save** to apply all changes; **Cancel** leaves the saved configuration unchanged. Existing single-model settings are migrated when saved.

![Settings with multiple custom models and compact field labels with hover help](docs/images/email-drafter-models.png)

| App selection | Provider | Model sent to the API |
| --- | --- | --- |
| Qwen 3.6 35B | SiliconFlow | `Qwen/Qwen3.6-35B-A3B` |
| DeepSeek Flash | DeepSeek official API | `deepseek-flash` |
| Custom API | User-configured OpenAI-compatible endpoint | User-configured model ID |

A custom base URL can end at `/v1` or include `/chat/completions`; the app normalizes the request URL. An API key is optional for local servers that do not require authentication.

DeepSeek Flash is the default model and uses the [official Chat Completions API](https://api-docs.deepseek.com/). Thinking is explicitly disabled for fast email drafting and refinement.

## Typical workflow

1. Enter a short brief describing what the email should accomplish.
2. Add useful context such as the recipient relationship, desired outcome, or previous conversation.
3. Generate the draft, then edit its subject and body directly.
4. Apply a one-click or custom refinement and copy the finished email.

Refinement requests always start from the text currently in the editors, so your manual changes are preserved.

Hover over the circled exclamation mark beside a field label in the compose form or Settings for a brief explanation and examples. Settings keeps titles short; URL format, optional API key guidance, and prompt placeholders appear in hover help.

## Prompt customization

The bundled prompts apply scenario diagnosis, relationship-aware tone, clear calls to action, concise structure, and a final quality check. Both prompts are editable from **Settings → Prompts**.

![Prompt settings with editable templates and token estimates](docs/images/email-drafter-settings.png)

The user template supports these placeholders:

`{scenario}`, `{outcome}`, `{sender}`, `{receiver}`, `{relationship}`, `{tone}`, `{content}`, `{previous_email}`, and `{additional_requirements}`.

Token counts are estimates because providers and models may tokenize the same prompt differently.

In Settings, hover over the icon beside **User prompt** to see the available placeholders, or hover over a token count for details about the estimate.

## Privacy and security

- The app does not connect to Gmail, Outlook, or another mailbox.
- Email content and prompts are sent only to the API provider selected for the request.
- API keys and preferences are stored locally through the operating system's `QSettings` location.
- `QSettings` is local configuration storage, not an encrypted credential vault. Avoid storing keys on an untrusted shared account.
- This project does not include analytics or telemetry.

## Development

Install the development dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Run the test suite in headless mode:

```bash
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```

The GitHub Actions workflow compiles the main module and runs the same tests on every push and pull request.

### Build the macOS app

```bash
pyinstaller --clean -y EmailDrafter.spec
```

The spec builds from `main.py` and includes the `email_drafter` package and dropdown asset. The application bundle is created at `dist/EmailDrafter.app`. PyInstaller output is platform-specific, so build release artifacts on the operating system you intend to support.

## Project layout

```text
main.py                    Desktop launcher and PyInstaller entry point
email_drafter/
    app.py                 Application startup
    kernel.py              Provider configuration, prompts, and draft parsing (no Qt)
    network.py             Asynchronous API transport and cancellation
    gui/
        main_window.py     Compose form, draft editor, and UI actions
        settings_dialog.py API key and prompt settings
        widgets.py         Shared widget styling and resource paths
tests/                     Unit and headless UI tests
EmailDrafter.spec           Optimized macOS PyInstaller configuration
docs/images/                README screenshots
```

## Contributing

Issues and focused pull requests are welcome. Please include tests for behavior changes and run the headless test command before opening a pull request. Never commit API keys, local settings, or generated build artifacts.

## License

Licensed under the [MIT License](LICENSE).
