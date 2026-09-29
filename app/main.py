# middleware that sits between cowrie and claude
# forwards commands to claude with a hardcoded system prompt, caches
# responses so we dont keep re-calling claude for the same convo
# no session state tracking yet, thats the next thing to build
import time
import uuid
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import cache
from app.claude_client import ClaudeError, get_completion
from app.config import ANTHROPIC_MODEL
from app.prompts import SHELL_SYSTEM_PROMPT

app = FastAPI(title="DeceptiveShell LLM Middleware")


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: list[ChatMessage]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "backend_model": ANTHROPIC_MODEL}


def _build_claude_messages(messages: list[ChatMessage]) -> list[dict]:
    # strips out cowrie's own system message, keeps the rest of the convo
    # for claude to use
    #
    # cowrie's exec mode (ssh host 'command') only sends a system message
    # with no user turn at all, so if theres nothing else left we just use
    # that text as the user turn instead - otherwise claude throws an error
    # on an empty message list
    cowrie_system = next((m.content for m in messages if m.role == "system"), None)
    conversation = [
        {"role": m.role, "content": m.content} for m in messages if m.role != "system"
    ]
    if not conversation and cowrie_system:
        conversation = [{"role": "user", "content": cowrie_system}]
    return conversation


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest) -> dict:
    conversation = _build_claude_messages(request.messages)

    content = cache.get(conversation)
    if content is None:
        try:
            content = await get_completion(
                SHELL_SYSTEM_PROMPT,
                conversation,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
        except ClaudeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        cache.set(conversation, content)

    # gotta reshape this back into the format cowrie expects
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": ANTHROPIC_MODEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }
