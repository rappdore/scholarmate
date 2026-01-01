import asyncio
import logging
import os
from collections.abc import AsyncGenerator, Generator

from pysbd import Segmenter

# Set before importing torch/kokoro
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

from kokoro import KPipeline

logger = logging.getLogger(__name__)


class AudioConversionError(Exception):
    """Raised when audio tensor conversion to bytes fails."""

    pass


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

# Audio format constants (Kokoro pipeline output format)
# Not yet used programmatically but reserved for WAV encoding, client negotiation, etc.
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

    def _convert_chunk_to_bytes(self, chunk) -> bytes:
        """Convert a pipeline audio chunk to bytes.

        Args:
            chunk: Audio chunk from the pipeline containing a torch tensor

        Returns:
            bytes: Raw PCM audio data

        Raises:
            AudioConversionError: If audio conversion fails
        """
        try:
            audio_array = chunk.audio.cpu().numpy()
            return audio_array.tobytes()
        except Exception as e:
            logger.error(f"Failed to convert audio tensor to bytes: {e}")
            raise AudioConversionError(f"Audio conversion failed: {e}") from e

    def _generate_audio_chunks(
        self, text: str, voice: str, speed: float
    ) -> Generator[bytes, None, None]:
        """Generate audio chunks for streaming.

        Args:
            text: Text to convert to speech
            voice: Voice identifier (already validated)
            speed: Speech speed multiplier (already validated)

        Yields:
            bytes: Raw PCM audio data chunks

        Raises:
            AudioConversionError: If audio conversion fails
            RuntimeError: If audio generation fails
        """
        try:
            generator = self.pipeline(text, voice=voice, speed=speed)
            for chunk in generator:
                yield self._convert_chunk_to_bytes(chunk)
        except AudioConversionError:
            raise
        except Exception as e:
            logger.error(f"Audio pipeline failed: {e}")
            raise RuntimeError(f"Audio generation failed: {e}") from e

    def _generate_audio_chunks_sync(
        self, text: str, voice: str, speed: float
    ) -> list[bytes]:
        """Collect all audio chunks synchronously.

        This method runs the entire pipeline and collects all chunks
        into a list. Use this for thread pool execution where generators
        cannot cross thread boundaries.

        Args:
            text: Text to convert to speech
            voice: Voice identifier (already validated)
            speed: Speech speed multiplier (already validated)

        Returns:
            list[bytes]: All audio data chunks

        Raises:
            AudioConversionError: If audio conversion fails
            RuntimeError: If audio generation fails
        """
        return list(self._generate_audio_chunks(text, voice, speed))

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
        yield from self._generate_audio_chunks(text, voice, speed)

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
            # Run the CPU-bound pipeline in a thread pool to avoid blocking the event loop
            chunks = await asyncio.to_thread(
                self._generate_audio_chunks_sync, text, voice, speed
            )

            # Yield each chunk with async sleep to allow event loop control
            for chunk in chunks:
                yield chunk
                await asyncio.sleep(0)  # Yield control to allow cancellation checks

        except Exception as e:
            logger.error(f"Async audio generation failed: {e}")
            raise RuntimeError(f"Audio generation failed: {e}") from e


# Singleton instance
tts_service = TTSService()
