"""
OP(AI)UM — Speech Recorder

Records audio from the microphone for speech-to-text transcription.
Uses sounddevice for cross-platform audio capture.
Toggle mode: click to start, click to stop.
"""

from __future__ import annotations

import tempfile
import wave
from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import QObject, Signal, QThread
from loguru import logger


class AudioRecorderWorker(QThread):
    """Background thread for audio recording."""

    recording_finished = Signal(str)  # Path to WAV file
    recording_error = Signal(str)
    level_update = Signal(float)  # Audio level 0-1

    SAMPLE_RATE = 16000
    CHANNELS = 1
    DTYPE = "int16"

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._is_recording = False
        self._frames: list[np.ndarray] = []

    def run(self) -> None:
        """Record audio until stopped."""
        try:
            import sounddevice as sd

            self._is_recording = True
            self._frames = []

            logger.info("Recording started.")

            def audio_callback(indata: np.ndarray, frames: int, time_info: Any, status: Any) -> None:
                if status:
                    logger.debug(f"Audio status: {status}")
                if self._is_recording:
                    self._frames.append(indata.copy())
                    # Calculate audio level for visual feedback
                    level = float(np.abs(indata).mean()) / 32768.0
                    self.level_update.emit(min(level * 10, 1.0))

            with sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype=self.DTYPE,
                callback=audio_callback,
                blocksize=1024,
            ):
                while self._is_recording:
                    sd.sleep(100)

            # Save to WAV
            if self._frames:
                wav_path = self._save_wav()
                logger.info(f"Recording saved: {wav_path}")
                self.recording_finished.emit(wav_path)
            else:
                self.recording_error.emit("No audio data recorded.")

        except ImportError:
            self.recording_error.emit("sounddevice not installed. Run: pip install sounddevice")
        except Exception as e:
            logger.error(f"Recording error: {e}")
            self.recording_error.emit(str(e))

    def stop_recording(self) -> None:
        """Signal the recording to stop."""
        self._is_recording = False

    def _save_wav(self) -> str:
        """Save recorded frames to a temporary WAV file."""
        audio_data = np.concatenate(self._frames, axis=0)

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, prefix="opaium_")
        wav_path = tmp.name
        tmp.close()

        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(2)  # 16-bit = 2 bytes
            wf.setframerate(self.SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())

        return wav_path


# Need to import Any for the callback type hint
from typing import Any


class SpeechRecorder(QObject):
    """
    High-level speech recorder with toggle start/stop.

    Signals:
        recording_started: Emitted when recording begins.
        recording_stopped: Emitted when recording stops.
        transcription_ready: Emitted with the transcribed text.
        audio_level: Emitted with current mic level (0-1).
        error: Emitted on any error.
    """

    recording_started = Signal()
    recording_stopped = Signal()
    transcription_ready = Signal(str)
    audio_level = Signal(float)
    error = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[AudioRecorderWorker] = None
        self._is_recording = False
        self._last_wav_path: Optional[str] = None

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def toggle(self) -> None:
        """Toggle recording on/off."""
        if self._is_recording:
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        """Start recording."""
        if self._is_recording:
            return

        self._worker = AudioRecorderWorker(self)
        self._worker.recording_finished.connect(self._on_recording_finished)
        self._worker.recording_error.connect(self._on_error)
        self._worker.level_update.connect(self.audio_level.emit)
        self._worker.start()

        self._is_recording = True
        self.recording_started.emit()

    def stop(self) -> None:
        """Stop recording."""
        if not self._is_recording or self._worker is None:
            return

        self._worker.stop_recording()
        self._worker.wait(5000)  # Wait up to 5s

        self._is_recording = False
        self.recording_stopped.emit()

    def _on_recording_finished(self, wav_path: str) -> None:
        """Handle completed recording."""
        self._last_wav_path = wav_path
        logger.info(f"Recording ready for transcription: {wav_path}")
        # Transcription will be triggered by the AI engine
        self.transcription_ready.emit(wav_path)

    def _on_error(self, error_msg: str) -> None:
        """Handle recording error."""
        self._is_recording = False
        self.error.emit(error_msg)

    def get_last_recording_path(self) -> Optional[str]:
        """Get the path to the last recorded WAV file."""
        return self._last_wav_path

    def cleanup(self) -> None:
        """Clean up temporary WAV files."""
        if self._last_wav_path:
            try:
                Path(self._last_wav_path).unlink(missing_ok=True)
            except Exception:
                pass
