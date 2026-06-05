"""
Shared async HTTP helper with tenacity retry logic.

Every external API call goes through `get_json`. It retries up to 3 times
with a 5-second wait on any HTTP or timeout error, then re-raises so the
caller can decide whether to skip or abort.
"""

from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(5),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
async def get_json(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    """
    Async GET that retries 3 times on HTTP / timeout errors.

    Args:
        client: Shared AsyncClient (connection-pooled across calls).
        url:    Full endpoint URL.
        params: Query-string parameters dict.

    Returns:
        Parsed JSON response as a dict.

    Raises:
        httpx.HTTPStatusError: On 4xx / 5xx after all retries exhausted.
        httpx.TimeoutException: On timeout after all retries exhausted.
    """
    response = await client.get(url, params=params, timeout=10.0)
    response.raise_for_status()
    return response.json()
