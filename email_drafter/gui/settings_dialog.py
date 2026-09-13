"""Local API credentials and prompt settings dialog."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

from ..kernel import (
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_USER_PROMPT,
    LEGACY_DEFAULT_SYSTEM_PROMPT,
    LEGACY_DEFAULT_USER_PROMPT,
    MODEL_CONFIG,
    PREVIOUS_DEFAULT_USER_PROMPT,
    PROMPT_PLACEHOLDERS,
    SYSTEM_PROMPT_SETTING,
    USER_PROMPT_SETTING,
    estimate_prompt_tokens,
    load_custom_models,
    load_prompt_setting,
    new_custom_model,
    render_user_prompt,
    save_custom_models,
)
from .widgets import (
    configure_modern_combo_box, hide_text_edit_scrollbars, make_field_label,
    make_settings_scroll_page,
)


class SettingsDialog(QDialog):
    """Local API key and prompt editor."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.custom_models = load_custom_models(settings)
        self._loading_custom_model = False
        self.setWindowTitle("Email Drafter Settings")
        self.resize(760, 700)
        self.setMinimumSize(640, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        layout.addWidget(make_field_label(
            "Settings",
            "API keys and prompts are saved locally on this device.\n"
            "Save applies your changes; Cancel discards them.\n"
            f"Settings file: {settings.fileName()}",
            title_font,
        ))

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #dfe4ee;
                border-radius: 10px;
                background-color: white;
                top: -1px;
            }
            QTabBar::tab {
                color: #60697b;
                background-color: #eef1f6;
                border: 1px solid #dfe4ee;
                min-width: 130px;
                padding: 12px 24px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                color: #4d3aaf;
                background-color: white;
                border-bottom-color: white;
                font-weight: 600;
            }
        """)
        layout.addWidget(self.tabs, 1)

        api_tab = QWidget()
        api_layout = QVBoxLayout(api_tab)
        api_layout.setContentsMargins(20, 20, 20, 20)
        api_layout.setSpacing(10)

        provider_keys_grid = QGridLayout()
        provider_keys_grid.setHorizontalSpacing(12)
        provider_keys_grid.setVerticalSpacing(7)

        siliconflow_label = make_field_label(
            "SiliconFlow", "API key for the built-in Qwen model via SiliconFlow.\nThe key is stored locally and sent only to SiliconFlow.", self._label_font(),
        )
        provider_keys_grid.addWidget(siliconflow_label, 0, 0)
        self.siliconflow_key = QLineEdit()
        self.siliconflow_key.setMinimumHeight(36)
        self.siliconflow_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.siliconflow_key.setPlaceholderText("Enter your SiliconFlow API key")
        self.siliconflow_key.setText(
            settings.value(MODEL_CONFIG["Qwen/Qwen3.6-35B-A3B"]["api_key_setting"], "", type=str)
        )
        provider_keys_grid.addWidget(self.siliconflow_key, 1, 0)

        deepseek_label = make_field_label(
            "DeepSeek", "API key for the built-in DeepSeek Flash model.\nUse a key issued by the official DeepSeek API.", self._label_font(),
        )
        provider_keys_grid.addWidget(deepseek_label, 0, 1)
        self.deepseek_key = QLineEdit()
        self.deepseek_key.setMinimumHeight(36)
        self.deepseek_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.deepseek_key.setPlaceholderText("Enter your DeepSeek API key")
        self.deepseek_key.setText(
            settings.value(MODEL_CONFIG["deepseek-flash"]["api_key_setting"], "", type=str)
        )
        provider_keys_grid.addWidget(self.deepseek_key, 1, 1)
        api_layout.addLayout(provider_keys_grid)

        api_layout.addSpacing(12)
        custom_heading = make_field_label(
            "Custom models",
            "Add models from any OpenAI-compatible provider or local server.\n"
            "Each model has its own endpoint and key.\n"
            "Use + Add or Delete, then Save to apply your changes.",
            self._label_font(),
        )
        api_layout.addWidget(custom_heading)

        custom_toolbar = QHBoxLayout()
        custom_toolbar.setSpacing(8)
        self.custom_model_selector = QComboBox()
        configure_modern_combo_box(self.custom_model_selector)
        self.custom_model_selector.setMinimumWidth(160)
        self.custom_model_selector.setPlaceholderText("No custom models yet")
        custom_toolbar.addWidget(self.custom_model_selector, 1)
        self.add_model_button = QPushButton("+ Add")
        self.add_model_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_model_button.setStyleSheet("""
            QPushButton {
                color: #4d3aaf; background-color: #eeebff;
                border: 1px solid #ddd7ff; border-radius: 8px;
                padding: 9px 14px; font-size: 13px; font-weight: 600;
            }
            QPushButton:hover { background-color: #e1dcff; }
        """)
        self.add_model_button.clicked.connect(self.add_custom_model)
        custom_toolbar.addWidget(self.add_model_button)
        self.delete_model_button = QPushButton("Delete")
        self.delete_model_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_model_button.setStyleSheet("""
            QPushButton {
                color: #b34457; background-color: #fff1f3;
                border: 1px solid #f2d8de; border-radius: 8px;
                padding: 9px 14px; font-weight: 600;
            }
            QPushButton:hover { background-color: #ffe4e9; }
            QPushButton:disabled { color: #aaa6b4; background-color: #f5f5f8; }
        """)
        self.delete_model_button.clicked.connect(self.delete_custom_model)
        custom_toolbar.addWidget(self.delete_model_button)
        api_layout.addLayout(custom_toolbar)

        custom_grid = QGridLayout()
        custom_grid.setHorizontalSpacing(12)
        custom_grid.setVerticalSpacing(7)

        custom_name_label = make_field_label(
            "Name", "A label used in the model selector, e.g. Work or Local.\nLeave blank to display the model ID.", self._label_font(),
        )
        custom_grid.addWidget(custom_name_label, 0, 0)
        custom_model_label = make_field_label(
            "Model ID", "The exact model identifier expected by your provider.\nFor example: llama3.2 for a local Ollama server.", self._label_font(),
        )
        custom_grid.addWidget(custom_model_label, 0, 1)

        self.custom_name = QLineEdit()
        self.custom_name.setMinimumHeight(36)
        self.custom_name.setPlaceholderText("Example: Local Ollama")
        custom_grid.addWidget(self.custom_name, 1, 0)
        self.custom_model = QLineEdit()
        self.custom_model.setMinimumHeight(36)
        self.custom_model.setPlaceholderText("Example: llama3.2")
        custom_grid.addWidget(self.custom_model, 1, 1)

        custom_url_label = make_field_label(
            "Base URL", "Your provider's OpenAI-compatible API address,\nusually ending in /v1. A full /chat/completions URL also works.", self._label_font(),
        )
        custom_grid.addWidget(custom_url_label, 2, 0, 1, 2)
        self.custom_base_url = QLineEdit()
        self.custom_base_url.setMinimumHeight(36)
        self.custom_base_url.setPlaceholderText("Example: http://localhost:11434/v1")
        custom_grid.addWidget(self.custom_base_url, 3, 0, 1, 2)

        custom_key_label = make_field_label(
            "API key", "The API key for this custom model.\nOptional for local servers that do not require authentication.", self._label_font(),
        )
        custom_grid.addWidget(custom_key_label, 4, 0, 1, 2)
        self.custom_api_key = QLineEdit()
        self.custom_api_key.setMinimumHeight(36)
        self.custom_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.custom_api_key.setPlaceholderText("Enter the custom provider API key")
        custom_grid.addWidget(self.custom_api_key, 5, 0, 1, 2)
        api_layout.addLayout(custom_grid)

        self.custom_fields = {
            "name": self.custom_name,
            "model": self.custom_model,
            "base_url": self.custom_base_url,
            "api_key": self.custom_api_key,
        }
        for field in self.custom_fields.values():
            field.textChanged.connect(self.update_custom_model)
        self.custom_model_selector.currentIndexChanged.connect(self.select_custom_model)
        self.refresh_custom_model_selector()

        self.show_keys_checkbox = QCheckBox("Show API keys")
        self.show_keys_checkbox.stateChanged.connect(self.toggle_key_visibility)
        api_layout.addWidget(self.show_keys_checkbox)
        api_layout.addStretch()

        self.api_scroll_area = make_settings_scroll_page(api_tab)
        self.tabs.addTab(self.api_scroll_area, "API Keys")

        prompts_tab = QWidget()
        prompts_layout = QVBoxLayout(prompts_tab)
        prompts_layout.setContentsMargins(20, 20, 20, 20)
        prompts_layout.setSpacing(8)

        system_header = QHBoxLayout()
        system_label = make_field_label(
            "System prompt", "Sets the writing style, structure, and rules\nused for drafting and refinement.", self._label_font(),
        )
        system_header.addWidget(system_label)
        system_header.addStretch()
        self.system_prompt_token_count = QLabel()
        self.system_prompt_token_count.setStyleSheet("color: #777f91; font-size: 12px;")
        self.system_prompt_token_count.setToolTip(
            "Estimated token count. Exact counts vary by provider and model."
        )
        system_header.addWidget(self.system_prompt_token_count)
        prompts_layout.addLayout(system_header)
        self.system_prompt_edit = QTextEdit()
        self.system_prompt_edit.setPlainText(
            load_prompt_setting(
                settings,
                SYSTEM_PROMPT_SETTING,
                DEFAULT_SYSTEM_PROMPT,
                LEGACY_DEFAULT_SYSTEM_PROMPT,
            )
        )
        self.system_prompt_edit.setFixedHeight(180)
        prompts_layout.addWidget(self.system_prompt_edit)

        user_header = QHBoxLayout()
        placeholder_names = ", ".join(f"{{{name}}}" for name in PROMPT_PLACEHOLDERS)
        user_label = make_field_label(
            "User prompt",
            "A template filled with your compose inputs before generation.\n"
            "Available placeholders:\n"
            + "\n".join(
                ", ".join(f"{{{name}}}" for name in PROMPT_PLACEHOLDERS[index:index + 3])
                for index in range(0, len(PROMPT_PLACEHOLDERS), 3)
            ),
            self._label_font(),
        )
        user_header.addWidget(user_label)
        user_header.addStretch()
        self.user_prompt_token_count = QLabel()
        self.user_prompt_token_count.setStyleSheet("color: #777f91; font-size: 12px;")
        self.user_prompt_token_count.setToolTip(
            "Estimated tokens in this template before input values are inserted.\n"
            "Exact counts vary by provider and model."
        )
        user_header.addWidget(self.user_prompt_token_count)
        prompts_layout.addLayout(user_header)
        self.user_prompt_edit = QTextEdit()
        self.user_prompt_edit.setPlainText(
            load_prompt_setting(
                settings,
                USER_PROMPT_SETTING,
                DEFAULT_USER_PROMPT,
                (LEGACY_DEFAULT_USER_PROMPT, PREVIOUS_DEFAULT_USER_PROMPT),
            )
        )
        self.user_prompt_edit.setMinimumHeight(150)
        prompts_layout.addWidget(self.user_prompt_edit, 1)

        self.user_prompt_edit.setAccessibleDescription(
            "Prompt template placeholders: " + placeholder_names
        )

        self.system_prompt_edit.textChanged.connect(self.update_prompt_token_counts)
        self.user_prompt_edit.textChanged.connect(self.update_prompt_token_counts)
        self.update_prompt_token_counts()

        self.prompts_scroll_area = make_settings_scroll_page(prompts_tab)
        self.tabs.addTab(self.prompts_scroll_area, "Prompts")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        restore_button = buttons.addButton(
            "Restore skill defaults", QDialogButtonBox.ButtonRole.ResetRole
        )
        restore_button.clicked.connect(self.restore_default_prompts)
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        for widget_type in (QLineEdit, QTextEdit):
            for field in self.findChildren(widget_type):
                field.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        hide_text_edit_scrollbars(self)

    @staticmethod
    def _label_font():
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        return font

    def toggle_key_visibility(self, _state):
        echo_mode = (
            QLineEdit.EchoMode.Normal
            if self.show_keys_checkbox.isChecked()
            else QLineEdit.EchoMode.Password
        )
        self.siliconflow_key.setEchoMode(echo_mode)
        self.deepseek_key.setEchoMode(echo_mode)
        self.custom_api_key.setEchoMode(echo_mode)

    def refresh_custom_model_selector(self, selected_id=None):
        self.custom_model_selector.blockSignals(True)
        self.custom_model_selector.clear()
        for profile in self.custom_models:
            label = profile["name"] or profile["model"] or "New custom model"
            self.custom_model_selector.addItem(label, profile["id"])
            self.custom_model_selector.setItemData(
                self.custom_model_selector.count() - 1,
                f"{profile['model']}\n{profile['base_url']}",
                Qt.ItemDataRole.ToolTipRole,
            )
        index = self.custom_model_selector.findData(selected_id)
        self.custom_model_selector.setCurrentIndex(
            max(index, 0) if self.custom_models else -1
        )
        self.custom_model_selector.blockSignals(False)
        self.select_custom_model(self.custom_model_selector.currentIndex())

    def select_custom_model(self, index):
        self._loading_custom_model = True
        profile = self.custom_models[index] if index >= 0 else {}
        for key, field in self.custom_fields.items():
            field.setText(profile.get(key, ""))
            field.setEnabled(index >= 0)
        self.delete_model_button.setEnabled(index >= 0)
        self._loading_custom_model = False

    def update_custom_model(self, _text):
        index = self.custom_model_selector.currentIndex()
        if self._loading_custom_model or index < 0:
            return
        profile = self.custom_models[index]
        profile.update({
            key: field.text().strip() for key, field in self.custom_fields.items()
        })
        self.custom_model_selector.setItemText(
            index, profile["name"] or profile["model"] or "New custom model"
        )
        self.custom_model_selector.setItemData(
            index, f"{profile['model']}\n{profile['base_url']}",
            Qt.ItemDataRole.ToolTipRole,
        )

    def add_custom_model(self):
        profile = new_custom_model()
        self.custom_models.append(profile)
        self.refresh_custom_model_selector(profile["id"])
        self.custom_name.setFocus()

    def delete_custom_model(self):
        index = self.custom_model_selector.currentIndex()
        if index < 0:
            return
        self.custom_models.pop(index)
        selected = (
            self.custom_models[min(index, len(self.custom_models) - 1)]
            if self.custom_models else None
        )
        self.refresh_custom_model_selector(selected["id"] if selected else None)

    def restore_default_prompts(self):
        self.system_prompt_edit.setPlainText(DEFAULT_SYSTEM_PROMPT)
        self.user_prompt_edit.setPlainText(DEFAULT_USER_PROMPT)

    def update_prompt_token_counts(self):
        system_tokens = estimate_prompt_tokens(
            self.system_prompt_edit.toPlainText()
        )
        user_tokens = estimate_prompt_tokens(
            self.user_prompt_edit.toPlainText()
        )
        self.system_prompt_token_count.setText(f"≈ {system_tokens:,} tokens")
        self.user_prompt_token_count.setText(f"≈ {user_tokens:,} tokens")

    def save_settings(self):
        system_prompt = self.system_prompt_edit.toPlainText().strip()
        user_prompt = self.user_prompt_edit.toPlainText().strip()
        if not system_prompt or not user_prompt:
            QMessageBox.warning(self, "Prompts required", "Both prompts must contain text.")
            return

        sample_values = {name: name for name in PROMPT_PLACEHOLDERS}
        try:
            render_user_prompt(user_prompt, **sample_values)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid prompt template", str(exc))
            return

        try:
            save_custom_models(self.settings, self.custom_models)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid custom model", str(exc))
            return

        self.settings.setValue(
            MODEL_CONFIG["Qwen/Qwen3.6-35B-A3B"]["api_key_setting"],
            self.siliconflow_key.text().strip(),
        )
        self.settings.setValue(
            MODEL_CONFIG["deepseek-flash"]["api_key_setting"],
            self.deepseek_key.text().strip(),
        )
        self.settings.setValue(SYSTEM_PROMPT_SETTING, system_prompt)
        self.settings.setValue(USER_PROMPT_SETTING, user_prompt)
        self.settings.sync()
        self.accept()

