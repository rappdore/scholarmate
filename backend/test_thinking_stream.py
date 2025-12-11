#!/usr/bin/env python3
"""
Test script for thinking stream implementation.
Tests the new structured streaming format with thinking/response separation.
"""

import asyncio
import json

import httpx


async def test_thinking_stream():
    """Test the /chat endpoint with structured thinking data"""

    url = "http://localhost:8000/ai/chat"

    # Test request - asking a question that might trigger thinking
    payload = {
        "message": "Explain what this document is about in simple terms.",
        "filename": "Why Machines Learn_ The Elegant Math Behind Modern AI -- Anil Ananthaswamy.pdf",
        "page_num": 1,
        "chat_history": [],
        "is_new_chat": True,
    }

    print("=" * 80)
    print("TESTING THINKING STREAM IMPLEMENTATION")
    print("=" * 80)
    print(f"\nSending request to: {url}")
    print(f"Question: {payload['message']}")
    print(f"Document: {payload['filename']}")
    print(f"Page: {payload['page_num']}\n")
    print("-" * 80)

    thinking_content = ""
    response_content = ""
    has_thinking = False
    thinking_complete = False

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, json=payload) as response:
            print("\nStreaming response:\n")

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue

                data_str = line[6:]  # Remove "data: " prefix
                try:
                    data = json.loads(data_str)

                    # Handle request_id
                    if "request_id" in data:
                        print(f"[REQUEST ID] {data['request_id']}\n")
                        continue

                    # Handle done
                    if data.get("done"):
                        print("\n[STREAM COMPLETE]")
                        break

                    # Handle structured data
                    if "type" in data:
                        chunk_type = data["type"]
                        content = data.get("content")
                        metadata = data.get("metadata", {})

                        if chunk_type == "metadata":
                            if metadata.get("thinking_started"):
                                print("\n[THINKING STARTED] 🧠\n")
                                has_thinking = True
                            if metadata.get("thinking_complete"):
                                print("\n[THINKING COMPLETE] ✓\n")
                                thinking_complete = True

                        elif chunk_type == "thinking":
                            if content:
                                thinking_content += content
                                print(
                                    f"\033[93m{content}\033[0m", end="", flush=True
                                )  # Yellow

                        elif chunk_type == "response":
                            if content:
                                response_content += content
                                print(
                                    f"\033[92m{content}\033[0m", end="", flush=True
                                )  # Green

                    # Handle old format (backward compatibility)
                    elif "content" in data:
                        response_content += data["content"]
                        print(data["content"], end="", flush=True)

                except json.JSONDecodeError as e:
                    print(f"\n[JSON ERROR] {e}: {data_str}")
                except Exception as e:
                    print(f"\n[ERROR] {e}")

    # Summary
    print("\n")
    print("=" * 80)
    print("STREAM SUMMARY")
    print("=" * 80)
    print(f"Has thinking: {has_thinking}")
    print(f"Thinking complete: {thinking_complete}")
    print(f"Thinking length: {len(thinking_content)} chars")
    print(f"Response length: {len(response_content)} chars")

    if has_thinking:
        print("\n[✓] SUCCESS: Thinking/response separation working!")
        print("\nThinking content preview:")
        print("-" * 80)
        print(
            thinking_content[:200] + "..."
            if len(thinking_content) > 200
            else thinking_content
        )
    else:
        print(
            "\n[i] INFO: No thinking content detected (model may not support <think> tags)"
        )

    print("\nResponse content preview:")
    print("-" * 80)
    print(
        response_content[:200] + "..."
        if len(response_content) > 200
        else response_content
    )
    print("\n" + "=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(test_thinking_stream())
    except KeyboardInterrupt:
        print("\n\n[CANCELLED] Test interrupted by user")
    except Exception as e:
        print(f"\n\n[ERROR] Test failed: {e}")
        import traceback

        traceback.print_exc()
