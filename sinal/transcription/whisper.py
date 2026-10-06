"""Adaptador de transcrição para modelos Whisper (faster-whisper / openai-whisper)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from sinal.media.audio import extract_audio
from sinal.media.subtitles import SubtitleCue
from sinal.transcription.base import Transcriber, TranscriptionError


class WhisperTranscriber(Transcriber):
    """Executa reconhecimento de fala local usando Whisper."""

    def __init__(
        self,
        model_size: str = "small",
        *,
        language: str = "pt",
        device: str = "auto",
        compute_type: str = "auto",
    ) -> None:
        self.model_size = model_size
        self.language = language
        self.device = device
        self.compute_type = compute_type

    def transcribe(self, media_path: str | Path) -> list[SubtitleCue]:
        source = Path(media_path)
        if not source.is_file():
            raise FileNotFoundError(f"arquivo de mídia não encontrado: {source}")

        # Tenta importar faster_whisper ou openai whisper
        try:
            from faster_whisper import WhisperModel  # type: ignore[import-untyped]
        except ImportError:
            try:
                import whisper  # type: ignore[import-untyped]
            except ImportError as error:
                raise TranscriptionError(
                    "O motor Whisper requer a instalação do pacote 'faster-whisper' ou 'openai-whisper'. "
                    "Instale com: pip install faster-whisper (ou forneça um arquivo .srt diretamente)"
                ) from error

            # Utiliza openai-whisper se disponível
            with tempfile.TemporaryDirectory() as tmp_dir:
                audio_path = Path(tmp_dir) / "audio.wav"
                extract_audio(source, audio_path, overwrite=True)
                model = whisper.load_model(self.model_size)
                result = model.transcribe(str(audio_path), language=self.language)
                cues: list[SubtitleCue] = []
                for idx, segment in enumerate(result.get("segments", []), start=1):
                    cues.append(
                        SubtitleCue(
                            index=idx,
                            start_seconds=float(segment["start"]),
                            end_seconds=float(segment["end"]),
                            text=str(segment["text"]).strip(),
                        )
                    )
                return cues

        # Utiliza faster-whisper
        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "audio.wav"
            extract_audio(source, audio_path, overwrite=True)

            model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            segments, _info = model.transcribe(
                str(audio_path),
                language=self.language,
                beam_size=5,
            )
            cues = []
            for idx, segment in enumerate(segments, start=1):
                cues.append(
                    SubtitleCue(
                        index=idx,
                        start_seconds=float(segment.start),
                        end_seconds=float(segment.end),
                        text=str(segment.text).strip(),
                    )
                )
            return cues
