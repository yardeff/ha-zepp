"""Config flow for Zepp (Amazfit) integration."""
from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    ZeppAuthError,
    ZeppConnectionError,
    async_discover_zepp_devices,
    async_exchange_access_token,
    async_login_web,
)
from .const import (
    CONF_APPTOKEN,
    CONF_CNAME,
    CONF_COUNTRY_CODE,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_REGION_HOST,
    CONF_USERID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONF_TOKEN_OR_URL = "token_or_url"

COUNTRY_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(value="AUTO", label="Auto-detect / Worldwide (Recommended)"),
            selector.SelectOptionDict(value="US", label="United States / North America (US)"),
            selector.SelectOptionDict(value="RU", label="Russia / CIS (RU)"),
            selector.SelectOptionDict(value="DE", label="Europe / Germany (DE)"),
            selector.SelectOptionDict(value="CN", label="China (CN)"),
            selector.SelectOptionDict(value="SG", label="Asia / Singapore (SG)"),
            selector.SelectOptionDict(value="IN", label="India (IN)"),
        ],
        mode=selector.SelectSelectorMode.DROPDOWN,
        custom_value=True,
    )
)


CONF_AUTH_METHOD = "auth_method"
AUTH_METHOD_PASSWORD = "password"
AUTH_METHOD_TOKEN = "token"

AUTH_METHOD_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(
                value=AUTH_METHOD_PASSWORD,
                label="Direct Zepp Account (Email & Password)",
            ),
            selector.SelectOptionDict(
                value=AUTH_METHOD_TOKEN,
                label="Browser Cookies (For Google, Apple, Mi, or Social logins)",
            ),
        ],
        mode=selector.SelectSelectorMode.LIST,
    )
)


@config_entries.HANDLERS.register(DOMAIN)
class ZeppConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Zepp."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Present choice of login method."""
        if user_input is not None:
            method = user_input.get(CONF_AUTH_METHOD, AUTH_METHOD_PASSWORD)
            if method == AUTH_METHOD_TOKEN:
                return await self.async_step_token()
            return await self.async_step_password()

        schema = vol.Schema(
            {
                vol.Required(CONF_AUTH_METHOD, default=AUTH_METHOD_PASSWORD): AUTH_METHOD_SELECTOR,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )

    async def async_step_password(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle direct email + password login."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            country_code = user_input.get(CONF_COUNTRY_CODE, "AUTO").strip().upper()

            session = async_get_clientsession(self.hass)
            try:
                auth_data = await async_login_web(
                    session, email, password, country_code=country_code
                )
            except ZeppAuthError:
                errors["base"] = "invalid_auth"
            except ZeppConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during Zepp login")
                errors["base"] = "unknown"
            else:
                return await self._async_create_zepp_entry(session, auth_data, email=email)

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_COUNTRY_CODE, default="AUTO"): COUNTRY_SELECTOR,
            }
        )

        return self.async_show_form(
            step_id="password",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle token or redirect URL login."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_input = user_input[CONF_TOKEN_OR_URL].strip()
            country_code = user_input.get(CONF_COUNTRY_CODE, "AUTO").strip().upper()

            session = async_get_clientsession(self.hass)
            try:
                auth_data = await async_exchange_access_token(
                    session, raw_input, country_code=country_code
                )
            except ZeppAuthError:
                errors["base"] = "invalid_auth"
            except ZeppConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during Zepp token login")
                errors["base"] = "unknown"
            else:
                return await self._async_create_zepp_entry(session, auth_data, email="Token Account")

        schema = vol.Schema(
            {
                vol.Required(CONF_TOKEN_OR_URL): str,
                vol.Optional(CONF_COUNTRY_CODE, default="AUTO"): COUNTRY_SELECTOR,
            }
        )

        return self.async_show_form(
            step_id="token",
            data_schema=schema,
            errors=errors,
        )

    async def _async_create_zepp_entry(
        self,
        session: Any,
        auth_data: dict[str, Any],
        email: str,
    ) -> FlowResult:
        """Complete authentication and create config entry."""
        userid = auth_data["userid"]
        apptoken = auth_data["apptoken"]
        cname = auth_data.get("cname")

        await self.async_set_unique_id(str(userid))
        self._abort_if_unique_id_configured()

        region_host, devices = await async_discover_zepp_devices(
            session, apptoken, userid, cname
        )

        if devices:
            first_dev = devices[0]
            title = f"{first_dev['device_name']} ({first_dev['device_mac']})"
        else:
            title = f"Zepp ({email})"

        return self.async_create_entry(
            title=title,
            data={
                CONF_EMAIL: email,
                CONF_APPTOKEN: apptoken,
                CONF_USERID: userid,
                CONF_CNAME: cname,
                CONF_REGION_HOST: region_host,
                "devices": devices,
            },
        )
