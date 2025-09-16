from typing import Any, AsyncGenerator, Dict, Optional

from openai import AsyncOpenAI


class OllamaService:
    def __init__(
        self, base_url: str = "http://localhost:1234/v1", model: str = "qwen3:30b"
    ):
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key="ollama",  # Ollama doesn't require a real API key
        )
        self.model = model

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
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat responses about the PDF content
        """
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

Keep responses conversational but informative."""

        messages = [{"role": "system", "content": system_prompt}]

        # Add chat history if provided
        if chat_history:
            messages.extend(chat_history[-10:])  # Keep last 10 messages for context

        # Add current message
        messages.append({"role": "user", "content": message})

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                # max_tokens=800,
                stream=True,
            )

            async for chunk in stream:
                # Check for cancellation if request_id is provided
                if request_id:
                    # Lazy import to avoid circular imports
                    from .request_tracking_service import request_tracking_service

                    if request_tracking_service.is_cancelled(request_id):
                        break

                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

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
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat responses about the EPUB content
        """
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

        # Add chat history if provided
        if chat_history:
            messages.extend(chat_history[-10:])  # Keep last 10 messages for context

        # Add current message
        messages.append({"role": "user", "content": message})

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                stream=True,
            )

            async for chunk in stream:
                # Check for cancellation if request_id is provided
                if request_id:
                    # Lazy import to avoid circular imports
                    from .request_tracking_service import request_tracking_service

                    if request_tracking_service.is_cancelled(request_id):
                        break

                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

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
