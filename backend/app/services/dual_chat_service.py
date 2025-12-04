"""
Dual Chat Service Module

This module provides a service for managing dual LLM chat sessions,
allowing two LLMs to respond to the same prompts simultaneously with
independent conversation histories.
"""

import asyncio
import json
import logging
import uuid
from typing import AsyncGenerator, Dict, List, Optional

from openai import AsyncOpenAI

from .llm_config_service import LLMConfigService
from .pdf_service import PDFService

# Configure logger
logger = logging.getLogger(__name__)


class DualChatSession:
    """Manages a dual chat session with two LLMs"""

    def __init__(self, request_id: str, primary_llm_id: int, secondary_llm_id: int):
        self.request_id = request_id
        self.primary_llm_id = primary_llm_id
        self.secondary_llm_id = secondary_llm_id
        self.llm1_task: Optional[asyncio.Task] = None
        self.llm2_task: Optional[asyncio.Task] = None
        self.cancelled = False

    async def cancel(self):
        """Cancel both LLM streams"""
        self.cancelled = True
        if self.llm1_task and not self.llm1_task.done():
            self.llm1_task.cancel()
        if self.llm2_task and not self.llm2_task.done():
            self.llm2_task.cancel()


class DualChatService:
    """Service for managing dual LLM chat sessions"""

    def __init__(self, db_path: str = "data/reading_progress.db"):
        self.db_path = db_path
        self.active_sessions: Dict[str, DualChatSession] = {}
        self.llm_config_service = LLMConfigService(db_path)
        self.pdf_service = PDFService()

    async def stream_dual_chat_response(
        self,
        message: str,
        filename: str,
        page_num: int,
        llm1_history: List[Dict],
        llm2_history: List[Dict],
        primary_llm_id: int,
        secondary_llm_id: int,
        is_new_chat: bool,
    ) -> AsyncGenerator[str, None]:
        """
        Stream responses from both LLMs concurrently.
        Yields SSE events with responses from both LLMs.
        """
        request_id = str(uuid.uuid4())
        session = DualChatSession(request_id, primary_llm_id, secondary_llm_id)
        self.active_sessions[request_id] = session

        try:
            # Send request_id first
            yield f"data: {json.dumps({'request_id': request_id})}\n\n"

            # Get document context
            context = await self._get_document_context(filename, page_num, is_new_chat)

            # Get LLM configurations with full API keys
            llm1_config = await self._get_llm_config(primary_llm_id)
            llm2_config = await self._get_llm_config(secondary_llm_id)

            if not llm1_config:
                yield f"data: {json.dumps({'llm1': {'error': f'LLM configuration {primary_llm_id} not found', 'done': True}})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
                return

            if not llm2_config:
                yield f"data: {json.dumps({'llm2': {'error': f'LLM configuration {secondary_llm_id} not found', 'done': True}})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
                return

            # Create queues for each LLM's responses
            llm1_queue = asyncio.Queue()
            llm2_queue = asyncio.Queue()

            # Start both LLM tasks concurrently
            session.llm1_task = asyncio.create_task(
                self._stream_from_llm(
                    llm1_config,
                    message,
                    context,
                    llm1_history,
                    llm1_queue,
                    filename,
                    page_num,
                )
            )
            session.llm2_task = asyncio.create_task(
                self._stream_from_llm(
                    llm2_config,
                    message,
                    context,
                    llm2_history,
                    llm2_queue,
                    filename,
                    page_num,
                )
            )

            # Stream responses from both queues
            async for event in self._merge_streams(llm1_queue, llm2_queue, session):
                yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            logger.error(f"Error in dual chat stream: {e}")
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
        finally:
            # Cleanup session
            if request_id in self.active_sessions:
                del self.active_sessions[request_id]

    async def _stream_from_llm(
        self,
        llm_config: Dict,
        message: str,
        context: str,
        history: List[Dict],
        queue: asyncio.Queue,
        filename: str,
        page_num: int,
    ):
        """Stream from a single LLM and put chunks in the queue"""
        try:
            # Build system prompt with context
            system_prompt = self._build_system_prompt(context, filename, page_num)

            # Prepare messages
            messages = [
                {"role": "system", "content": system_prompt},
                *history,
                {"role": "user", "content": message},
            ]

            # Stream from LLM
            async for chunk in self._call_llm_stream(llm_config, messages):
                await queue.put({"content": chunk, "done": False})

            # Signal completion
            await queue.put({"done": True})

        except asyncio.CancelledError:
            logger.info(f"LLM stream cancelled for {llm_config.get('name', 'unknown')}")
            await queue.put({"cancelled": True})
        except Exception as e:
            logger.error(
                f"Error streaming from LLM {llm_config.get('name', 'unknown')}: {e}"
            )
            await queue.put({"error": str(e), "done": True})

    async def _merge_streams(
        self,
        llm1_queue: asyncio.Queue,
        llm2_queue: asyncio.Queue,
        session: DualChatSession,
    ) -> AsyncGenerator[Dict, None]:
        """
        Merge two LLM streams into a single event stream.
        Yields events with llm1 and/or llm2 data.

        Uses tagged tasks to track which queue each piece of data came from,
        preventing stream crossing.
        """
        llm1_done = False
        llm2_done = False

        while not (llm1_done and llm2_done):
            if session.cancelled:
                yield {"cancelled": True}
                break

            # Create tagged tasks so we know which queue data came from
            tasks = {}
            if not llm1_done:
                tasks["llm1"] = asyncio.create_task(llm1_queue.get())
            if not llm2_done:
                tasks["llm2"] = asyncio.create_task(llm2_queue.get())

            if not tasks:
                break

            # Wait for at least one task to complete
            done, pending = await asyncio.wait(
                tasks.values(), return_when=asyncio.FIRST_COMPLETED
            )

            # Process completed tasks and match them to their source
            for completed_task in done:
                # Find which queue this task belongs to
                source = None
                for queue_name, task in tasks.items():
                    if task == completed_task:
                        source = queue_name
                        break

                if source:
                    try:
                        data = await completed_task

                        # Check if this stream is done
                        if data.get("done") or data.get("cancelled"):
                            if source == "llm1":
                                llm1_done = True
                            else:
                                llm2_done = True

                        # Yield data with correct source label
                        yield {source: data}

                    except Exception as e:
                        logger.error(f"Error processing {source} stream data: {e}")
                        if source == "llm1":
                            llm1_done = True
                        else:
                            llm2_done = True

            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Final done signal
        yield {"done": True}

    async def _call_llm_stream(
        self, llm_config: Dict, messages: List[Dict]
    ) -> AsyncGenerator[str, None]:
        """Call LLM API and stream response chunks"""
        try:
            # Create OpenAI-compatible client
            client = AsyncOpenAI(
                base_url=llm_config["base_url"], api_key=llm_config["api_key"]
            )

            # Make streaming request
            stream = await client.chat.completions.create(
                model=llm_config["model_name"], messages=messages, stream=True
            )

            # Stream chunks
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Error calling LLM API: {e}")
            raise

    async def stop_session(self, request_id: str):
        """Stop a dual chat session"""
        session = self.active_sessions.get(request_id)
        if session:
            await session.cancel()
            logger.info(f"Cancelled dual chat session: {request_id}")
        else:
            logger.warning(f"Session not found: {request_id}")

    def _build_system_prompt(self, context: str, filename: str, page_num: int) -> str:
        """Build system prompt with document context"""
        return f"""You are an intelligent study assistant helping a user understand a PDF document.

Current context:
- Document: {filename}
- Current page: {page_num}
- Page content: {context[:2000]}{"..." if len(context) > 2000 else ""}

You should:
1. Answer questions directly related to the PDF content
2. Provide explanations and clarifications
3. Help connect concepts within the document
4. Suggest related questions or areas to explore
5. Reference specific parts of the content when relevant

Keep responses conversational but informative. When explaining a concept, emphasize intuition. Rigor is important, but not at the expense of clarity. Why something makes intuitive sense is just as important as the technical details. If explaining math, use LaTeX to format equations."""

    async def _get_document_context(
        self, filename: str, page_num: int, is_new_chat: bool
    ) -> str:
        """Extract document context for the chat"""
        try:
            # Get current page text
            current_text = self.pdf_service.extract_page_text(filename, page_num)

            if is_new_chat:
                # For new chats, include surrounding context
                context_pages = []

                # Previous page
                if page_num > 1:
                    try:
                        prev_text = self.pdf_service.extract_page_text(
                            filename, page_num - 1
                        )
                        context_pages.append(
                            f"[Previous page {page_num - 1}]\n{prev_text[:500]}..."
                        )
                    except Exception:
                        pass

                # Current page
                context_pages.append(f"[Current page {page_num}]\n{current_text}")

                # Next page
                try:
                    pdf_info = self.pdf_service.get_pdf_info(filename)
                    if page_num < pdf_info["page_count"]:
                        next_text = self.pdf_service.extract_page_text(
                            filename, page_num + 1
                        )
                        context_pages.append(
                            f"[Next page {page_num + 1}]\n{next_text[:500]}..."
                        )
                except Exception:
                    pass

                return "\n\n".join(context_pages)
            else:
                # For ongoing chats, just return current page
                return f"[Page {page_num}]\n{current_text}"

        except Exception as e:
            logger.error(f"Error extracting context: {e}")
            return f"[Error extracting context from page {page_num}]"

    async def _get_llm_config(self, config_id: int) -> Optional[Dict]:
        """Get LLM configuration by ID with full API key"""
        try:
            # Get configuration from database
            config = self.llm_config_service.get_configuration_by_id(config_id)
            if not config:
                return None

            # We need the full API key, not the masked version
            # Query directly with mask_key=False
            with self.llm_config_service.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, name, description, base_url, api_key, model_name,
                           is_active, created_at, updated_at
                    FROM llm_configurations
                    WHERE id = ?
                """,
                    (config_id,),
                )
                row = cursor.fetchone()
                if row:
                    return self.llm_config_service._row_to_dict(row, mask_key=False)
                return None

        except Exception as e:
            logger.error(f"Error fetching LLM config {config_id}: {e}")
            return None


# Singleton instance
dual_chat_service = DualChatService()
