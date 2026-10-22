# middleware that sits between cowrie and claude
# forwards commands to claude with a hardcoded system prompt, caches
# responses so we dont keep re-calling claude for the same convo
# tracks a fake filesystem per session so cd/mkdir/touch stay consistent
import time
import uuid
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import cache, session_state
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


def _extract_system_text(messages: list[ChatMessage]) -> Optional[str]:
    return next((m.content for m in messages if m.role == "system"), None)


def _build_claude_messages(
    messages: list[ChatMessage], cowrie_system: Optional[str]
) -> list[dict]:
    # strips out cowrie's own system message, keeps the rest of the convo
    # for claude to use
    #
    # cowrie's exec mode (ssh host 'command') only sends a system message
    # with no user turn at all, so if theres nothing else left we just use
    # that text as the user turn instead - otherwise claude throws an error
    # on an empty message list
    #
    # cowrie also only logs an assistant turn when a command's output was
    # non-empty, so two silent commands in a row (cd then mkdir, say) show
    # up as two user turns back to back with nothing in between - claude's
    # api wants strict alternation, and without a fix it answers the wrong
    # command. fill those gaps with a "[no output]" placeholder instead.
    conversation: list[dict] = []
    for m in messages:
        if m.role == "system":
            continue
        text = m.content if (m.content and m.content.strip()) else ""
        if m.role == "user":
            if conversation and conversation[-1]["role"] == "user":
                conversation.append({"role": "assistant", "content": "[no output]"})
            conversation.append({"role": "user", "content": text})
        else:
            if conversation and conversation[-1]["role"] == "assistant":
                continue
            conversation.append({"role": "assistant", "content": text or "[no output]"})
    while conversation and conversation[0]["role"] == "assistant":
        conversation.pop(0)
    if not conversation and cowrie_system:
        conversation = [{"role": "user", "content": cowrie_system}]
    return conversation


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest) -> dict:
    cowrie_system = _extract_system_text(request.messages)
    conversation = _build_claude_messages(request.messages, cowrie_system)

    # figure out which session this is and whatever it was just typed, so we
    # can key the cache and the fake filesystem off something more useful
    # than just the raw conversation text
    session_key = session_state.get_session_key(cowrie_system)
    cwd_before = session_state.get_state(session_key).cwd
    command = (
        conversation[-1]["content"]
        if conversation and conversation[-1]["role"] == "user"
        else ""
    )

    content = cache.get(session_key, cwd_before, command)
    if content is None:
        # inject whats already "there" from earlier in this session before
        # asking claude to simulate the new command, so it cant just make
        # up a directory listing that contradicts what it said last time
        state_prompt = session_state.build_state_prompt(session_key)
        system_prompt = f"{SHELL_SYSTEM_PROMPT}\n\n{state_prompt}"

        try:
            content = await get_completion(
                system_prompt,
                conversation,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
        except ClaudeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        cache.set(session_key, cwd_before, command, content)

    # apply whatever this command did (cd/mkdir/touch) so the next command
    # in this session sees the updated state
    session_state.update_state(session_key, command)

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
