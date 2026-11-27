"""Utilitaires HTTP partagés (retries avec backoff pour les APIs image/TTS)."""

import asyncio
import logging
import random
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 529}


def _retry_after(response: httpx.Response) -> Optional[float]:
    value = response.headers.get("Retry-After")
    try:
        return min(float(value), 60.0) if value else None
    except ValueError:
        return None


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_attempts: int = 4,
    base_delay: float = 2.0,
    **kwargs,
) -> httpx.Response:
    """Envoie une requête; réessaie sur 429/5xx et erreurs réseau (backoff exponentiel + jitter).

    Les erreurs 4xx non transitoires (clé invalide, prompt refusé...) sont levées immédiatement.
    Retourne la réponse (statut 2xx) ou lève `httpx.HTTPStatusError` / `httpx.TransportError`.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            response = await client.request(method, url, **kwargs)
            if response.status_code in RETRYABLE_STATUS and attempt < max_attempts:
                delay = _retry_after(response) or base_delay * 2 ** (attempt - 1)
                logger.warning("⏳ HTTP %s sur %s, nouvel essai %d/%d dans %.1fs",
                               response.status_code, httpx.URL(url).host, attempt + 1, max_attempts, delay)
                await asyncio.sleep(delay + random.uniform(0, 0.5))
                continue
            response.raise_for_status()
            return response
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            if attempt >= max_attempts:
                raise
            delay = base_delay * 2 ** (attempt - 1)
            logger.warning("⏳ Erreur réseau (%s), nouvel essai %d/%d dans %.1fs",
                           type(exc).__name__, attempt + 1, max_attempts, delay)
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")
