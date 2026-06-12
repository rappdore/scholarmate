import logging
from collections.abc import AsyncGenerator
from typing import cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.models.llm_types import LLMConfiguration
from app.models.stream_types import StreamChunk
from app.services.epub.epub_chat_context_service import EPUBChatContext
from app.services.request_tracking_service import RequestTrackingService
from app.services.stream_parser import ThinkingStreamParser

# Configure logger
logger = logging.getLogger(__name__)

# Default fallback configuration for LM Studio
DEFAULT_BASE_URL = "http://localhost:1234/v1"
DEFAULT_API_KEY = "not-needed"
DEFAULT_MODEL = ""

# Number of chat history messages sent to the LLM for context
CHAT_HISTORY_LIMIT = 10

# Maximum reasoning traces kept per file to bound memory usage
MAX_REASONING_PER_FILE = 50


class OllamaService:
    def __init__(self, db_path: str, request_tracking: RequestTrackingService) -> None:
        self.db_path = db_path
        # Shared tracker injected by the registry so cancellation requests
        # made through the routers are visible to in-flight streams here.
        self._request_tracking = request_tracking
        # Always assigned by _load_active_configuration() below (both its
        # success and fallback paths), so these are never None after __init__.
        self.client: AsyncOpenAI
        self.model: str
        self.base_url: str
        self.api_key: str
        self.always_starts_with_thinking: bool = False
        # Session storage for reasoning traces, keyed by filename
        self._reasoning_sessions: dict[str, list] = {}

        # Load initial configuration
        self._load_active_configuration()

    def _load_active_configuration(self) -> None:
        """
        Load the active LLM configuration from database.
        Falls back to LM Studio defaults if no active configuration exists.
        """
        try:
            # Import here to avoid circular dependency
            from app.services.llm_config_service import LLMConfigService

            llm_config_service = LLMConfigService(self.db_path)
            config: LLMConfiguration | None = (
                llm_config_service.get_active_configuration()
            )

            if config:
                # Load from database with type safety
                self.base_url = config.base_url
                self.api_key = config.api_key
                self.model = config.model_name
                self.always_starts_with_thinking = config.always_starts_with_thinking
                logger.info(f"✅ Loaded LLM configuration from database: {config.name}")
                logger.info(f"   - Base URL: {self.base_url}")
                logger.info(f"   - Model: {self.model}")
                logger.info(
                    f"   - Always starts with thinking: {self.always_starts_with_thinking}"
                )
            else:
                # No active configuration, use LM Studio defaults
                self.base_url = DEFAULT_BASE_URL
                self.api_key = DEFAULT_API_KEY
                self.model = DEFAULT_MODEL
                self.always_starts_with_thinking = False
                logger.warning(
                    f"⚠️  No active LLM configuration found in database. "
                    f"Using default fallback: {DEFAULT_BASE_URL}"
                )

            # Initialize client
            self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)

        except Exception as e:
            logger.error(f"Error loading LLM configuration: {e}")
            logger.warning(f"Falling back to default configuration: {DEFAULT_BASE_URL}")

            # Fall back to defaults
            self.base_url = DEFAULT_BASE_URL
            self.api_key = DEFAULT_API_KEY
            self.model = DEFAULT_MODEL
            self.always_starts_with_thinking = False

            self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)

    def _clear_reasoning_session(self, filename: str) -> None:
        """Drop any stored reasoning traces for a file (called on new chats)."""
        if filename in self._reasoning_sessions:
            logger.debug(f"Clearing reasoning session for {filename}")
            del self._reasoning_sessions[filename]
        else:
            logger.debug(f"Starting new chat for {filename} (no existing session)")

    def _store_reasoning(self, filename: str, reasoning_details) -> None:
        """Store a reasoning trace (or None placeholder) for a file, capped in size."""
        session = self._reasoning_sessions.setdefault(filename, [])
        session.append(reasoning_details)
        if len(session) > MAX_REASONING_PER_FILE:
            del session[: len(session) - MAX_REASONING_PER_FILE]

    @staticmethod
    def _reconstruct_history_with_reasoning(
        chat_history: list,
        stored_reasoning: list,
        history_limit: int = CHAT_HISTORY_LIMIT,
    ) -> list:
        """
        Build the message list for the LLM from chat history, re-attaching stored
        reasoning traces to assistant messages.

        Reasoning traces are stored append-only per response, so the most recent
        trace belongs to the most recent assistant message. Because the history
        is truncated to the last `history_limit` messages, alignment must be done
        from the END: the last min(len) stored reasonings are zipped with the
        last assistant messages in the truncated slice.
        """
        history = chat_history[-history_limit:]
        assistant_indices = [
            i for i, msg in enumerate(history) if msg.get("role") == "assistant"
        ]

        pair_count = min(len(assistant_indices), len(stored_reasoning))
        reasoning_by_index: dict[int, object] = {}
        if pair_count:
            for idx, reasoning in zip(
                assistant_indices[-pair_count:], stored_reasoning[-pair_count:]
            ):
                reasoning_by_index[idx] = reasoning

        messages: list = []
        for i, msg in enumerate(history):
            reasoning = reasoning_by_index.get(i)
            if reasoning:
                messages.append(
                    {
                        "role": "assistant",
                        "content": msg.get("content", ""),
                        "reasoning_details": reasoning,
                    }
                )
                logger.debug(
                    f"Attached reasoning_details to assistant message at index {i}"
                )
            else:
                messages.append(msg)

        return messages

    def reload_configuration(self) -> None:
        """
        Reload configuration from database (called when active config changes).
        This allows switching LLMs without restarting the service.
        """
        logger.info("🔄 Reloading LLM configuration...")
        self._load_active_configuration()
        logger.info("✅ Configuration reloaded successfully!")
        logger.info(f"   - Base URL: {self.base_url}")
        logger.info(f"   - Model: {self.model}")
        logger.info(
            f"   - Always starts with thinking: {self.always_starts_with_thinking}"
        )

    async def analyze_page(
        self, text: str, filename: str, page_num: int, context: str = ""
    ) -> str:
        """
        Analyze a PDF page using AI
        """
        logger.info(
            f"[LLM] analyze_page - Using model: {self.model}, base_url: {self.base_url}"
        )

        system_prompt = """

        You are an intelligent study assistant. Your role is to help users understand documents by providing clear, insightful analysis of the content.

When analyzing a page, you should:
1. Summarize the key points and main ideas
2. Explain any complex concepts in simpler terms
3. Highlight important information or insights
4. Provide context or background knowledge when helpful
5. Point out connections to other concepts or fields
6. Suggest questions the reader might want to explore further
lms
Keep your analysis concise but thorough, and focus on enhancing understanding rather than just repeating the content. Keep the tone playful and engaging. A tone too terse and lacking in levity makes the user feel like they're talking to a robot."""

        user_prompt = f"""Please analyze page {page_num} of the document "{filename}".

{f"Additional context: {context}" if context else ""}

Page content:
{text}

Provide a helpful analysis that will aid in understanding this content."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
            )

            # content is only None for tool-call responses, which we never request
            return cast(str, response.choices[0].message.content).strip()

        except Exception as e:
            raise Exception(f"Failed to analyze page: {str(e)}")

    async def analyze_epub_section(
        self,
        epub_context: EPUBChatContext,
        filename: str,
        nav_id: str,
        context: str = "",
    ) -> str:
        """
        Analyze an EPUB section using AI.

        Args:
            epub_context: Structured context from EPUBChatContextService
            filename: EPUB filename
            nav_id: Navigation section ID
            context: Additional user-provided context
        """
        logger.info(
            f"[LLM] analyze_epub_section - Using model: {self.model}, base_url: {self.base_url}"
        )

        # Use the formatted context from the context service
        formatted_context = epub_context.format_for_llm()

        system_prompt = """You are an intelligent study assistant. Your role is to help users understand EPUB documents by providing clear, insightful analysis of the content.

When analyzing a section, you should:
1. Summarize the key points and main ideas
2. Explain any complex concepts in simpler terms
3. Highlight important information or insights
4. Provide context or background knowledge when helpful
5. Point out connections to other concepts or fields
6. Suggest questions the reader might want to explore further

Keep your analysis concise but thorough, and focus on enhancing understanding rather than just repeating the content."""

        user_prompt = f"""Please analyze the current section of the document "{filename}".

Current section: {epub_context.current_section_title or nav_id}

{f"Additional context: {context}" if context else ""}

{formatted_context}

Provide a helpful analysis that will aid in understanding this content."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
            )

            # content is only None for tool-call responses, which we never request
            return cast(str, response.choices[0].message.content).strip()

        except Exception as e:
            raise Exception(f"Failed to analyze EPUB section: {str(e)}")

    async def chat_stream(
        self,
        message: str,
        filename: str,
        page_num: int,
        pdf_text: str,
        chat_history: list | None = None,
        request_id: str | None = None,
        is_new_chat: bool = False,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream chat responses about the PDF content with structured thinking/response separation.

        Returns:
            AsyncGenerator yielding StreamChunk TypedDicts with separated thinking/response content
        """
        logger.info(
            f"[LLM] chat_stream - Using model: {self.model}, base_url: {self.base_url}"
        )

        # Clear reasoning session if this is a new chat
        if is_new_chat:
            self._clear_reasoning_session(filename)

        system_prompt = f"""
        You are an intelligent study assistant helping a user understand a PDF document.

Current context:
- Document: {filename}
- Current page: {page_num}
- Page content: {pdf_text[:2000]}{"..." if len(pdf_text) > 2000 else ""}

You should:
1. Answer questions directly related to the PDF content
2. Provide explanations and clarifications
3. Help connect concepts within the document
4. Suggest related questions or areas to explore
5. Reference specific parts of the content when relevant

Keep responses conversational but informative. When explaining a concept, emphasize intuition. Rigor is important, but not at the expense of clarity. Why something makes intuitive sense is just as important as the technical details. If explaining math, use LaTeX to format equations."""

        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt}
        ]

        # Add chat history if provided, reconstructing with reasoning_details
        if chat_history:
            messages.extend(
                self._reconstruct_history_with_reasoning(
                    chat_history, self._reasoning_sessions.get(filename, [])
                )
            )

        # Add current message
        messages.append({"role": "user", "content": message})

        try:
            # NEW: Create parser for this stream
            parser = ThinkingStreamParser(
                always_starts_with_thinking=self.always_starts_with_thinking
            )
            logger.debug(
                f"[LLM] Initialized ThinkingStreamParser (always_starts_with_thinking={self.always_starts_with_thinking})"
            )

            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                # max_tokens=800,
                stream=True,
                extra_body={"reasoning": {"enabled": True}},
            )

            reasoning_details = None
            async for chunk in stream:
                # Check for cancellation if request_id is provided
                if request_id:
                    if self._request_tracking.is_cancelled(request_id):
                        logger.info(
                            f"[LLM] Request {request_id} cancelled, stopping stream"
                        )
                        break

                if chunk.choices[0].delta.content:
                    raw_content = chunk.choices[0].delta.content

                    # NEW: Process through thinking parser
                    async for structured_chunk in parser.process_chunk(raw_content):
                        yield structured_chunk

                # Capture reasoning_details from the response
                if hasattr(chunk.choices[0], "message") and hasattr(
                    chunk.choices[0].message, "reasoning_details"
                ):
                    reasoning_details = chunk.choices[0].message.reasoning_details
                elif hasattr(chunk.choices[0], "delta") and hasattr(
                    chunk.choices[0].delta, "reasoning_details"
                ):
                    reasoning_details = chunk.choices[0].delta.reasoning_details

            # NEW: Finalize parser to flush buffer
            async for final_chunk in parser.finalize():
                yield final_chunk

            # Store the reasoning_details (or None to keep alignment) for this response
            self._store_reasoning(filename, reasoning_details)
            logger.debug(
                f"[LLM] Stored reasoning_details for {filename}"
                if reasoning_details
                else f"[LLM] No reasoning_details in response for {filename}"
            )

            logger.info(f"[LLM] Stream complete for {filename}")

        except Exception as e:
            logger.error(f"Chat stream error: {str(e)}", exc_info=True)
            yield StreamChunk(
                type="response",
                content=f"Error: {str(e)}",
                metadata={"thinking_started": False, "thinking_complete": False},
            )

    async def chat_epub_stream(
        self,
        message: str,
        filename: str,
        nav_id: str,
        epub_context: EPUBChatContext,
        chat_history: list | None = None,
        request_id: str | None = None,
        is_new_chat: bool = False,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream chat responses about the EPUB content with structured thinking/response separation.

        Args:
            message: The user's message
            filename: EPUB filename
            nav_id: Current navigation section ID
            epub_context: Structured context from EPUBChatContextService
            chat_history: Previous chat messages
            request_id: Optional request ID for cancellation tracking
            is_new_chat: Whether this is the first message in a conversation

        Returns:
            AsyncGenerator yielding StreamChunk TypedDicts with separated thinking/response content
        """
        logger.info(
            f"[LLM] chat_epub_stream - Using model: {self.model}, base_url: {self.base_url}"
        )

        # Clear reasoning session if this is a new chat
        if is_new_chat:
            self._clear_reasoning_session(filename)

        # Use the structured context from EPUBChatContextService
        formatted_context = epub_context.format_for_llm()

        system_prompt = f"""You are an intelligent study assistant helping a user understand an EPUB document.

Current context:
- Document: {filename}
- Current section: {epub_context.current_section_title or nav_id}

{formatted_context}

You should:
1. Answer questions directly related to the EPUB content
2. Provide explanations and clarifications
3. Help connect concepts within the document
4. Suggest related questions or areas to explore
5. Reference specific parts of the content when relevant

Keep responses conversational but informative."""

        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt}
        ]

        # Add chat history if provided, reconstructing with reasoning_details
        if chat_history:
            messages.extend(
                self._reconstruct_history_with_reasoning(
                    chat_history, self._reasoning_sessions.get(filename, [])
                )
            )

        # Add current message
        messages.append({"role": "user", "content": message})

        try:
            # NEW: Create parser for this stream
            parser = ThinkingStreamParser(
                always_starts_with_thinking=self.always_starts_with_thinking
            )
            logger.debug(
                f"[LLM] Initialized ThinkingStreamParser for EPUB (always_starts_with_thinking={self.always_starts_with_thinking})"
            )

            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                stream=True,
                extra_body={"reasoning": {"enabled": True}},
            )

            reasoning_details = None
            async for chunk in stream:
                # Check for cancellation if request_id is provided
                if request_id:
                    if self._request_tracking.is_cancelled(request_id):
                        logger.info(
                            f"[LLM] Request {request_id} cancelled, stopping EPUB stream"
                        )
                        break

                if chunk.choices[0].delta.content:
                    raw_content = chunk.choices[0].delta.content

                    # NEW: Process through thinking parser
                    async for structured_chunk in parser.process_chunk(raw_content):
                        yield structured_chunk

                # Capture reasoning_details from the response
                if hasattr(chunk.choices[0], "message") and hasattr(
                    chunk.choices[0].message, "reasoning_details"
                ):
                    reasoning_details = chunk.choices[0].message.reasoning_details
                elif hasattr(chunk.choices[0], "delta") and hasattr(
                    chunk.choices[0].delta, "reasoning_details"
                ):
                    reasoning_details = chunk.choices[0].delta.reasoning_details

            # NEW: Finalize parser to flush buffer
            async for final_chunk in parser.finalize():
                yield final_chunk

            # Store the reasoning_details (or None to keep alignment) for this response
            self._store_reasoning(filename, reasoning_details)
            logger.debug(
                f"[LLM] Stored reasoning_details for {filename}"
                if reasoning_details
                else f"[LLM] No reasoning_details in response for {filename}"
            )

            logger.info(f"[LLM] EPUB stream complete for {filename}")

        except Exception as e:
            logger.error(f"EPUB chat stream error: {str(e)}", exc_info=True)
            yield StreamChunk(
                type="response",
                content=f"Error: {str(e)}",
                metadata={"thinking_started": False, "thinking_complete": False},
            )

    async def test_connection(self) -> dict[str, object]:
        """
        Test connection to Ollama
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello, are you working?"}],
                # max_tokens=50
            )

            return {
                "status": "connected",
                "model": self.model,
                "response": response.choices[0].message.content,
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def analyze_page_stream(
        self, text: str, filename: str, page_num: int, context: str = ""
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Analyze a PDF page using AI with streaming response and structured thinking/response.

        Returns:
            AsyncGenerator yielding StreamChunk TypedDicts with separated thinking/response content
        """
        logger.info(
            f"[LLM] analyze_page_stream - Using model: {self.model}, base_url: {self.base_url}"
        )

        system_prompt = """

        You are an intelligent study assistant. Your role is to help users understand PDF documents by providing clear, insightful analysis of the content.

When analyzing a page, you should:
1. Summarize the key points and main ideas
2. Provide the summary as a few bullet points
3. Brevity is the key

focus on enhancing understanding rather than just repeating the content."""

        user_prompt = f"""Please analyze page {page_num} of the document "{filename}".

{f"Additional context: {context}" if context else ""}

Page content:
{text}

Provide a helpful analysis that will aid in understanding this content."""

        try:
            # Create parser for this stream
            parser = ThinkingStreamParser(
                always_starts_with_thinking=self.always_starts_with_thinking
            )
            logger.debug(
                f"[LLM] Initialized ThinkingStreamParser for analyze_page_stream "
                f"(always_starts_with_thinking={self.always_starts_with_thinking})"
            )

            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    raw_content = chunk.choices[0].delta.content

                    # Process through thinking parser
                    async for structured_chunk in parser.process_chunk(raw_content):
                        yield structured_chunk

            # Finalize parser to flush buffer
            async for final_chunk in parser.finalize():
                yield final_chunk

            logger.info(f"[LLM] analyze_page_stream complete for {filename}")

        except Exception as e:
            logger.error(f"analyze_page_stream error: {str(e)}", exc_info=True)
            yield StreamChunk(
                type="response",
                content=f"Error: {str(e)}",
                metadata={"thinking_started": False, "thinking_complete": False},
            )

    async def analyze_epub_section_stream(
        self,
        epub_context: EPUBChatContext,
        filename: str,
        nav_id: str,
        context: str = "",
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Analyze an EPUB section using AI with streaming response and structured thinking/response.

        Args:
            epub_context: Structured context from EPUBChatContextService
            filename: EPUB filename
            nav_id: Navigation section ID
            context: Additional user-provided context

        Returns:
            AsyncGenerator yielding StreamChunk TypedDicts with separated thinking/response content
        """
        logger.info(
            f"[LLM] analyze_epub_section_stream - Using model: {self.model}, base_url: {self.base_url}"
        )

        # Use the formatted context from the context service
        formatted_context = epub_context.format_for_llm()

        system_prompt = """You are an intelligent study assistant. Your role is to help users understand EPUB documents by providing clear, insightful analysis of the content.

When analyzing a section, you should:
1. Summarize the key points and main ideas
2. Explain any complex concepts in simpler terms
3. Highlight important information or insights
4. Provide context or background knowledge when helpful
5. Point out connections to other concepts or fields
6. Suggest questions the reader might want to explore further

Keep your analysis concise but thorough, and focus on enhancing understanding rather than just repeating the content."""

        user_prompt = f"""Please analyze the current section of the document "{filename}".

Current section: {epub_context.current_section_title or nav_id}

{f"Additional context: {context}" if context else ""}

{formatted_context}

Provide a helpful analysis that will aid in understanding this content."""

        try:
            # Create parser for this stream
            parser = ThinkingStreamParser(
                always_starts_with_thinking=self.always_starts_with_thinking
            )
            logger.debug(
                f"[LLM] Initialized ThinkingStreamParser for analyze_epub_section_stream "
                f"(always_starts_with_thinking={self.always_starts_with_thinking})"
            )

            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    raw_content = chunk.choices[0].delta.content

                    # Process through thinking parser
                    async for structured_chunk in parser.process_chunk(raw_content):
                        yield structured_chunk

            # Finalize parser to flush buffer
            async for final_chunk in parser.finalize():
                yield final_chunk

            logger.info(f"[LLM] analyze_epub_section_stream complete for {filename}")

        except Exception as e:
            logger.error(f"analyze_epub_section_stream error: {str(e)}", exc_info=True)
            yield StreamChunk(
                type="response",
                content=f"Error: {str(e)}",
                metadata={"thinking_started": False, "thinking_complete": False},
            )
