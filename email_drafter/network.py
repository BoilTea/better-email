"""Asynchronous OpenAI-compatible HTTP transport, independent of GUI widgets."""

import json

from PySide6.QtCore import QByteArray, QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .kernel import extract_api_error, parse_model_response, prepare_model_request


class ModelRequestClient(QObject):
    """Own one cancellable request and report results through Qt signals."""

    succeeded = Signal(str)
    failed = Signal(str, str)
    cancelled = Signal()
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.network_manager = QNetworkAccessManager(self)
        self.active_reply = None
        self.request_was_cancelled = False
        self.active_model_name = ""

    def start(self, system_prompt, user_prompt, model_configuration):
        if self.active_reply is not None:
            raise RuntimeError("An API request is already in progress.")

        selected_model, api_key, base_url, request_model = model_configuration
        endpoint, payload = prepare_model_request(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=selected_model,
            api_key=api_key,
            base_url=base_url,
            request_model=request_model,
        )
        request = QNetworkRequest(QUrl(endpoint))
        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json"
        )
        request.setRawHeader(QByteArray(b"Accept"), QByteArray(b"application/json"))
        if api_key:
            request.setRawHeader(
                QByteArray(b"Authorization"),
                QByteArray(f"Bearer {api_key}".encode("utf-8")),
            )
        request.setTransferTimeout(60_000)

        self.request_was_cancelled = False
        self.active_model_name = request_model or selected_model
        reply = self.network_manager.post(
            request, QByteArray(json.dumps(payload).encode("utf-8"))
        )
        self.active_reply = reply
        reply.finished.connect(lambda: self._handle_reply(reply))

    def cancel(self):
        if self.active_reply is not None:
            self.request_was_cancelled = True
            self.active_reply.abort()

    def _handle_reply(self, reply):
        network_error = reply.error()
        error_string = reply.errorString()
        if network_error == QNetworkReply.NetworkError.OperationCanceledError:
            raw_response = ""
        else:
            raw_response = bytes(reply.readAll()).decode("utf-8", errors="replace")
        reply.deleteLater()

        if reply is not self.active_reply:
            return

        was_cancelled = (
            self.request_was_cancelled
            or network_error == QNetworkReply.NetworkError.OperationCanceledError
        )
        self.active_reply = None
        self.finished.emit()

        if was_cancelled:
            self.cancelled.emit()
        elif network_error != QNetworkReply.NetworkError.NoError:
            self.failed.emit(
                "Request failed", extract_api_error(raw_response) or error_string
            )
        else:
            try:
                draft = parse_model_response(raw_response, self.active_model_name)
            except Exception as exc:
                self.failed.emit("Invalid response", str(exc))
            else:
                self.succeeded.emit(draft)
