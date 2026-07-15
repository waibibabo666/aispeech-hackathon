"""Audio transcription parser using local SenseVoice-Small.

Uses sherpa-onnx with SenseVoice-Small INT8 model for fully offline,
high-accuracy Chinese speech recognition.

## Model Setup

SenseVoice-Small INT8 ONNX model (~227MB) should be placed in:
    data/models/sensevoice/
        model.int8.onnx
        tokens.txt

Download:
    https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/
    sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09.tar.bz2
"""

from pathlib import Path

import numpy as np

from .base import BaseParser

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".mpga"}

SENSEVOICE_MODEL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "models" / "sensevoice"
SENSEVOICE_MODEL_FILE = "model.int8.onnx"
SENSEVOICE_TOKENS_FILE = "tokens.txt"

# Lazy-loaded singleton
_recognizer = None


def _check_available() -> bool:
    return (SENSEVOICE_MODEL_DIR / SENSEVOICE_MODEL_FILE).exists() and (
        SENSEVOICE_MODEL_DIR / SENSEVOICE_TOKENS_FILE
    ).exists()


def _get_recognizer():
    global _recognizer
    if _recognizer is not None:
        return _recognizer

    if not _check_available():
        raise FileNotFoundError(
            "SenseVoice model files not found.\n"
            "Download from GitHub:\n"
            "  https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
            "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09.tar.bz2\n"
            "Extract model.int8.onnx + tokens.txt to:\n"
            f"  {SENSEVOICE_MODEL_DIR.resolve()}"
        )

    import sherpa_onnx

    _recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
        model=str(SENSEVOICE_MODEL_DIR / SENSEVOICE_MODEL_FILE),
        tokens=str(SENSEVOICE_MODEL_DIR / SENSEVOICE_TOKENS_FILE),
        num_threads=2,
        use_itn=True,
        language="zh",
    )
    return _recognizer


def _transcribe(file_path: Path) -> str:
    recognizer = _get_recognizer()

    suffix = file_path.suffix.lower()

    if suffix == ".wav":
        import wave
        with wave.open(str(file_path), "rb") as wf:
            sr = wf.getframerate()
            nch = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            raw = wf.readframes(wf.getnframes())
        dtype = np.int16 if sampwidth == 2 else np.int32
        audio = np.frombuffer(raw, dtype=dtype).astype(np.float32) / 32768.0
        if nch > 1:
            audio = audio.reshape(-1, nch).mean(axis=1)
    else:
        import soundfile as sf
        audio, sr = sf.read(str(file_path), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

    # Resample to 16kHz
    if sr != 16000:
        ratio = 16000 / sr
        target_len = int(len(audio) * ratio)
        audio = np.interp(
            np.linspace(0, len(audio) - 1, target_len),
            np.arange(len(audio)),
            audio,
        ).astype(np.float32)

    stream = recognizer.create_stream()
    stream.accept_waveform(16000, audio.astype(np.float32))
    recognizer.decode_stream(stream)
    return stream.result.text


class AudioParser(BaseParser):
    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in SUPPORTED_EXTENSIONS

    def parse(self, file_path: Path) -> str:
        return _transcribe(file_path)
