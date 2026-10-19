"""Token estimation for quota accounting.

The MCP server never runs a model, so the exact prompt/completion token counts
charged by the LLM provider are not observable here.  What the server does know
is the payload it exchanges with the client: the tool arguments it receives and
the article text, search results and JSON documents it sends back.  That volume
is what this module measures, and it is the quantity the weekly quota in
:mod:`src.middleware.rate_limit` is charged against.

The estimate uses the industry heuristic of four characters per token, which
holds closely enough for Portuguese and English prose.  A real tokenizer such as
``tiktoken`` was deliberately not adopted: it downloads its vocabulary at first
use, adding a network dependency and cold-start latency to every container, and
the extra precision would be spent on a number that is an approximation of the
provider's billing either way.
"""

_CHARS_PER_TOKEN = 4


def estimate_tokens(payload: bytes | str) -> int:
    """Estimate how many tokens *payload* represents.

    Args:
        payload: Raw request or response content. Bytes are measured as UTF-8
            text, replacing undecodable sequences rather than raising.

    Returns:
        The estimated token count, never negative. Empty payloads return 0.
    """
    if not payload:
        return 0

    text = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else payload
    return len(text) // _CHARS_PER_TOKEN
