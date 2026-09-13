"""Compose and draft editors, with UI orchestration for API requests."""

import markdown
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QGraphicsDropShadowEffect, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QTextEdit, QVBoxLayout, QWidget,
)

from ..kernel import (
    CUSTOM_MODEL,
    DEFAULT_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_USER_PROMPT,
    EMAIL_SCENARIOS,
    LEGACY_DEFAULT_SYSTEM_PROMPT,
    LEGACY_DEFAULT_USER_PROMPT,
    MODEL_CONFIG,
    PREVIOUS_DEFAULT_USER_PROMPT,
    REFINEMENT_ACTIONS,
    SETTINGS_APPLICATION,
    SETTINGS_ORGANIZATION,
    SYSTEM_PROMPT_SETTING,
    USER_PROMPT_SETTING,
    build_email_prompt,
    build_refinement_prompt,
    is_custom_model,
    load_custom_models,
    load_prompt_setting,
    split_email_draft,
)
from ..network import ModelRequestClient
from .settings_dialog import SettingsDialog
from .widgets import (
    configure_modern_combo_box, hide_text_edit_scrollbars, make_field_label,
)


class EmailDrafterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
        self.api_client = ModelRequestClient(self)
        self.api_client.succeeded.connect(self.handle_generated_draft)
        self.api_client.failed.connect(self.handle_request_error)
        self.api_client.cancelled.connect(self.handle_request_cancelled)
        self.api_client.finished.connect(lambda: self.set_generation_active(False))
        self.active_request_kind = "generate"
        self.setWindowTitle("AI Email Drafter")
        self.setGeometry(70, 60, 1240, 840)
        self.setMinimumSize(1000, 720)
        self.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)

        # Define fonts
        self.label_font = QFont()
        self.label_font.setPointSize(12)
        self.label_font.setBold(True)

        self.input_font = QFont()
        self.input_font.setPointSize(12)

        self.button_font = QFont()
        self.button_font.setPointSize(14)
        self.button_font.setBold(True)

        self.title_font = QFont()
        self.title_font.setPointSize(23)
        self.title_font.setBold(True)

        self.subtitle_font = QFont()
        self.subtitle_font.setPointSize(18)
        self.subtitle_font.setBold(True)

        # Apply modern stylesheet
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f3f6fb;
            }
            QWidget {
                background-color: #f3f6fb;
            }
            QLabel {
                color: #172033;
            }
            QTextEdit, QLineEdit {
                background-color: #f8f9fc;
                border: 1px solid #dfe4ee;
                border-radius: 10px;
                padding: 10px;
                color: #20283a;
                font-size: 14px;
                selection-background-color: #eeebff;
            }
            QTextEdit:focus, QLineEdit:focus {
                border: 2px solid #6d5bd0;
                border-radius: 10px;
                outline: 0;
                background-color: white;
            }
            QComboBox {
                selection-background-color: #6d5bd0;
                selection-color: white;
                background-color: #f8f9fc;
                border: 1px solid #dfe4ee;
                border-radius: 10px;
                padding: 8px 12px;
                color: #20283a;
                font-size: 14px;
                min-height: 25px;
            }
            QComboBox:hover, QComboBox:focus {
                border: 2px solid #6d5bd0;
                border-radius: 10px;
                outline: 0;
                background-color: white;
            }
            QComboBox::drop-down {
                border: none;
                width: 34px;
            }
            QComboBox QAbstractItemView {
                selection-background-color: #eeebff;
                selection-color: #4d3aaf;
                background-color: white;
                border: 1px solid #dfe4ee;
                padding: 5px;
                outline: none;
            }
            QPushButton {
                background-color: #6d5bd0;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #5c49c5;
            }
            QPushButton:pressed {
                background-color: #4d3aaf;
            }
            QPushButton:disabled {
                background-color: #b9b2df;
                color: #f7f6ff;
            }
            QPushButton#clearButton {
                background-color: #95a5a6;
            }
            QPushButton#clearButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton#clearButton:pressed {
                background-color: #6c7a7b;
            }
            QScrollArea {
                border: none;
                background-color: #f3f6fb;
            }
            QTextEdit[readOnly="true"] {
                background-color: #fbfcfe;
                border: 1px solid #dfe4ee;
            }
        """)

        # The right draft panel stays anchored to the window. Only the compose
        # panel scrolls when its fields no longer fit vertically.
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)

        # Main layout
        main_layout = QHBoxLayout(self.main_widget)
        main_layout.setSpacing(24)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Left side: Input fields
        self.input_widget = QWidget()
        self.input_widget.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 16px;
            }
        """)

        # Add shadow effect to input widget
        input_shadow = QGraphicsDropShadowEffect()
        input_shadow.setBlurRadius(28)
        input_shadow.setXOffset(0)
        input_shadow.setYOffset(6)
        input_shadow.setColor(QColor(37, 47, 75, 28))
        self.input_widget.setGraphicsEffect(input_shadow)

        input_layout = QVBoxLayout(self.input_widget)
        input_layout.setSpacing(10)
        input_layout.setContentsMargins(26, 24, 26, 24)

        # Title and settings
        title_row = QHBoxLayout()
        title_label = QLabel("Compose better emails")
        title_label.setFont(self.title_font)
        title_label.setStyleSheet("color: #172033; background-color: transparent;")
        title_row.addWidget(title_label)
        title_row.addStretch()

        settings_button = QPushButton("Settings")
        settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_button.clicked.connect(self.open_settings)
        settings_button.setStyleSheet("""
            QPushButton {
                color: #4d3aaf;
                background-color: #eeebff;
                border: 1px solid #ddd7ff;
                border-radius: 9px;
                padding: 7px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #e1dcff;
            }
        """)
        title_row.addWidget(settings_button)
        input_layout.addLayout(title_row)

        subtitle_label = QLabel("Turn a short brief into a polished, ready-to-send message.")
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet(
            "color: #70798c; background-color: transparent; font-size: 13px; margin-bottom: 8px;"
        )
        input_layout.addWidget(subtitle_label)

        # Previous email
        self.previous_email_toggle = QPushButton(
            "▸  Add previous email or thread (optional)"
        )
        self.previous_email_toggle.setCheckable(True)
        self.previous_email_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.previous_email_toggle.setToolTip(
            "Paste the message you received or earlier conversation context"
        )
        self.previous_email_toggle.setStyleSheet("""
            QPushButton {
                color: #5d50c6;
                background-color: transparent;
                border: none;
                padding: 4px 2px;
                text-align: left;
                font-size: 13px;
                font-weight: 600;
                min-height: 20px;
            }
            QPushButton:hover {
                color: #4d3aaf;
                background-color: #f6f4ff;
                border-radius: 7px;
            }
        """)
        input_layout.addWidget(self.previous_email_toggle)

        self.previous_email_text = QTextEdit()
        self.previous_email_text.setFont(self.input_font)
        self.previous_email_text.setPlaceholderText(
            "Paste the email you are replying to, or relevant earlier messages…"
        )
        self.previous_email_text.setFixedHeight(96)
        self.previous_email_text.setVisible(False)
        self.previous_email_toggle.toggled.connect(self.toggle_previous_email)
        input_layout.addWidget(self.previous_email_text)        

        # Content (required)
        brief_header = QHBoxLayout()
        brief_header.setSpacing(10)
        content_label = make_field_label(
            "What should the email say?",
            "Describe your key message or request.\nThis is the only required writing field.",
            self.label_font,
        )
        brief_header.addWidget(content_label)
        brief_header.addStretch()

        clear_button = QPushButton("Clear brief")
        clear_button.setObjectName("clearButton")
        clear_button.setFont(self.label_font)
        clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_button.setStyleSheet("""
            QPushButton {
                background-color: #f0f2f7;
                color: #4e586b;
                border: 1px solid #e1e5ed;
                border-radius: 8px;
                padding: 5px 10px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #e9e6ff;
                color: #4d3aaf;
                border-color: #d8d2ff;
            }
            QPushButton:pressed {
                background-color: #ded8ff;
            }
        """)
        brief_header.addWidget(clear_button)
        input_layout.addLayout(brief_header)

        self.content_text = QTextEdit()
        self.content_text.setFont(self.input_font)
        self.content_text.setPlaceholderText(
            "Example: Ask the team to send final budget figures by Friday afternoon..."
        )
        self.content_text.setFixedHeight(110)
        clear_button.clicked.connect(self.content_text.clear)
        input_layout.addWidget(self.content_text)

        details_layout = QGridLayout()
        details_layout.setHorizontalSpacing(14)
        details_layout.setVerticalSpacing(8)

        # Tone
        tone_label = make_field_label(
            "Tone", "How the email should sound, e.g. warm, formal, or direct.\nLeave blank for a neutral tone.", self.label_font,
        )
        details_layout.addWidget(tone_label, 0, 0)
        self.tone_entry = QLineEdit()
        self.tone_entry.setFont(self.input_font)
        self.tone_entry.setPlaceholderText("Neutral")
        details_layout.addWidget(self.tone_entry, 1, 0)

        # Sender
        sender_label = make_field_label(
            "Sender", "Your name or email, used in the draft and sign-off.\nLeave blank to use a generic sender.", self.label_font,
        )
        details_layout.addWidget(sender_label, 2, 0)
        self.sender_entry = QLineEdit()
        self.sender_entry.setFont(self.input_font)
        self.sender_entry.setPlaceholderText("Your name or email")
        details_layout.addWidget(self.sender_entry, 3, 0)

        # Receiver
        receiver_label = make_field_label(
            "Receiver", "Who the email is for; helps personalize the greeting.\nLeave blank to use a generic recipient.", self.label_font,
        )
        details_layout.addWidget(receiver_label, 2, 1)
        self.receiver_entry = QLineEdit()
        self.receiver_entry.setFont(self.input_font)
        self.receiver_entry.setPlaceholderText("Recipient name or email")
        details_layout.addWidget(self.receiver_entry, 3, 1)

        # Relationship
        relationship_label = make_field_label(
            "Relationship", "Your relationship with the recipient, e.g. client,\nmanager, or colleague. Helps set the level of formality.", self.label_font,
        )
        details_layout.addWidget(relationship_label, 0, 1)
        self.relationship_entry = QLineEdit()
        self.relationship_entry.setFont(self.input_font)
        self.relationship_entry.setPlaceholderText("Professional")
        details_layout.addWidget(self.relationship_entry, 1, 1)

        # Skill-aware scenario and outcome
        scenario_label = make_field_label(
            "Scenario", "The type of email, such as a follow-up or meeting request.\nAuto-detect chooses a structure from your brief.", self.label_font,
        )
        details_layout.addWidget(scenario_label, 4, 0)
        self.scenario_dropdown = QComboBox()
        self.scenario_dropdown.setFont(self.input_font)
        configure_modern_combo_box(self.scenario_dropdown)
        for display_name, scenario_id in EMAIL_SCENARIOS:
            self.scenario_dropdown.addItem(display_name, scenario_id)
        details_layout.addWidget(self.scenario_dropdown, 5, 0)

        outcome_label = make_field_label(
            "Desired outcome", "What you want the recipient to do next,\ne.g. approve a proposal or confirm a date.", self.label_font,
        )
        details_layout.addWidget(outcome_label, 4, 1)
        self.outcome_entry = QLineEdit()
        self.outcome_entry.setFont(self.input_font)
        self.outcome_entry.setPlaceholderText("e.g., confirm approval by Friday")
        details_layout.addWidget(self.outcome_entry, 5, 1)

        # Additional Requirements
        additional_label = make_field_label(
            "Additional Requirements", "Optional constraints, such as a word limit, language,\ndeadline, or specific details to include.", self.label_font,
        )
        details_layout.addWidget(additional_label, 6, 0, 1, 2)
        self.additional_requirements_entry = QLineEdit()
        self.additional_requirements_entry.setFont(self.input_font)
        self.additional_requirements_entry.setPlaceholderText("e.g., include deadline (optional)")
        details_layout.addWidget(self.additional_requirements_entry, 7, 0, 1, 2)

        # Model dropdown
        model_label = make_field_label(
            "AI Model", "The model used for generation and refinements.\nManage API keys and custom models in Settings.", self.label_font,
        )
        details_layout.addWidget(model_label, 8, 0, 1, 2)
        self.model_dropdown = QComboBox()
        self.model_dropdown.setFont(self.input_font)
        configure_modern_combo_box(self.model_dropdown)
        self.refresh_model_dropdown()
        details_layout.addWidget(self.model_dropdown, 9, 0, 1, 2)

        self.model_hint = QLabel()
        self.model_hint.setStyleSheet(
            "color: #7a8395; background-color: transparent; font-size: 12px; margin-bottom: 4px;"
        )
        self.model_dropdown.currentIndexChanged.connect(self.update_model_hint)
        self.update_model_hint()
        details_layout.addWidget(self.model_hint, 10, 0, 1, 2)
        input_layout.addLayout(details_layout)

        # Submit button
        self.submit_button = QPushButton("Generate email")
        self.submit_button.setFont(self.button_font)
        self.submit_button.clicked.connect(self.handle_submit_action)
        self.submit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_button.setMinimumHeight(45)
        self.submit_button.setStyleSheet("""
            QPushButton {
                background-color: #6d5bd0;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5c49c5;
            }
            QPushButton:pressed {
                background-color: #4d3aaf;
            }
            QPushButton:disabled {
                background-color: #b9b2df;
                color: #f7f6ff;
            }
            QPushButton[cancelMode="true"] {
                background-color: #d75c68;
            }
            QPushButton[cancelMode="true"]:hover {
                background-color: #c94b58;
            }
        """)
        input_layout.addWidget(self.submit_button)

        # Stretch to push content up
        input_layout.addStretch()

        # Right side: Output (Subject and Content)
        self.output_widget = QWidget()
        self.output_widget.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 16px;
            }
        """)

        # Add shadow effect to output widget
        output_shadow = QGraphicsDropShadowEffect()
        output_shadow.setBlurRadius(28)
        output_shadow.setXOffset(0)
        output_shadow.setYOffset(6)
        output_shadow.setColor(QColor(37, 47, 75, 28))
        self.output_widget.setGraphicsEffect(output_shadow)

        output_layout = QVBoxLayout(self.output_widget)
        output_layout.setSpacing(10)
        output_layout.setContentsMargins(26, 24, 26, 24)

        # Output title and generation status
        output_header = QHBoxLayout()
        output_title = QLabel("Your draft")
        output_title.setFont(self.subtitle_font)
        output_title.setStyleSheet("color: #172033; background-color: transparent;")
        output_header.addWidget(output_title)
        output_header.addStretch()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(
            "color: #5d50c6; background-color: #eeebff; border-radius: 10px; "
            "padding: 5px 10px; font-size: 11px; font-weight: 600;"
        )
        output_header.addWidget(self.status_label)
        output_layout.addLayout(output_header)

        output_helper = QLabel("Edit the result directly, refine it, then copy when ready.")
        output_helper.setStyleSheet(
            "color: #70798c; background-color: transparent; font-size: 13px; margin-bottom: 8px;"
        )
        output_layout.addWidget(output_helper)

        # Subject output
        subject_label = QLabel("Subject")
        subject_label.setFont(self.label_font)
        subject_label.setStyleSheet("color: #34495e; background-color: transparent; margin-top: 10px;")
        output_layout.addWidget(subject_label)
        self.subject_text = QLineEdit()
        self.subject_text.setFont(self.input_font)
        self.subject_text.setPlaceholderText("Your subject line will appear here")
        self.subject_text.setFixedHeight(52)
        self.subject_text.setStyleSheet("""
            QLineEdit {
                background-color: #fbfcfe;
                border: 1px solid #dfe4ee;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        output_layout.addWidget(self.subject_text)

        # Content output
        content_label = QLabel("Email Body")
        content_label.setFont(self.label_font)
        content_label.setStyleSheet("color: #34495e; background-color: transparent; margin-top: 10px;")
        output_layout.addWidget(content_label)
        self.content_output_text = QTextEdit()
        self.content_output_text.setFont(self.input_font)
        self.content_output_text.setPlaceholderText("Your polished email will appear here")
        self.content_output_text.setStyleSheet("""
            QTextEdit {
                background-color: #fbfcfe;
                border: 1px solid #dfe4ee;
                border-radius: 10px;
                padding: 15px;
                line-height: 1.6;
            }
        """)
        output_layout.addWidget(self.content_output_text)

        refinement_label = QLabel("Refine draft")
        refinement_label.setFont(self.label_font)
        refinement_label.setStyleSheet(
            "color: #34495e; background-color: transparent; margin-top: 4px;"
        )
        output_layout.addWidget(refinement_label)

        refinement_layout = QGridLayout()
        refinement_layout.setHorizontalSpacing(6)
        refinement_layout.setVerticalSpacing(6)
        self.refinement_buttons = []
        for column, (label, instruction) in enumerate(REFINEMENT_ACTIONS):
            button = QPushButton(label)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setEnabled(False)
            button.setStyleSheet("""
                QPushButton {
                    color: #4d3aaf;
                    background-color: #f3f1ff;
                    border: 1px solid #ddd7ff;
                    border-radius: 8px;
                    padding: 7px 8px;
                    min-height: 18px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #e9e5ff;
                }
                QPushButton:disabled {
                    color: #aaa6c4;
                    background-color: #f5f5f8;
                    border-color: #e7e7ec;
                }
            """)
            button.clicked.connect(
                lambda _checked=False, request=instruction: self.refine_email(request)
            )
            refinement_layout.addWidget(button, 0, column)
            self.refinement_buttons.append(button)
        output_layout.addLayout(refinement_layout)

        custom_refinement_layout = QHBoxLayout()
        custom_refinement_layout.setSpacing(6)
        self.custom_refinement_entry = QLineEdit()
        self.custom_refinement_entry.setPlaceholderText(
            "Custom change, e.g. make the ask clearer…"
        )
        self.custom_refinement_entry.setEnabled(False)
        self.custom_refinement_entry.returnPressed.connect(
            self.apply_custom_refinement
        )
        custom_refinement_layout.addWidget(self.custom_refinement_entry, 1)

        self.apply_refinement_button = QPushButton("Apply")
        self.apply_refinement_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_refinement_button.setEnabled(False)
        self.apply_refinement_button.clicked.connect(self.apply_custom_refinement)
        self.apply_refinement_button.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #6d5bd0;
                border-radius: 8px;
                padding: 8px 12px;
                min-height: 18px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #5c49c5; }
            QPushButton:disabled {
                color: #aaa6c4;
                background-color: #ecebf3;
            }
        """)
        custom_refinement_layout.addWidget(self.apply_refinement_button)
        output_layout.addLayout(custom_refinement_layout)

        output_actions = QHBoxLayout()
        output_actions.addStretch()

        clear_output_button = QPushButton("Clear draft")
        clear_output_button.setObjectName("clearButton")
        clear_output_button.clicked.connect(self.clear_output)
        clear_output_button.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_output_button.setStyleSheet("""
            QPushButton {
                color: #4e586b;
                background-color: #f0f2f7;
                border: 1px solid #e1e5ed;
                border-radius: 10px;
                padding: 9px 14px;
            }
            QPushButton:hover {
                color: #4d3aaf;
                background-color: #e9e6ff;
            }
        """)
        output_actions.addWidget(clear_output_button)

        self.copy_button = QPushButton("Copy email")
        self.copy_button.clicked.connect(self.copy_email)
        self.copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_button.setEnabled(False)
        self.copy_button.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #6d5bd0;
                border-radius: 10px;
                padding: 9px 14px;
            }
            QPushButton:hover {
                background-color: #5c49c5;
            }
            QPushButton:disabled {
                color: #9b94c9;
                background-color: #eeebff;
            }
        """)
        output_actions.addWidget(self.copy_button)
        output_layout.addLayout(output_actions)
        self.subject_text.textChanged.connect(self.update_draft_actions)
        self.content_output_text.textChanged.connect(self.update_draft_actions)

        self.left_scroll_area = QScrollArea()
        self.left_scroll_area.setWidgetResizable(True)
        self.left_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.left_scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.left_scroll_area.setWidget(self.input_widget)

        # The scroll area owns only the compose card; the output card remains a
        # direct child of the main layout and always resizes with the window.
        main_layout.addWidget(self.left_scroll_area)
        main_layout.addWidget(self.output_widget)

        # Give the denser compose form a little more room at narrow widths.
        main_layout.setStretch(0, 11)
        main_layout.setStretch(1, 10)

        # Suppress the oversized native macOS focus halo. The stylesheet above
        # provides the consistent rounded purple focus border instead.
        for widget_type in (QLineEdit, QTextEdit, QComboBox):
            for field in self.findChildren(widget_type):
                field.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        hide_text_edit_scrollbars(self)

    def refresh_model_dropdown(self):
        selected_model = self.model_dropdown.currentData() or DEFAULT_MODEL
        self.custom_models = {
            profile["id"]: profile for profile in load_custom_models(self.settings)
        }
        self.model_dropdown.blockSignals(True)
        self.model_dropdown.clear()
        for model, config in MODEL_CONFIG.items():
            if model == CUSTOM_MODEL:
                continue
            self.model_dropdown.addItem(config["display_name"], model)
        for model, profile in self.custom_models.items():
            name = profile["name"] or profile["model"] or "Custom model"
            self.model_dropdown.addItem(f"{name}  ·  Custom API", model)
            self.model_dropdown.setItemData(
                self.model_dropdown.count() - 1,
                f"{profile['model']}\n{profile['base_url']}",
                Qt.ItemDataRole.ToolTipRole,
            )

        selected_index = self.model_dropdown.findData(selected_model)
        if selected_index < 0:
            selected_index = self.model_dropdown.findData(DEFAULT_MODEL)
        self.model_dropdown.setCurrentIndex(selected_index)
        self.model_dropdown.blockSignals(False)
        if hasattr(self, "model_hint"):
            self.update_model_hint()

    def update_model_hint(self, _index=None):
        model = self.model_dropdown.currentData()
        if is_custom_model(model):
            profile = self.custom_models[model]
            status = "Configured" if profile["model"] and profile["base_url"] else "Setup required"
            self.model_hint.setText(f"{profile['model']}  ·  Custom API  ·  {status}")
            return

        model_config = MODEL_CONFIG[model]
        has_key = bool(
            self.settings.value(model_config["api_key_setting"], "", type=str).strip()
        )
        key_status = "Key saved" if has_key else "Key required"
        if model.startswith("Qwen/"):
            self.model_hint.setText(
                f"SiliconFlow API  ·  Fast mode  ·  {key_status}"
            )
        else:
            self.model_hint.setText(
                f"DeepSeek official API  ·  Fast mode  ·  {key_status}"
            )

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            self.refresh_model_dropdown()
        else:
            self.update_model_hint()
        return result

    def has_any_api_key(self):
        has_provider_key = any(
            self.settings.value(config["api_key_setting"], "", type=str).strip()
            for model, config in MODEL_CONFIG.items()
            if model != CUSTOM_MODEL
        )
        has_custom_api = any(
            profile["model"] and profile["base_url"]
            for profile in load_custom_models(self.settings)
        )
        return has_provider_key or has_custom_api

    def resolve_model_configuration(self):
        """Return the selected provider settings, prompting once if incomplete."""
        def read_configuration():
            selected_model = self.model_dropdown.currentData()
            if is_custom_model(selected_model):
                profile = self.custom_models[selected_model]
                return (
                    selected_model, profile["api_key"], profile["base_url"],
                    profile["model"], bool(profile["model"] and profile["base_url"]),
                )
            model_config = MODEL_CONFIG[selected_model]
            api_key = self.settings.value(
                model_config["api_key_setting"], "", type=str
            ).strip()
            return selected_model, api_key, None, None, bool(api_key)

        selected_model, api_key, base_url, request_model, ready = read_configuration()
        if not ready:
            self.open_settings()
            selected_model, api_key, base_url, request_model, ready = read_configuration()

        if not ready:
            config_key = CUSTOM_MODEL if is_custom_model(selected_model) else selected_model
            model_config = MODEL_CONFIG[config_key]
            requirement = (
                "a model ID and base URL"
                if is_custom_model(selected_model)
                else "an API key"
            )
            QMessageBox.warning(
                self,
                "API configuration required",
                f"Add {requirement} for {model_config['provider']} in Settings first.",
            )
            return None

        return selected_model, api_key, base_url, request_model

    def start_model_request(
        self,
        system_prompt,
        user_prompt,
        model_configuration,
        request_kind="generate",
    ):
        """Start a shared cancellable request for generation or refinement."""
        self.active_request_kind = request_kind
        self.api_client.start(system_prompt, user_prompt, model_configuration)
        self.set_generation_active(True)

    def clear_output(self):
        self.subject_text.clear()
        self.content_output_text.clear()
        self.copy_button.setEnabled(False)
        self.set_refinement_controls_enabled(False)
        self.status_label.setText("Ready")

    def toggle_previous_email(self, expanded):
        """Show reply context only when the user needs it."""
        self.previous_email_text.setVisible(expanded)
        self.previous_email_toggle.setText(
            "▾  Previous email or thread (optional)"
            if expanded
            else "▸  Add previous email or thread (optional)"
        )
        if expanded:
            self.previous_email_text.setFocus()

    def copy_email(self):
        subject = self.subject_text.text().strip()
        body = self.content_output_text.toPlainText().strip()
        if not subject and not body:
            return
        QApplication.clipboard().setText(f"Subject: {subject}\n\n{body}".strip())
        self.status_label.setText("Copied")

    def update_draft_actions(self):
        """Enable copy and refinement whenever an editable draft is present."""
        has_draft = bool(
            self.subject_text.text().strip()
            or self.content_output_text.toPlainText().strip()
        )
        self.copy_button.setEnabled(has_draft)
        if self.api_client.active_reply is None:
            self.set_refinement_controls_enabled(has_draft)

    def set_refinement_controls_enabled(self, enabled):
        for button in self.refinement_buttons:
            button.setEnabled(enabled)
        self.custom_refinement_entry.setEnabled(enabled)
        self.apply_refinement_button.setEnabled(enabled)

    def apply_custom_refinement(self):
        instruction = self.custom_refinement_entry.text().strip()
        if not instruction:
            QMessageBox.warning(
                self,
                "Change request required",
                "Describe how you want the current draft changed.",
            )
            return
        self.refine_email(instruction)

    def refine_email(self, instruction):
        """Revise the user's current edited draft using the selected model."""
        if self.api_client.active_reply is not None:
            return

        model_configuration = self.resolve_model_configuration()
        if model_configuration is None:
            return
        system_prompt = load_prompt_setting(
            self.settings,
            SYSTEM_PROMPT_SETTING,
            DEFAULT_SYSTEM_PROMPT,
            LEGACY_DEFAULT_SYSTEM_PROMPT,
        )
        try:
            user_prompt = build_refinement_prompt(
                self.subject_text.text(),
                self.content_output_text.toPlainText(),
                instruction,
            )
            self.start_model_request(
                system_prompt,
                user_prompt,
                model_configuration,
                request_kind="refine",
            )
        except Exception as exc:
            self.status_label.setText("Error")
            QMessageBox.critical(self, "Refinement failed", str(exc))

    def handle_submit_action(self):
        if self.api_client.active_reply is not None:
            self.cancel_generation()
            return
        self.generate_email()

    def generate_email(self):
        """Start an asynchronous, cancellable email-generation request."""
        content = self.content_text.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "Content required", "Please enter what the email should say.")
            return

        tone = self.tone_entry.text().strip() or "neutral"
        sender = self.sender_entry.text().strip() or "Sender"
        receiver = self.receiver_entry.text().strip() or "Recipient"
        relationship = self.relationship_entry.text().strip() or "professional"
        scenario = self.scenario_dropdown.currentText() or "Auto-detect"
        outcome = self.outcome_entry.text().strip()
        previous_email = self.previous_email_text.toPlainText().strip()
        additional_requirements = self.additional_requirements_entry.text().strip() or ""
        model_configuration = self.resolve_model_configuration()
        if model_configuration is None:
            return

        system_prompt = load_prompt_setting(
            self.settings,
            SYSTEM_PROMPT_SETTING,
            DEFAULT_SYSTEM_PROMPT,
            LEGACY_DEFAULT_SYSTEM_PROMPT,
        )
        user_prompt_template = load_prompt_setting(
            self.settings,
            USER_PROMPT_SETTING,
            DEFAULT_USER_PROMPT,
            (LEGACY_DEFAULT_USER_PROMPT, PREVIOUS_DEFAULT_USER_PROMPT),
        )

        try:
            user_prompt = build_email_prompt(
                content=content,
                tone=tone,
                sender=sender,
                receiver=receiver,
                relationship=relationship,
                previous_email=previous_email,
                additional_requirements=additional_requirements,
                scenario=scenario,
                outcome=outcome,
                user_prompt_template=user_prompt_template,
            )
            self.start_model_request(
                system_prompt,
                user_prompt,
                model_configuration,
                request_kind="generate",
            )
        except Exception as e:
            self.status_label.setText("Error")
            QMessageBox.critical(self, "Error", f"{str(e)}\n")
            return

    def cancel_generation(self):
        """Abort the active network reply without blocking the interface."""
        if self.api_client.active_reply is None:
            return
        self.submit_button.setEnabled(False)
        self.submit_button.setText("Cancelling…")
        self.status_label.setText("Cancelling…")
        self.api_client.cancel()

    def handle_generated_draft(self, email_draft):
        self.display_email_draft(email_draft)
        if self.active_request_kind == "refine":
            self.custom_refinement_entry.clear()
            self.status_label.setText("Refined")
        else:
            self.status_label.setText("Complete")

    def handle_request_error(self, title, message):
        self.status_label.setText("Error")
        QMessageBox.critical(self, title, message)

    def handle_request_cancelled(self):
        self.status_label.setText("Cancelled")

    def display_email_draft(self, email_draft):
        subject, email_content = split_email_draft(email_draft)
        self.subject_text.setText(subject)
        self.content_output_text.setHtml(markdown.markdown(email_content))
        self.update_draft_actions()

    def set_generation_active(self, active):
        self.submit_button.setProperty("cancelMode", active)
        self.submit_button.style().unpolish(self.submit_button)
        self.submit_button.style().polish(self.submit_button)
        self.submit_button.setEnabled(True)
        self.submit_button.setText(
            "Cancel request" if active else "Generate email"
        )
        if active:
            self.set_refinement_controls_enabled(False)
            self.status_label.setText(
                "Refining…" if self.active_request_kind == "refine" else "Writing…"
            )
        else:
            self.update_draft_actions()

    def closeEvent(self, event):
        self.api_client.cancel()
        super().closeEvent(event)

