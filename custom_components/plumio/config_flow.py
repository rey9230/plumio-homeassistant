"""Config flow: link a Nest by showing a code that its admin approves in the Plumio app.

Home Assistant never sees a password. It shows a short code (and a QR of the same
link); the Nest's admin scans it with their phone and confirms with their fingerprint
or PIN; then this flow collects a token of its own, scoped to that one Nest.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    QrCodeSelector,
    QrCodeSelectorConfig,
    QrErrorCorrectionLevel,
)

from .api import PlumioClient, PlumioError
from .const import (
    CONF_API_URL,
    CONF_HOME_FROM_PLACES,
    CONF_LINK_ID,
    CONF_MAX_GPS_ACCURACY,
    CONF_NEST_ID,
    CONF_TOKEN,
    DEFAULT_API_URL,
    DEFAULT_HOME_FROM_PLACES,
    DEFAULT_MAX_GPS_ACCURACY,
    DOMAIN,
)
from .coordinator import PlumioConfigEntry

SECTION_ADVANCED = "advanced"


class PlumioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Link one Nest per config entry."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_url = DEFAULT_API_URL
        self._pairing: dict[str, Any] | None = None
        self._reauth_entry: PlumioConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: PlumioConfigEntry) -> PlumioOptionsFlow:
        return PlumioOptionsFlow()

    def _client(self) -> PlumioClient:
        return PlumioClient(async_get_clientsession(self.hass), self._api_url)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Start. Nothing to fill in; a collapsed section allows a different server (testing)."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(SECTION_ADVANCED): section(
                            vol.Schema({vol.Optional(CONF_API_URL, default=DEFAULT_API_URL): str}),
                            {"collapsed": True},
                        )
                    }
                ),
            )
        advanced = user_input.get(SECTION_ADVANCED) or {}
        self._api_url = (advanced.get(CONF_API_URL) or DEFAULT_API_URL).rstrip("/")
        return await self.async_step_link()

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The link was revoked from the app (or its admin left the Nest): link again."""
        self._reauth_entry = self._get_reauth_entry()
        self._api_url = entry_data.get(CONF_API_URL, DEFAULT_API_URL)
        return await self.async_step_link()

    async def async_step_link(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the code, and on submit check whether the admin approved it."""
        errors: dict[str, str] = {}
        if user_input is not None and self._pairing is not None:
            try:
                result = await self._client().pair_poll(self._pairing["deviceCode"])
            except PlumioError:
                errors["base"] = "cannot_connect"
            else:
                status = result.get("status")
                if status == "APPROVED":
                    return await self._finish(result)
                if status == "PENDING":
                    errors["base"] = "not_approved_yet"
                else:
                    # Denied or expired: that code is dead, start over with a fresh one.
                    self._pairing = None
                    errors["base"] = "denied" if status == "DENIED" else "expired"

        if self._pairing is None:
            try:
                self._pairing = await self._client().pair_start(self.hass.config.location_name)
            except PlumioError:
                return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="link",
            data_schema=vol.Schema(
                {
                    vol.Optional("qr"): QrCodeSelector(
                        QrCodeSelectorConfig(
                            data=self._pairing["verificationUriComplete"],
                            scale=6,
                            error_correction_level=QrErrorCorrectionLevel.QUARTILE,
                        )
                    )
                }
            ),
            description_placeholders={
                "code": self._pairing["userCode"],
                "url": self._pairing["verificationUri"],
            },
            errors=errors,
        )

    async def _finish(self, result: dict[str, Any]) -> ConfigFlowResult:
        data = {
            CONF_API_URL: self._api_url,
            CONF_TOKEN: result["token"],
            CONF_LINK_ID: result["linkId"],
            CONF_NEST_ID: result["nestId"],
        }
        await self.async_set_unique_id(result["nestId"])
        if self._reauth_entry is not None:
            # Approving a different Nest would silently swap every entity's meaning.
            self._abort_if_unique_id_mismatch(reason="wrong_nest")
            return self.async_update_reload_and_abort(self._reauth_entry, data=data)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=result.get("nestName") or "Plumio", data=data)


class PlumioOptionsFlow(OptionsFlow):
    """Behaviour that is a matter of taste, not of linking."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOME_FROM_PLACES,
                        default=options.get(CONF_HOME_FROM_PLACES, DEFAULT_HOME_FROM_PLACES),
                    ): BooleanSelector(),
                    vol.Required(
                        CONF_MAX_GPS_ACCURACY,
                        default=options.get(CONF_MAX_GPS_ACCURACY, DEFAULT_MAX_GPS_ACCURACY),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=5000, step=10, unit_of_measurement="m", mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
        )
