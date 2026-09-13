import os
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QTextEdit

from email_drafter import kernel
from email_drafter.gui.main_window import EmailDrafterGUI
from email_drafter.gui.settings_dialog import SettingsDialog


class PromptTests(unittest.TestCase):
    def test_legacy_custom_model_migrates_and_stays_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(os.path.join(directory, "settings.ini"), QSettings.Format.IniFormat)
            settings.setValue(kernel.CUSTOM_NAME_SETTING, "Old model")
            settings.setValue(kernel.CUSTOM_MODEL_SETTING, "legacy-model")
            settings.setValue(kernel.CUSTOM_BASE_URL_SETTING, "https://example.com/v1")
            settings.setValue(kernel.CUSTOM_API_KEY_SETTING, "legacy-key")
            profiles = kernel.load_custom_models(settings)
            self.assertEqual(profiles[0]["id"], kernel.CUSTOM_MODEL)
            self.assertEqual(profiles[0]["api_key"], "legacy-key")
            kernel.save_custom_models(settings, profiles)
            self.assertEqual(kernel.load_custom_models(settings), profiles)
            kernel.save_custom_models(settings, [])
            settings.sync()
            self.assertEqual(kernel.load_custom_models(settings), [])
            self.assertFalse(settings.contains(kernel.CUSTOM_API_KEY_SETTING))

    def test_token_estimate_handles_empty_ascii_and_cjk_text(self):
        self.assertEqual(kernel.estimate_prompt_tokens(""), 0)
        self.assertEqual(kernel.estimate_prompt_tokens("12345678"), 2)
        self.assertEqual(kernel.estimate_prompt_tokens("你好"), 2)

    def test_render_user_prompt_rejects_unknown_placeholder(self):
        with self.assertRaisesRegex(ValueError, "Unknown prompt placeholder"):
            kernel.render_user_prompt("Hello {unknown}", sender="Sam")

    def test_legacy_defaults_upgrade_without_overwriting_custom_prompts(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(
                os.path.join(directory, "settings.ini"),
                QSettings.Format.IniFormat,
            )
            settings.setValue(
                kernel.SYSTEM_PROMPT_SETTING,
                kernel.LEGACY_DEFAULT_SYSTEM_PROMPT,
            )
            upgraded = kernel.load_prompt_setting(
                settings,
                kernel.SYSTEM_PROMPT_SETTING,
                kernel.DEFAULT_SYSTEM_PROMPT,
                kernel.LEGACY_DEFAULT_SYSTEM_PROMPT,
            )
            self.assertEqual(upgraded, kernel.DEFAULT_SYSTEM_PROMPT)

            settings.setValue(kernel.SYSTEM_PROMPT_SETTING, "My custom prompt")
            custom = kernel.load_prompt_setting(
                settings,
                kernel.SYSTEM_PROMPT_SETTING,
                kernel.DEFAULT_SYSTEM_PROMPT,
                kernel.LEGACY_DEFAULT_SYSTEM_PROMPT,
            )
            self.assertEqual(custom, "My custom prompt")

            settings.setValue(
                kernel.USER_PROMPT_SETTING,
                kernel.PREVIOUS_DEFAULT_USER_PROMPT,
            )
            upgraded_user_prompt = kernel.load_prompt_setting(
                settings,
                kernel.USER_PROMPT_SETTING,
                kernel.DEFAULT_USER_PROMPT,
                (
                    kernel.LEGACY_DEFAULT_USER_PROMPT,
                    kernel.PREVIOUS_DEFAULT_USER_PROMPT,
                ),
            )
            self.assertEqual(upgraded_user_prompt, kernel.DEFAULT_USER_PROMPT)


class ModelRequestTests(unittest.TestCase):
    def test_qwen_request_uses_siliconflow_and_skill_fields(self):
        user_prompt = kernel.build_email_prompt(
            content="Ask Alex to approve the budget.",
            scenario="Request / ask",
            outcome="Approval by Friday",
            sender="Sam",
            receiver="Alex",
        )
        endpoint, payload = kernel.prepare_model_request(
            system_prompt=kernel.DEFAULT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model="Qwen/Qwen3.6-35B-A3B",
            api_key="test-key",
        )

        self.assertEqual(
            endpoint,
            "https://api.siliconflow.cn/v1/chat/completions",
        )
        self.assertEqual(payload["enable_thinking"], False)
        sent_user_prompt = payload["messages"][1]["content"]
        self.assertEqual(payload["model"], "Qwen/Qwen3.6-35B-A3B")
        self.assertIn("Scenario: Request / ask", sent_user_prompt)
        self.assertIn("Desired outcome: Approval by Friday", sent_user_prompt)

    def test_deepseek_uses_official_flash_api_without_thinking(self):
        endpoint, payload = kernel.prepare_model_request(
            system_prompt=kernel.DEFAULT_SYSTEM_PROMPT,
            user_prompt="Draft a brief follow-up email.",
            model="deepseek-flash",
            api_key="test-key",
        )

        self.assertEqual(endpoint, "https://api.deepseek.com/chat/completions")
        self.assertEqual(payload["model"], "deepseek-flash")
        self.assertEqual(payload.get("thinking"), {"type": "disabled"})
        self.assertNotIn("enable_thinking", payload)

    def test_openai_compatible_response_is_parsed(self):
        response = (
            '{"choices":[{"message":{"content":'
            '"**Subject**: Approval needed\\n\\nHi Alex"}}]}'
        )
        result = kernel.parse_model_response(response, "test-model")
        self.assertTrue(result.startswith("**Subject**:"))

    def test_previous_email_is_included_in_default_prompt(self):
        prompt = kernel.build_email_prompt(
            content="Confirm that Tuesday works.",
            previous_email="Can we meet next Tuesday?",
        )

        self.assertIn("Previous email or thread", prompt)
        self.assertIn("Can we meet next Tuesday?", prompt)

    def test_previous_email_is_appended_to_an_older_custom_prompt(self):
        prompt = kernel.build_email_prompt(
            content="Confirm that Tuesday works.",
            previous_email="Can we meet next Tuesday?",
            user_prompt_template="Write this email: {content}",
        )

        self.assertTrue(prompt.startswith("Write this email:"))
        self.assertIn("Can we meet next Tuesday?", prompt)

    def test_refinement_prompt_preserves_current_edited_draft(self):
        prompt = kernel.build_refinement_prompt(
            "Updated timeline",
            "Hi Alex,\n\nThe launch is Tuesday.",
            "Make this warmer",
        )

        self.assertIn("Make this warmer", prompt)
        self.assertIn("**Subject**: Updated timeline", prompt)
        self.assertIn("The launch is Tuesday", prompt)
        self.assertIn("Preserve names, dates", prompt)


class CancellationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def test_cancel_aborts_active_reply(self):
        class FakeReply:
            aborted = False

            def abort(self):
                self.aborted = True

        window = EmailDrafterGUI()
        reply = FakeReply()
        window.api_client.active_reply = reply
        window.cancel_generation()

        self.assertTrue(reply.aborted)
        self.assertTrue(window.api_client.request_was_cancelled)
        self.assertEqual(window.status_label.text(), "Cancelling…")

        window.api_client.active_reply = None
        window.close()


class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def test_multiple_custom_models_save_select_delete_and_cancel(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(os.path.join(directory, "settings.ini"), QSettings.Format.IniFormat)
            window = EmailDrafterGUI()
            window.settings = settings
            dialog = SettingsDialog(settings, window)
            dialog.add_custom_model()
            dialog.custom_name.setText("Cloud model")
            dialog.custom_model.setText("mail-cloud")
            dialog.custom_base_url.setText("https://example.com/v1/")
            dialog.custom_api_key.setText("cloud-key")
            first_id = dialog.custom_models[0]["id"]
            dialog.add_custom_model()
            dialog.custom_name.setText("Local model")
            dialog.custom_model.setText("mail-local")
            dialog.custom_base_url.setText("http://localhost:11434/v1")
            second_id = dialog.custom_models[1]["id"]
            dialog.custom_model_selector.setCurrentIndex(0)
            self.assertEqual(dialog.custom_api_key.text(), "cloud-key")
            dialog.save_settings()

            window.refresh_model_dropdown()
            window.model_dropdown.setCurrentIndex(window.model_dropdown.findData(first_id))
            self.assertEqual(
                window.resolve_model_configuration(),
                (first_id, "cloud-key", "https://example.com/v1", "mail-cloud"),
            )
            cancelled = SettingsDialog(settings, window)
            cancelled.delete_custom_model()
            cancelled.reject()
            self.assertEqual(len(kernel.load_custom_models(settings)), 2)

            reopened = SettingsDialog(settings, window)
            reopened.delete_custom_model()
            reopened.save_settings()
            window.refresh_model_dropdown()
            self.assertEqual(window.model_dropdown.findData(first_id), -1)
            self.assertEqual(window.model_dropdown.currentData(), kernel.DEFAULT_MODEL)
            window.model_dropdown.setCurrentIndex(window.model_dropdown.findData(second_id))
            configuration = window.resolve_model_configuration()
            self.assertEqual(configuration, (second_id, "", "http://localhost:11434/v1", "mail-local"))
            endpoint, payload = kernel.prepare_model_request("System", "Brief", *configuration)
            self.assertEqual(endpoint, "http://localhost:11434/v1/chat/completions")
            self.assertEqual(payload["model"], "mail-local")
            self.assertNotIn("thinking", payload)
            window.close()

    def test_settings_load_and_save_provider_keys_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(
                os.path.join(directory, "settings.ini"),
                QSettings.Format.IniFormat,
            )
            settings.setValue("api_keys/siliconflow", "siliconflow-test-key")
            settings.setValue("api_keys/deepseek", "deepseek-test-key")
            dialog = SettingsDialog(settings)
            try:
                self.assertEqual(dialog.siliconflow_key.text(), "siliconflow-test-key")
                self.assertEqual(dialog.deepseek_key.text(), "deepseek-test-key")
                dialog.siliconflow_key.setText("updated-siliconflow-key")
                dialog.deepseek_key.setText("updated-deepseek-key")
                dialog.save_settings()
                self.assertEqual(
                    settings.value("api_keys/siliconflow"), "updated-siliconflow-key"
                )
                self.assertEqual(
                    settings.value("api_keys/deepseek"), "updated-deepseek-key"
                )
            finally:
                dialog.close()

    def test_only_compose_panel_is_inside_the_scroll_area(self):
        window = EmailDrafterGUI()

        self.assertIs(window.centralWidget(), window.main_widget)
        self.assertIs(window.left_scroll_area.widget(), window.input_widget)
        self.assertTrue(window.left_scroll_area.isAncestorOf(window.input_widget))
        self.assertFalse(window.left_scroll_area.isAncestorOf(window.output_widget))
        help_icons = window.findChildren(QLabel, "fieldHelpIcon")
        help_by_name = {icon.accessibleName(): icon.toolTip() for icon in help_icons}
        self.assertTrue(help_by_name["Help for Tone"])
        self.assertTrue(help_by_name["Help for Relationship"])
        self.assertEqual(
            window.left_scroll_area.verticalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )

        window.resize(1000, 720)
        window.previous_email_toggle.setChecked(True)
        window.show()
        self.qt_app.processEvents()
        scroll_bar = window.left_scroll_area.verticalScrollBar()
        self.assertGreater(scroll_bar.maximum(), 0)
        scroll_bar.setValue(scroll_bar.maximum())
        self.assertEqual(scroll_bar.value(), scroll_bar.maximum())

        window.close()

    def test_multiline_editor_scrollbars_are_hidden_everywhere(self):
        window = EmailDrafterGUI()
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(
                os.path.join(directory, "settings.ini"),
                QSettings.Format.IniFormat,
            )
            settings_dialog = SettingsDialog(settings, window)
            help_by_name = {
                icon.accessibleName(): icon.toolTip()
                for icon in settings_dialog.findChildren(QLabel, "fieldHelpIcon")
            }
            self.assertIn("/v1", help_by_name["Help for Base URL"])
            self.assertIn("Optional", help_by_name["Help for API key"])
            for name in kernel.PROMPT_PLACEHOLDERS:
                self.assertIn("{" + name + "}", help_by_name["Help for User prompt"])
            editors = window.findChildren(QTextEdit)
            editors.extend(settings_dialog.findChildren(QTextEdit))

            self.assertTrue(editors)
            for editor in editors:
                self.assertEqual(
                    editor.horizontalScrollBarPolicy(),
                    Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
                )
                self.assertEqual(
                    editor.verticalScrollBarPolicy(),
                    Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
                )

            settings_dialog.close()
        window.close()

    def test_settings_tabs_scroll_independently_at_compact_size(self):
        window = EmailDrafterGUI()
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(
                os.path.join(directory, "settings.ini"),
                QSettings.Format.IniFormat,
            )
            dialog = SettingsDialog(settings, window)
            dialog.resize(640, 480)
            dialog.show()

            pages = (dialog.api_scroll_area, dialog.prompts_scroll_area)
            self.assertIs(dialog.tabs.widget(0), pages[0])
            self.assertIs(dialog.tabs.widget(1), pages[1])
            for index, page in enumerate(pages):
                dialog.tabs.setCurrentIndex(index)
                self.qt_app.processEvents()
                scroll_bar = page.verticalScrollBar()
                self.assertGreater(scroll_bar.maximum(), 0)
                scroll_bar.setValue(scroll_bar.maximum())
                self.assertEqual(scroll_bar.value(), scroll_bar.maximum())

            dialog.close()
        window.close()

    def test_draft_is_editable_and_refinement_controls_follow_its_state(self):
        window = EmailDrafterGUI()

        self.assertFalse(window.subject_text.isReadOnly())
        self.assertFalse(window.content_output_text.isReadOnly())
        self.assertEqual(
            [button.text() for button in window.refinement_buttons],
            [label for label, _instruction in kernel.REFINEMENT_ACTIONS],
        )
        self.assertFalse(window.apply_refinement_button.isEnabled())

        window.content_output_text.setPlainText("An edited draft")
        self.assertTrue(window.apply_refinement_button.isEnabled())
        self.assertTrue(all(button.isEnabled() for button in window.refinement_buttons))

        window.clear_output()
        self.assertFalse(window.apply_refinement_button.isEnabled())
        window.close()


class AsyncRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def setUp(self):
        test_case = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_length = int(self.headers.get("Content-Length", "0"))
                test_case.request_body = self.rfile.read(content_length)
                if test_case.response_delay:
                    time.sleep(test_case.response_delay)
                response = (
                    b'{"choices":[{"message":{"content":'
                    b'"**Subject**: Local test\\n\\nHi Alex,\\n\\nDone."}}]}'
                )
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(response)))
                    self.end_headers()
                    self.wfile.write(response)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, format, *args):
                pass

        self.request_body = b""
        self.response_delay = 0
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.server_thread.start()
        self.temp_directory = tempfile.TemporaryDirectory()
        settings = QSettings(
            os.path.join(self.temp_directory.name, "settings.ini"),
            QSettings.Format.IniFormat,
        )
        settings.setValue(
            kernel.CUSTOM_BASE_URL_SETTING,
            f"http://127.0.0.1:{self.server.server_port}/v1",
        )
        settings.setValue(kernel.CUSTOM_MODEL_SETTING, "local-test-model")

        self.window = EmailDrafterGUI()
        self.window.settings = settings
        self.window.refresh_model_dropdown()
        custom_index = self.window.model_dropdown.findData(kernel.CUSTOM_MODEL)
        self.window.model_dropdown.setCurrentIndex(custom_index)
        self.window.content_text.setPlainText("Tell Alex the task is done.")
        self.window.previous_email_text.setPlainText(
            "Alex asked whether the task is complete."
        )

    def tearDown(self):
        if self.window.api_client.active_reply is not None:
            self.window.cancel_generation()
            self.wait_until(lambda: self.window.api_client.active_reply is None)
        self.window.close()
        self.server.shutdown()
        self.server.server_close()
        self.temp_directory.cleanup()

    @staticmethod
    def wait_until(predicate, timeout_ms=2000):
        deadline = time.monotonic() + timeout_ms / 1000
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(10)
        return predicate()

    def test_request_completes_without_blocking_the_ui(self):
        self.window.generate_email()

        self.assertIsNotNone(self.window.api_client.active_reply)
        self.assertEqual(self.window.status_label.text(), "Writing…")
        self.assertTrue(self.wait_until(lambda: self.window.api_client.active_reply is None))
        self.assertEqual(self.window.status_label.text(), "Complete")
        self.assertIn("Local test", self.window.subject_text.text())
        self.assertIn(b'"model": "local-test-model"', self.request_body)
        self.assertIn(b"Alex asked whether the task is complete", self.request_body)

    def test_in_flight_request_can_be_cancelled(self):
        self.response_delay = 0.5
        self.window.generate_email()
        QTest.qWait(30)
        self.window.cancel_generation()

        self.assertTrue(self.wait_until(lambda: self.window.api_client.active_reply is None))
        self.assertEqual(self.window.status_label.text(), "Cancelled")
        self.assertEqual(self.window.submit_button.text(), "Generate email")

    def test_edited_draft_can_be_refined_asynchronously(self):
        self.window.subject_text.setText("Edited subject")
        self.window.content_output_text.setPlainText(
            "Hi Alex,\n\nThis is my manually edited body."
        )
        instruction = kernel.REFINEMENT_ACTIONS[0][1]
        self.window.refine_email(instruction)

        self.assertIsNotNone(self.window.api_client.active_reply)
        self.assertEqual(self.window.status_label.text(), "Refining…")
        self.assertFalse(self.window.apply_refinement_button.isEnabled())
        self.assertTrue(self.wait_until(lambda: self.window.api_client.active_reply is None))
        self.assertEqual(self.window.status_label.text(), "Refined")
        self.assertIn(b"Edited subject", self.request_body)
        self.assertIn(b"manually edited body", self.request_body)
        self.assertIn(b"substantially shorter", self.request_body)

    def test_custom_change_request_uses_current_draft(self):
        self.window.subject_text.setText("Budget review")
        self.window.content_output_text.setPlainText("Please review the budget.")
        self.window.custom_refinement_entry.setText(
            "Add a polite request for a response by Thursday"
        )
        self.window.apply_custom_refinement()

        self.assertEqual(self.window.status_label.text(), "Refining…")
        self.assertTrue(self.wait_until(lambda: self.window.api_client.active_reply is None))
        self.assertEqual(self.window.status_label.text(), "Refined")
        self.assertIn(b"Budget review", self.request_body)
        self.assertIn(b"response by Thursday", self.request_body)
        self.assertEqual(self.window.custom_refinement_entry.text(), "")


if __name__ == "__main__":
    unittest.main()
