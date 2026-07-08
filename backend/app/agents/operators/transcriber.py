"""
TranscriberOperator — Audio extraction and Whisper API transcription.

Downloads video/audio from a URL, extracts audio as MP3 via pydub,
and sends it to OpenAI Whisper for speech-to-text transcription.

Sprint 2 / CI-CORE-01 / T01-2
"""

import hashlib
import logging
import tempfile
from pathlib import Path

import requests
from openai import AsyncOpenAI
from pydub import AudioSegment

from app.agents.base import BaseAgent
from app.config import settings

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


class TranscriberOperator(BaseAgent):
    """Operator that transcribes business call recordings via OpenAI Whisper.

    Provides two interfaces:
    - ``transcribe()`` — standalone async method for direct use (Celery tasks,
      route handlers).  Does not invoke the AI loop.
    - ``transcribe_audio`` tool — registered with the BaseAgent tool registry
      so the Anthropic model can call it within a conversation.
    """

    def __init__(self) -> None:
        super().__init__(
            agent_id="op-transcriber",
            name="Transcriber Operator",
            model=settings.anthropic_model_default,
            max_tokens=2048,
        )

        self.system_prompt = (
            "You are the Transcriber Operator (CI-OPS-TRX), a shared utility in the Central Intelligence platform. "
            "Your sole function is to produce accurate, complete transcripts from business call recordings.\n\n"
            "## Operation\n\n"
            "When given a call URL and call type, use the transcribe_audio tool to extract the transcript. "
            "Return the result immediately. Do not summarize, analyze, or modify the transcript content.\n\n"
            "## Call Types\n\n"
            "- sales_call: Discovery or closing calls with leads. Accuracy on objections and pricing language is critical.\n"
            "- coaching: Delivery sessions with active members. Accuracy on goals, action items, and breakthroughs is critical.\n"
            "- accountability: Check-in calls. Accuracy on progress updates and reported blockers is critical.\n\n"
            "## Error Handling\n\n"
            "If transcription fails, report the failure clearly with: the URL attempted, the error type, "
            "and whether a retry is likely to succeed (e.g. file size exceeded vs. network timeout). "
            "Do not attempt to reconstruct or guess transcript content.\n\n"
            "## Output Contract\n\n"
            "Return the raw JSON object from the transcribe_audio tool without modification. "
            "Do not wrap it in prose or add commentary. The caller expects: "
            '{"transcript": "...", "duration_seconds": N, "language": "en"}'
        )

        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

        # Register the transcribe_audio tool for AI-loop usage.
        self.register_tool(
            name="transcribe_audio",
            description=(
                "Download a video/audio file from a URL, extract the audio, "
                "and transcribe it using OpenAI Whisper. Returns a JSON object "
                "with transcript text, duration in seconds, and detected language."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "video_url": {
                        "type": "string",
                        "description": "Public URL of the video or audio file to transcribe.",
                    },
                    "call_type": {
                        "type": "string",
                        "enum": ["sales_call", "coaching", "accountability"],
                        "description": "Type of business call.",
                    },
                },
                "required": ["video_url", "call_type"],
            },
            handler=self._tool_transcribe_audio,
        )

        logger.info("TranscriberOperator initialised")

    # -------------------------------------------------------------------
    # Standalone interface (primary — used by routes / Celery)
    # -------------------------------------------------------------------

    async def transcribe(self, video_url: str, call_type: str) -> dict:
        """Download, extract audio, and transcribe without the AI loop.

        Parameters
        ----------
        video_url:
            Public URL pointing to a video or audio file.
        call_type:
            One of ``sales_call``, ``coaching``, ``accountability``.

        Returns
        -------
        dict
            ``{"transcript": "...", "duration_seconds": N, "language": "en"}``

        Raises
        ------
        ValueError
            If the file exceeds 25 MB.
        ConnectionError
            If the URL is unreachable.
        openai.OpenAIError
            If the Whisper API call fails.
        """
        logger.info(
            "Transcribe requested — url=%s call_type=%s",
            video_url,
            call_type,
        )

        audio_path = await self._download_and_extract(video_url)

        try:
            result = await self._whisper_transcribe(audio_path)
        finally:
            # Clean up the temporary audio file.
            try:
                audio_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Failed to clean up temp file %s", audio_path)

        logger.info(
            "Transcription complete — duration=%ss language=%s",
            result["duration_seconds"],
            result["language"],
        )
        return result

    # -------------------------------------------------------------------
    # Tool handler (wraps transcribe for the AI loop)
    # -------------------------------------------------------------------

    async def _tool_transcribe_audio(
        self, video_url: str, call_type: str
    ) -> dict:
        """Tool handler invoked by BaseAgent when Claude calls transcribe_audio."""
        return await self.transcribe(video_url, call_type)

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------

    @staticmethod
    def compute_url_hash(video_url: str) -> str:
        """Return the SHA-256 hex digest of a video URL for deduplication."""
        return hashlib.sha256(video_url.encode("utf-8")).hexdigest()

    async def _download_and_extract(self, video_url: str) -> Path:
        """Download file from URL, validate size, extract audio as MP3.

        Returns the ``Path`` to a temporary MP3 file.
        """
        # --- HEAD check for file size ---
        try:
            head = requests.head(video_url, allow_redirects=True, timeout=15)
            head.raise_for_status()
        except requests.RequestException as exc:
            logger.error("HEAD request failed for %s: %s", video_url, exc)
            raise ConnectionError(
                f"Unable to reach URL: {video_url}"
            ) from exc

        content_length = head.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File exceeds 25MB limit "
                f"(Content-Length: {int(content_length)} bytes)"
            )

        # --- Stream-download the file ---
        try:
            resp = requests.get(video_url, stream=True, timeout=120)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("GET request failed for %s: %s", video_url, exc)
            raise ConnectionError(
                f"Unable to download file: {video_url}"
            ) from exc

        # Write to a temp file, enforcing 25 MB cap during download.
        tmp_input = tempfile.NamedTemporaryFile(
            delete=False, suffix=".download"
        )
        downloaded = 0
        try:
            for chunk in resp.iter_content(chunk_size=8192):
                downloaded += len(chunk)
                if downloaded > MAX_FILE_SIZE_BYTES:
                    tmp_input.close()
                    Path(tmp_input.name).unlink(missing_ok=True)
                    raise ValueError(
                        f"File exceeds 25MB limit (downloaded {downloaded} bytes)"
                    )
                tmp_input.write(chunk)
        finally:
            tmp_input.close()

        input_path = Path(tmp_input.name)

        # --- Convert to MP3 via pydub ---
        try:
            audio = AudioSegment.from_file(str(input_path))
        except Exception as exc:
            input_path.unlink(missing_ok=True)
            logger.error("pydub failed to decode audio: %s", exc)
            raise ValueError(
                f"Could not decode audio from the downloaded file: {exc}"
            ) from exc

        mp3_path = input_path.with_suffix(".mp3")
        audio.export(str(mp3_path), format="mp3")

        # Remove the original download.
        input_path.unlink(missing_ok=True)

        logger.debug(
            "Audio extracted — mp3_path=%s size=%d bytes",
            mp3_path,
            mp3_path.stat().st_size,
        )
        return mp3_path

    async def _whisper_transcribe(self, audio_path: Path) -> dict:
        """Transcribe via local faster-whisper. Returns ``{transcript, duration_seconds, language}``."""
        import anyio
        from app.services.local_whisper import transcribe_file
        return await anyio.to_thread.run_sync(transcribe_file, audio_path)
