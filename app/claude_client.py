# async client that actually talks to claude
import anthropic
from anthropic import AsyncAnthropic

from app.config import ANTHROPIC_API_KEY, ANTHROPIC_MAX_TOKENS, ANTHROPIC_MODEL

_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY, timeout=15.0, max_retries=1) if ANTHROPIC_API_KEY else AsyncAnthropic(timeout=15.0, max_retries=1)


# gets raised if claude cant be reached or sends back an error
class ClaudeError(Exception):
    pass


async def get_completion(
    system_prompt: str,
    messages: list[dict],
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    # sends the system prompt + convo to claude and just returns the text back
    kwargs: dict = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": max_tokens or ANTHROPIC_MAX_TOKENS,
        "system": system_prompt,
        "messages": messages,
    }
    if temperature is not None:
        # anthropic only takes 0.0-1.0 but cowrie lets the temperature config
        # go up to 2.0, so gotta clamp it or claude throws a 400 on us
        kwargs["temperature"] = min(max(temperature, 0.0), 1.0)

    try:
        kwargs.pop("temperature", None)
        response = await _client.messages.create(**kwargs)
    except anthropic.APIError as exc:
        raise ClaudeError(f"Claude API error: {exc}") from exc

    text = "".join(block.text for block in response.content if block.type == "text")
    # Claude sometimes continues the transcript and invents the next command; cut it off
    for marker in ("Human:", "Assistant:"):
        text = text.split(marker)[0]
    text = text.replace("[no output]", "")
    return text
