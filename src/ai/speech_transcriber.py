"""
OP(AI)UM — Speech Transcriber

Bridges the SpeechRecorder and OpenAI transcription API.
Takes a WAV file path and returns transcribed text.
Runs transcription in a background thread to avoid UI blocking.
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import QObject, Signal

from src.ai.openai_client import OpenAIClient
from src.utils.thread_pool import ThreadPoolManager, Worker


class SpeechTranscriber(QObject):
    """
    Handles speech-to-text transcription via OpenAI API.

    Signals:
        transcription_complete: Emitted with transcribed text.
        transcription_error: Emitted with error message.
        transcription_started: Emitted when transcription begins.
    """

    transcription_complete = Signal(str)
    transcription_error = Signal(str)
    transcription_started = Signal()

    def __init__(
        self,
        openai_client: OpenAIClient,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = openai_client
        self._is_transcribing = False

    @property
    def is_transcribing(self) -> bool:
        return self._is_transcribing

    def transcribe(self, wav_path: str, language: str = "en") -> None:
        """
        Transcribe a WAV file in the background.

        Args:
            wav_path: Path to the WAV audio file.
            language: Language code.
        """
        if self._is_transcribing:
            logger.warning("Transcription already in progress.")
            return

        self._is_transcribing = True
        self.transcription_started.emit()

        worker = Worker(self._do_transcribe, wav_path, language)
        worker.signals.result.connect(self._on_success)
        worker.signals.error.connect(self._on_error)
        worker.signals.finished.connect(self._on_finished)
        ThreadPoolManager.run(worker)

    def _do_transcribe(self, wav_path: str, language: str) -> str:
        """Execute transcription (runs in thread pool)."""
        return self._client.transcribe_audio(wav_path, language=language)

    def _on_success(self, text: object) -> None:
        """Handle successful transcription."""
        transcribed = str(text).strip()
        if transcribed:
            logger.info(f"Transcription: {transcribed[:80]}...")
            self.transcription_complete.emit(transcribed)
        else:
            self.transcription_error.emit("Transcription returned empty text.")

    def _on_error(self, error_msg: str) -> None:
        """Handle transcription error."""
        logger.error(f"Transcription failed: {error_msg}")
        self.transcription_error.emit(f"Transcription failed: {error_msg}")

    def _on_finished(self) -> None:
        """Handle transcription completion."""
        self._is_transcribing = False
