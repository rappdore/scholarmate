import asyncio
import os
from collections.abc import AsyncGenerator, Generator

from pysbd import Segmenter

# Set before importing torch/kokoro
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

from kokoro import KPipeline


class TTSService:
    _instance = None
    _pipeline = None
    _segmenter = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def pipeline(self) -> KPipeline:
        if self._pipeline is None:
            self._pipeline = KPipeline(lang_code="a")  # American English
        return self._pipeline

    @property
    def segmenter(self) -> Segmenter:
        if self._segmenter is None:
            self._segmenter = Segmenter(language="en", clean=False)
        return self._segmenter

    def segment_text(self, text: str) -> list[str]:
        """Split text into sentences."""
        sentences = self.segmenter.segment(text)
        # Filter empty sentences
        return [s.strip() for s in sentences if s.strip()]

    def generate_audio(
        self, text: str, voice: str = "af_heart", speed: float = 1.0
    ) -> Generator[bytes, None, None]:
        """Generate audio chunks for text. Yields raw PCM float32 bytes."""
        generator = self.pipeline(text, voice=voice, speed=speed)
        for chunk in generator:
            # Convert torch tensor to numpy, then to bytes
            audio_array = chunk.audio.cpu().numpy()
            yield audio_array.tobytes()

    async def generate_audio_async(
        self, text: str, voice: str = "af_heart", speed: float = 1.0
    ) -> AsyncGenerator[bytes, None]:
        """Async wrapper for audio generation."""
        generator = self.pipeline(text, voice=voice, speed=speed)

        for chunk in generator:
            # Convert torch tensor to numpy, then to bytes
            audio_array = chunk.audio.cpu().numpy()
            yield audio_array.tobytes()
            # Yield control to allow cancellation checks
            await asyncio.sleep(0)


# Singleton instance
tts_service = TTSService()
