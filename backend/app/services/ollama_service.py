import os
from typing import Any, AsyncGenerator, Dict, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

# get the API key from the environment variables
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("OPENAI_API_KEY is not set")

# get the LLM URL from the environment variables
# sometimes we will use the local LLM URL, sometimes we will use the OpenRouter URL
LLM_URL = os.getenv("LLM_URL")
if not LLM_URL:
    raise ValueError("LLM_URL is not set")

# get the LLM model from the environment variables
LLM_MODEL = os.getenv("LLM_MODEL")
if not LLM_MODEL:
    raise ValueError("LLM_MODEL is not set")


class OllamaService:
    def __init__(self, base_url: str = LLM_URL, model: str = LLM_MODEL):
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=API_KEY,  # Ollama doesn't require a real API key
        )
        self.model = model
        # Session storage for reasoning traces, keyed by filename
        self._reasoning_sessions: Dict[str, list] = {}

    async def analyze_page(
        self, text: str, filename: str, page_num: int, context: str = ""
    ) -> str:
        """
        Analyze a PDF page using AI
        """
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
