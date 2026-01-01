import asyncio
import logging
import os
from collections.abc import AsyncGenerator, Generator

from pysbd import Segmenter

# Set before importing torch/kokoro
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

from kokoro import KPipeline

logger = logging.getLogger(__name__)

# Supported voice identifiers
SUPPORTED_VOICES = {
    "af_heart",  # Female American
    "af_bella",  # Female American
    "af_sarah",  # Female American
    "af_sky",  # Female American
    "am_adam",  # Male American
    "am_michael",  # Male American
    "bf_emma",  # Female British
    "bm_george",  # Male British
    "bm_lewis",  # Male British
}

# Configuration constants
MAX_SPEED = 3.0
MIN_SPEED = 0.1

# Audio format constants
SAMPLE_RATE = 24000  # Hz
CHANNELS = 1  # Mono
SAMPLE_FORMAT = "float32"  # 32-bit floating point
BYTE_ORDER = "little"  # Little endian


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

    def _validate_parameters(self, voice: str, speed: float) -> None:
        """Validate input parameters for audio generation."""
        if voice not in SUPPORTED_VOICES:
            raise ValueError(
                f"Unsupported voice '{voice}'. Supported voices: {sorted(SUPPORTED_VOICES)}"
            )

        if not isinstance(speed, (int, float)):
            raise ValueError(f"Speed must be a number, got {type(speed).__name__}")

        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")

        if speed > MAX_SPEED:
            raise ValueError(f"Speed too high (max {MAX_SPEED}), got {speed}")

        if speed < MIN_SPEED:
            raise ValueError(f"Speed too low (min {MIN_SPEED}), got {speed}")

    def generate_audio(
        self, text: str, voice: str = "af_heart", speed: float = 1.0
    ) -> Generator[bytes, None, None]:
        """Generate audio chunks for text.

        Audio format:
        - Sample rate: 24000 Hz
        - Channels: 1 (mono)
        - Sample format: float32 (32-bit floating point)
        - Byte order: little endian

        Args:
            text: Text to convert to speech
            voice: Voice identifier (must be one of the supported voices)
            speed: Speech speed multiplier (0.1 to 3.0, default 1.0)

        Yields:
            bytes: Raw PCM audio data chunks

        Raises:
            ValueError: If voice is unsupported or speed is out of range
            RuntimeError: If audio generation fails
        """
        self._validate_parameters(voice, speed)

        try:
            generator = self.pipeline(text, voice=voice, speed=speed)
            for chunk in generator:
                try:
                    # Convert torch tensor to numpy, then to bytes
                    audio_array = chunk.audio.cpu().numpy()
                    yield audio_array.tobytes()
                except Exception as e:
                    logger.error(f"Failed to convert audio tensor to bytes: {e}")
                    raise RuntimeError(f"Audio conversion failed: {e}") from e
        except Exception as e:
            if "Failed to convert audio tensor to bytes" in str(e):
                raise  # Re-raise our own conversion errors
            logger.error(f"Audio pipeline failed: {e}")
            raise RuntimeError(f"Audio generation failed: {e}") from e

    async def generate_audio_async(
        self, text: str, voice: str = "af_heart", speed: float = 1.0
    ) -> AsyncGenerator[bytes, None]:
        """Async wrapper for audio generation.

        Audio format:
        - Sample rate: 24000 Hz
        - Channels: 1 (mono)
        - Sample format: float32 (32-bit floating point)
        - Byte order: little endian

        Args:
            text: Text to convert to speech
            voice: Voice identifier (must be one of the supported voices)
            speed: Speech speed multiplier (0.1 to 3.0, default 1.0)

        Yields:
            bytes: Raw PCM audio data chunks

        Raises:
            ValueError: If voice is unsupported or speed is out of range
            RuntimeError: If audio generation fails
        """
        self._validate_parameters(voice, speed)

        try:
            generator = self.pipeline(text, voice=voice, speed=speed)
            for chunk in generator:
                try:
                    # Convert torch tensor to numpy, then to bytes
                    audio_array = chunk.audio.cpu().numpy()
                    yield audio_array.tobytes()
                    # Yield control to allow cancellation checks
                    await asyncio.sleep(0)
                except Exception as e:
                    logger.error(f"Failed to convert audio tensor to bytes: {e}")
                    raise RuntimeError(f"Audio conversion failed: {e}") from e
        except Exception as e:
            if "Failed to convert audio tensor to bytes" in str(e):
                raise  # Re-raise our own conversion errors
            logger.error(f"Audio pipeline failed: {e}")
            raise RuntimeError(f"Audio generation failed: {e}") from e


# Singleton instance
tts_service = TTSService()
