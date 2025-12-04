import logging
from typing import Any, AsyncGenerator, Dict, Optional

from openai import AsyncOpenAI

# Configure logger
logger = logging.getLogger(__name__)

# Default fallback configuration for LM Studio
DEFAULT_BASE_URL = "http://localhost:1234/v1"
DEFAULT_API_KEY = "not-needed"
DEFAULT_MODEL = ""


class OllamaService:
    def __init__(self, db_path: str = "data/reading_progress.db"):
        self.db_path = db_path
        self.client = None
        self.model = None
        self.base_url = None
        self.api_key = None
        # Session storage for reasoning traces, keyed by filename
        self._reasoning_sessions: Dict[str, list] = {}

        # Load initial configuration
        self._load_active_configuration()

    def _load_active_configuration(self):
        """
        Load the active LLM configuration from database.
        Falls back to LM Studio defaults if no active configuration exists.
        """
        try:
            # Import here to avoid circular dependency
            from app.services.llm_config_service import LLMConfigService

            llm_config_service = LLMConfigService(self.db_path)
            config = llm_config_service.get_active_configuration()

            if config:
                # Load from database
                self.base_url = config["base_url"]
                self.api_key = config["api_key"]
                self.model = config["model_name"]
                logger.info(
                    f"✅ Loaded LLM configuration from database: {config['name']}"
                )
                logger.info(f"   - Base URL: {self.base_url}")
                logger.info(f"   - Model: {self.model}")
            else:
                # No active configuration, use LM Studio defaults
                self.base_url = DEFAULT_BASE_URL
                self.api_key = DEFAULT_API_KEY
                self.model = DEFAULT_MODEL
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

            self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)

    def reload_configuration(self):
        """
        Reload configuration from database (called when active config changes).
        This allows switching LLMs without restarting the service.
        """
        logger.info("🔄 Reloading LLM configuration...")
        self._load_active_configuration()
        logger.info("✅ Configuration reloaded successfully!")
        logger.info(f"   - Base URL: {self.base_url}")
        logger.info(f"   - Model: {self.model}")

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

            return response.choices[0].message.content.strip()

        except Exception as e:
            raise Exception(f"Failed to analyze page: {str(e)}")

    async def analyze_epub_section(
        self, text: str, filename: str, nav_id: str, context: str = ""
    ) -> str:
        """
        Analyze an EPUB section using AI
        """
        logger.info(
            f"[LLM] analyze_epub_section - Using model: {self.model}, base_url: {self.base_url}"
        )

        system_prompt = """

        You are an intelligent study assistant. Your role is to help users understand EPUB documents by providing clear, insightful analysis of the content.

When analyzing a section, you should:
1. Summarize the key points and main ideas
2. Explain any complex concepts in simpler terms
3. Highlight important information or insights
4. Provide context or background knowledge when helpful
5. Point out connections to other concepts or fields
6. Suggest questions the reader might want to explore further

Keep your analysis concise but thorough, and focus on enhancing understanding rather than just repeating the content."""

        user_prompt = f"""Please analyze the section with ID '{nav_id}' of the document "{filename}".

{f"Additional context: {context}" if context else ""}

Section content:
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

            return response.choices[0].message.content.strip()

        except Exception as e:
            raise Exception(f"Failed to analyze EPUB section: {str(e)}")

    async def chat_stream(
        self,
        message: str,
        filename: str,
        page_num: int,
        pdf_text: str,
        chat_history: list = None,
        request_id: Optional[str] = None,
        is_new_chat: bool = False,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat responses about the PDF content with reasoning trace preservation
        """
        logger.info(
            f"[LLM] chat_stream - Using model: {self.model}, base_url: {self.base_url}"
        )

        # Clear reasoning session if this is a new chat
        if is_new_chat:
            if filename in self._reasoning_sessions:
                print(f"[DEBUG] Clearing reasoning session for {filename}")
                del self._reasoning_sessions[filename]
            else:
                print(f"[DEBUG] Starting new chat for {filename} (no existing session)")

        # Initialize session storage if it doesn't exist
        if filename not in self._reasoning_sessions:
            self._reasoning_sessions[filename] = []

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

        messages = [{"role": "system", "content": system_prompt}]

        # Add chat history if provided, reconstructing with reasoning_details
        if chat_history:
            stored_reasoning = self._reasoning_sessions[filename]
            assistant_msg_count = 0

            for msg in chat_history[-10:]:  # Keep last 10 messages for context
                if msg.get("role") == "assistant":
                    # Try to match this assistant message with stored reasoning
                    if assistant_msg_count < len(stored_reasoning):
                        reasoning = stored_reasoning[assistant_msg_count]
                        if reasoning:
                            messages.append(
                                {
                                    "role": "assistant",
                                    "content": msg.get("content", ""),
                                    "reasoning_details": reasoning,
                                }
                            )
                            print(
                                f"[DEBUG] Added assistant message {assistant_msg_count} with reasoning_details: {reasoning}"
                            )
                        else:
                            messages.append(msg)
                        assistant_msg_count += 1
                    else:
                        messages.append(msg)
                else:
                    messages.append(msg)

        # Add current message
        messages.append({"role": "user", "content": message})

        try:
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
                    # Lazy import to avoid circular imports
                    from .request_tracking_service import request_tracking_service

                    if request_tracking_service.is_cancelled(request_id):
                        break

                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

                # Capture reasoning_details from the response
                if hasattr(chunk.choices[0], "message") and hasattr(
                    chunk.choices[0].message, "reasoning_details"
                ):
                    reasoning_details = chunk.choices[0].message.reasoning_details
                elif hasattr(chunk.choices[0], "delta") and hasattr(
                    chunk.choices[0].delta, "reasoning_details"
                ):
                    reasoning_details = chunk.choices[0].delta.reasoning_details

            # Store the reasoning_details for this response
            if reasoning_details:
                self._reasoning_sessions[filename].append(reasoning_details)
                print(
                    f"[DEBUG] Stored reasoning_details for {filename}: {reasoning_details}"
                )
            else:
                # Store None to keep indexing aligned
                self._reasoning_sessions[filename].append(None)
                print(f"[DEBUG] No reasoning_details in response for {filename}")

        except Exception as e:
            yield f"Error: {str(e)}"

    async def chat_epub_stream(
        self,
        message: str,
        filename: str,
        nav_id: str,
        epub_text: str,
        chat_history: list = None,
        request_id: Optional[str] = None,
        is_new_chat: bool = False,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat responses about the EPUB content with reasoning trace preservation
        """
        logger.info(
            f"[LLM] chat_epub_stream - Using model: {self.model}, base_url: {self.base_url}"
        )

        # Clear reasoning session if this is a new chat
        if is_new_chat:
            if filename in self._reasoning_sessions:
                print(f"[DEBUG] Clearing reasoning session for {filename}")
                del self._reasoning_sessions[filename]
            else:
                print(f"[DEBUG] Starting new chat for {filename} (no existing session)")

        # Initialize session storage if it doesn't exist
        if filename not in self._reasoning_sessions:
            self._reasoning_sessions[filename] = []

        system_prompt = f"""
        You are an intelligent study assistant helping a user understand an EPUB document.

Current context:
- Document: {filename}
- Current section: {nav_id}
- Section content: {epub_text[:2000]}{"..." if len(epub_text) > 2000 else ""}

You should:
1. Answer questions directly related to the EPUB content
2. Provide explanations and clarifications
3. Help connect concepts within the document
4. Suggest related questions or areas to explore
5. Reference specific parts of the content when relevant

Keep responses conversational but informative."""

        messages = [{"role": "system", "content": system_prompt}]

        # Add chat history if provided, reconstructing with reasoning_details
        if chat_history:
            stored_reasoning = self._reasoning_sessions[filename]
            assistant_msg_count = 0

            for msg in chat_history[-10:]:  # Keep last 10 messages for context
                if msg.get("role") == "assistant":
                    # Try to match this assistant message with stored reasoning
                    if assistant_msg_count < len(stored_reasoning):
                        reasoning = stored_reasoning[assistant_msg_count]
                        if reasoning:
                            messages.append(
                                {
                                    "role": "assistant",
                                    "content": msg.get("content", ""),
                                    "reasoning_details": reasoning,
                                }
                            )
                            print(
                                f"[DEBUG] Added assistant message {assistant_msg_count} with reasoning_details: {reasoning}"
                            )
                        else:
                            messages.append(msg)
                        assistant_msg_count += 1
                    else:
                        messages.append(msg)
                else:
                    messages.append(msg)

        # Add current message
        messages.append({"role": "user", "content": message})

        try:
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
                    # Lazy import to avoid circular imports
                    from .request_tracking_service import request_tracking_service

                    if request_tracking_service.is_cancelled(request_id):
                        break

                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

                # Capture reasoning_details from the response
                if hasattr(chunk.choices[0], "message") and hasattr(
                    chunk.choices[0].message, "reasoning_details"
                ):
                    reasoning_details = chunk.choices[0].message.reasoning_details
                elif hasattr(chunk.choices[0], "delta") and hasattr(
                    chunk.choices[0].delta, "reasoning_details"
                ):
                    reasoning_details = chunk.choices[0].delta.reasoning_details

            # Store the reasoning_details for this response
            if reasoning_details:
                self._reasoning_sessions[filename].append(reasoning_details)
                print(
                    f"[DEBUG] Stored reasoning_details for {filename}: {reasoning_details}"
                )
            else:
                # Store None to keep indexing aligned
                self._reasoning_sessions[filename].append(None)
                print(f"[DEBUG] No reasoning_details in response for {filename}")

        except Exception as e:
            yield f"Error: {str(e)}"

    async def test_connection(self) -> Dict[str, Any]:
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
    ) -> AsyncGenerator[str, None]:
        """
        Analyze a PDF page using AI with streaming response
        """
        logger.info(
            f"[LLM] analyze_page_stream - Using model: {self.model}, base_url: {self.base_url}"
        )

        system_prompt = """

        You are an intelligent study assistant. Your role is to help users understand PDF documents by providing clear, insightful analysis of the content.

When analyzing a page, you should:
1. Summarize the key points and main ideas
2. Explain any complex concepts in simpler terms
3. Highlight important information or insights
4. Provide context or background knowledge when helpful
5. Point out connections to other concepts or fields
6. Suggest questions the reader might want to explore further

Keep your analysis concise but thorough, and focus on enhancing understanding rather than just repeating the content."""

        user_prompt = f"""Please analyze page {page_num} of the document "{filename}".

{f"Additional context: {context}" if context else ""}

Page content:
{text}

Provide a helpful analysis that will aid in understanding this content."""

        try:
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
                    yield chunk.choices[0].delta.content

        except Exception as e:
            yield f"Error: {str(e)}"

    async def analyze_epub_section_stream(
        self, text: str, filename: str, nav_id: str, context: str = ""
    ) -> AsyncGenerator[str, None]:
        """
        Analyze an EPUB section using AI with a streaming response.
        """
        logger.info(
            f"[LLM] analyze_epub_section_stream - Using model: {self.model}, base_url: {self.base_url}"
        )

        system_prompt = """

        You are an intelligent study assistant. Your role is to help users understand EPUB documents by providing clear, insightful analysis of the content.

When analyzing a section, you should:
1. Summarize the key points and main ideas
2. Explain any complex concepts in simpler terms
3. Highlight important information or insights
4. Provide context or background knowledge when helpful
5. Point out connections to other concepts or fields
6. Suggest questions the reader might want to explore further

Keep your analysis concise but thorough, and focus on enhancing understanding rather than just repeating the content."""

        user_prompt = f"""Please analyze the section with ID '{nav_id}' of the document "{filename}".

{f"Additional context: {context}" if context else ""}

Section content:
{text}

Provide a helpful analysis that will aid in understanding this content."""

        try:
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
                    yield chunk.choices[0].delta.content

        except Exception as e:
            yield f"Error: {str(e)}"


# Global instance
# This creates a singleton instance of the OllamaService that can be imported
# and used throughout the application. This ensures all parts of the app use
# the same LLM configuration.
ollama_service = OllamaService()
