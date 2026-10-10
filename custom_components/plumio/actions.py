"""Run a Plumio action and turn its failures into errors a person can read."""

from __future__ import annotations

from collections.abc import Awaitable

from homeassistant.exceptions import HomeAssistantError

from .api import PlumioAuthError, PlumioConnectionError, PlumioRequestError
from .const import DOMAIN

# Server error codes that have their own translated message.
_KNOWN_CODES = {
    "premium_required",
    "actions_disabled",
    "rate_limited",
    "not_found",
    "zone_limit",
    "validation_error",
}


async def run_action[T](call: Awaitable[T]) -> T:
    """Await `call`; raise a translated HomeAssistantError if Plumio says no."""
    try:
        return await call
    except PlumioRequestError as err:
        key = err.code if err.code in _KNOWN_CODES else "request_failed"
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=key,
            translation_placeholders={"detail": err.detail or err.code},
        ) from err
    except PlumioAuthError as err:
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="link_revoked") from err
    except PlumioConnectionError as err:
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="cannot_connect") from err
