import asyncio
import base64
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.tts_service import DEFAULT_SPEED, tts_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["tts"])


async def generate_tts(
    websocket: WebSocket,
    text: str,
    voice: str,
    speed: float,
) -> None:
    """Generate TTS audio and stream it via WebSocket.

    This runs as an asyncio task that can be cancelled.
    Raises asyncio.CancelledError when stop is requested.
    """
    segments = tts_service.segment_text_with_offsets(text)
    logger.info(f"TTS: Starting generation for {len(segments)} sentences")

    for idx, segment in enumerate(segments):
        try:
            # Notify sentence start with character offsets for highlighting
            await websocket.send_json(
                {
                    "type": "sentence_start",
                    "index": idx,
                    "text": segment.text,
                    "startOffset": segment.start_offset,
                    "endOffset": segment.end_offset,
                }
            )

            # Generate and stream audio
            chunk_count = 0
            async for audio_chunk in tts_service.generate_audio_async(
                segment.text, voice=voice, speed=speed
            ):
                # Encode as base64 for JSON transport
                audio_b64 = base64.b64encode(audio_chunk).decode("utf-8")
                await websocket.send_json(
                    {"type": "audio", "index": idx, "data": audio_b64}
                )
                chunk_count += 1

            logger.debug(
                f"TTS: Sentence {idx} complete, sent {chunk_count} audio chunks"
            )

            # Notify sentence end
            await websocket.send_json({"type": "sentence_end", "index": idx})

        except asyncio.CancelledError:
            # Re-raise cancellation to allow proper cleanup
            logger.info(f"TTS: Generation cancelled at sentence {idx}")
            raise
        except Exception as e:
            # Log the error but try to continue with the next sentence
            logger.error(f"TTS: Error generating audio for sentence {idx}: {e}")
            # Notify client of the error for this sentence
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"Failed to generate audio for sentence {idx}: {e!s}",
                }
            )
            # Skip to next sentence rather than failing entirely
            continue

    logger.info("TTS: Generation complete")
    await websocket.send_json({"type": "done"})


@router.websocket("/tts")
async def tts_websocket(websocket: WebSocket):
    await websocket.accept()

    current_task: asyncio.Task | None = None

    try:
        while True:
            # Wait for message
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "start":
                # Cancel any existing TTS task
                if current_task and not current_task.done():
                    current_task.cancel()
                    try:
                        await current_task
                    except asyncio.CancelledError:
                        pass

                text = message.get("text", "")
                voice = message.get("voice", "af_heart")
                speed = message.get("speed", DEFAULT_SPEED)

                if not text.strip():
                    await websocket.send_json(
                        {"type": "error", "message": "No text provided"}
                    )
                    continue

                # Start TTS generation as a cancellable task
                current_task = asyncio.create_task(
                    generate_tts(websocket, text, voice, speed)
                )

                # Use asyncio.wait to listen for either task completion or new messages
                while not current_task.done():
                    # Create a task for receiving the next message
                    receive_task = asyncio.create_task(websocket.receive_text())

                    done, _pending = await asyncio.wait(
                        [current_task, receive_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    if receive_task in done:
                        # Got a new message while generating
                        try:
                            new_data = receive_task.result()
                            new_message = json.loads(new_data)

                            if new_message.get("type") == "stop":
                                # Cancel the TTS task
                                current_task.cancel()
                                try:
                                    await current_task
                                except asyncio.CancelledError:
                                    pass
                                await websocket.send_json({"type": "stopped"})
                                current_task = None
                                break

                            elif new_message.get("type") == "start":
                                # New start request - cancel current and restart
                                current_task.cancel()
                                try:
                                    await current_task
                                except asyncio.CancelledError:
                                    pass

                                text = new_message.get("text", "")
                                voice = new_message.get("voice", "af_heart")
                                speed = new_message.get("speed", DEFAULT_SPEED)

                                if text.strip():
                                    current_task = asyncio.create_task(
                                        generate_tts(websocket, text, voice, speed)
                                    )
                                else:
                                    await websocket.send_json(
                                        {"type": "error", "message": "No text provided"}
                                    )
                                    current_task = None
                                    break
                        except json.JSONDecodeError:
                            await websocket.send_json(
                                {"type": "error", "message": "Invalid JSON message"}
                            )
                        except Exception as e:
                            await websocket.send_json(
                                {
                                    "type": "error",
                                    "message": f"Message processing error: {e!s}",
                                }
                            )
                    else:
                        # TTS task completed or errored - cancel receive task
                        receive_task.cancel()
                        try:
                            await receive_task
                        except asyncio.CancelledError:
                            pass

                        # Check if TTS task raised an exception
                        if current_task.done() and current_task.exception():
                            exc = current_task.exception()
                            await websocket.send_json(
                                {
                                    "type": "error",
                                    "message": f"Audio generation failed: {exc!s}",
                                }
                            )
                        current_task = None

            elif message.get("type") == "stop":
                # Stop requested but no task running
                if current_task and not current_task.done():
                    current_task.cancel()
                    try:
                        await current_task
                    except asyncio.CancelledError:
                        pass
                    current_task = None
                await websocket.send_json({"type": "stopped"})

    except WebSocketDisconnect:
        # Clean up on disconnect
        if current_task and not current_task.done():
            current_task.cancel()
            try:
                await current_task
            except asyncio.CancelledError:
                pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
        finally:
            if current_task and not current_task.done():
                current_task.cancel()
                try:
                    await current_task
                except asyncio.CancelledError:
                    pass
