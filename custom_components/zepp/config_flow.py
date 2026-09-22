"""Config flow for Zepp (Amazfit) integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
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
    CONF_SCAN_INTERVAL,
    CONF_USERID,
    DEFAULT_SCAN_INTERVAL,
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
    """Handle a config flow for Zepp with progress screens and discovery."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow state."""
        self._auth_method: str = AUTH_METHOD_PASSWORD
        self._email: str | None = None
        self._password: str | None = None
        self._token_or_url: str | None = None
        self._country_code: str = "AUTO"
        self._is_reauth: bool = False
        self._discovery_task: asyncio.Task[None] | None = None
        self._auth_data: dict[str, Any] | None = None
        self._discovered_host: str | None = None
        self._discovered_devices: list[dict[str, Any]] | None = None
        self._error: str | None = None
        self._error_detail: str | None = None
        self._abort_reason: str | None = None

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
            self._auth_method = AUTH_METHOD_PASSWORD
            self._email = user_input[CONF_EMAIL].strip()
            self._password = user_input[CONF_PASSWORD]
            self._country_code = user_input.get(CONF_COUNTRY_CODE, "AUTO").strip().upper()
            self._is_reauth = False
            self._discovery_task = None
            self._error = None
            self._error_detail = None
            self._abort_reason = None
            return await self.async_step_discovery()

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL, default=self._email or ""): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_COUNTRY_CODE, default=self._country_code or "AUTO"): COUNTRY_SELECTOR,
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
            self._auth_method = AUTH_METHOD_TOKEN
            self._token_or_url = user_input[CONF_TOKEN_OR_URL].strip()
            self._country_code = user_input.get(CONF_COUNTRY_CODE, "AUTO").strip().upper()
            self._is_reauth = False
            self._discovery_task = None
            self._error = None
            self._error_detail = None
            self._abort_reason = None
            return await self.async_step_discovery()

        schema = vol.Schema(
            {
                vol.Required(CONF_TOKEN_OR_URL, default=self._token_or_url or ""): str,
                vol.Optional(CONF_COUNTRY_CODE, default=self._country_code or "AUTO"): COUNTRY_SELECTOR,
            }
        )

        return self.async_show_form(
            step_id="token",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "login_url": "https://user.zepp.com/universalLogin/index.html#/login?project_name=watchface&project_redirect_uri=https%3A%2F%2Fwatchface.zepp.com%2Fcreate&platform_app=com.huami.webapp&specify_lang=en"
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> FlowResult:
        """Handle re-authentication upon token expiry."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication confirmation dialog."""
        reauth_entry = self._get_reauth_entry()
        is_password = bool(reauth_entry.data.get(CONF_PASSWORD))

        if user_input is not None:
            self._is_reauth = True
            self._discovery_task = None
            self._error = None
            self._error_detail = None
            self._abort_reason = None
            self._country_code = user_input.get(CONF_COUNTRY_CODE, reauth_entry.data.get(CONF_COUNTRY_CODE, "AUTO")).strip().upper()
            if is_password:
                self._auth_method = AUTH_METHOD_PASSWORD
                self._email = user_input.get(CONF_EMAIL, reauth_entry.data.get(CONF_EMAIL, "")).strip()
                self._password = user_input[CONF_PASSWORD]
            else:
                self._auth_method = AUTH_METHOD_TOKEN
                self._token_or_url = user_input[CONF_TOKEN_OR_URL].strip()
            return await self.async_step_discovery()

        if is_password:
            schema = vol.Schema(
                {
                    vol.Required(CONF_EMAIL, default=self._email or reauth_entry.data.get(CONF_EMAIL, "")): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_COUNTRY_CODE, default=self._country_code or reauth_entry.data.get(CONF_COUNTRY_CODE, "AUTO")): COUNTRY_SELECTOR,
                }
            )
        else:
            schema = vol.Schema(
                {
                    vol.Required(CONF_TOKEN_OR_URL, default=self._token_or_url or ""): str,
                    vol.Optional(CONF_COUNTRY_CODE, default=self._country_code or reauth_entry.data.get(CONF_COUNTRY_CODE, "AUTO")): COUNTRY_SELECTOR,
                }
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            description_placeholders={"account": reauth_entry.title},
        )

    async def async_step_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Connect to Zepp cloud and discover devices while showing a progress screen."""
        if self._discovery_task is None:
            self._discovery_task = self.hass.async_create_task(
                self._async_connect_and_discover()
            )

        if not self._discovery_task.done():
            return self.async_show_progress(
                step_id="discovery",
                progress_action="connecting",
                progress_task=self._discovery_task,
            )

        return self.async_show_progress_done(next_step_id="discovery_done")

    async def _async_connect_and_discover(self) -> None:
        """Background worker for authentication and device discovery."""
        session = async_get_clientsession(self.hass)
        try:
            if self._auth_method == AUTH_METHOD_PASSWORD:
                self._auth_data = await async_login_web(
                    session, self._email or "", self._password or "", country_code=self._country_code
                )
            else:
                self._auth_data = await async_exchange_access_token(
                    session, self._token_or_url or "", country_code=self._country_code
                )

            userid = self._auth_data["userid"]
            apptoken = self._auth_data["apptoken"]
            cname = self._auth_data.get("cname")

            if not self._is_reauth:
                await self.async_set_unique_id(str(userid))
                self._abort_if_unique_id_configured()

            self._discovered_host, self._discovered_devices = await async_discover_zepp_devices(
                session, apptoken, userid, cname
            )
        except data_entry_flow.AbortFlow as exc:
            self._abort_reason = exc.reason
        except ZeppAuthError as exc:
            self._error = "invalid_auth"
            self._error_detail = str(exc)
        except ZeppConnectionError as exc:
            self._error = "cannot_connect"
            self._error_detail = str(exc)
        except Exception as exc:
            _LOGGER.exception("Unexpected exception during Zepp discovery")
            self._error = "unknown"
            self._error_detail = str(exc)

    async def async_step_discovery_done(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle completion of the discovery task."""
        if self._abort_reason:
            return self.async_abort(reason=self._abort_reason)

        if self._error:
            return await self.async_step_discovery_error()

        if self._is_reauth:
            reauth_entry = self._get_reauth_entry()
            new_data = {
                **reauth_entry.data,
                CONF_COUNTRY_CODE: self._country_code,
                CONF_APPTOKEN: self._auth_data["apptoken"],
                CONF_USERID: self._auth_data["userid"],
            }
            if self._email:
                new_data[CONF_EMAIL] = self._email
            if self._password:
                new_data[CONF_PASSWORD] = self._password
            if self._auth_data.get("cname"):
                new_data[CONF_CNAME] = self._auth_data["cname"]
            if self._discovered_host:
                new_data[CONF_REGION_HOST] = self._discovered_host
            if self._discovered_devices:
                new_data["devices"] = self._discovered_devices

            return self.async_update_reload_and_abort(
                reauth_entry, data=new_data
            )

        devices = self._discovered_devices or []
        if devices:
            first_dev = devices[0]
            title = f"{first_dev['device_name']} ({first_dev['device_mac']})"
        else:
            account_name = self._email or self._auth_data.get("userid", "Account")
            title = f"Zepp ({account_name})"

        entry_data: dict[str, Any] = {
            CONF_EMAIL: self._email or "",
            CONF_APPTOKEN: self._auth_data["apptoken"],
            CONF_USERID: self._auth_data["userid"],
            CONF_CNAME: self._auth_data.get("cname"),
            CONF_REGION_HOST: self._discovered_host,
            "devices": devices,
        }
        if self._password:
            entry_data[CONF_PASSWORD] = self._password
        if self._country_code:
            entry_data[CONF_COUNTRY_CODE] = self._country_code

        return self.async_create_entry(
            title=title,
            data=entry_data,
        )

    async def async_step_discovery_error(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Display discovery error screen with option to return and retry."""
        if user_input is not None:
            self._discovery_task = None
            if self._is_reauth:
                return await self.async_step_reauth_confirm()
            if self._auth_method == AUTH_METHOD_PASSWORD:
                return await self.async_step_password()
            return await self.async_step_token()

        error_detail = self._error_detail or ""
        return self.async_show_form(
            step_id="discovery_error",
            data_schema=vol.Schema({}),
            errors={"base": self._error} if self._error else None,
            description_placeholders={"error_detail": error_detail},
        )

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return ZeppOptionsFlowHandler()


class ZeppOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Zepp integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            interval = int(user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
            return self.async_create_entry(title="", data={CONF_SCAN_INTERVAL: interval})

        current_interval = str(
            self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=current_interval,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value="5", label="5 minutes"),
                                selector.SelectOptionDict(value="10", label="10 minutes"),
                                selector.SelectOptionDict(value="15", label="15 minutes (Default)"),
                                selector.SelectOptionDict(value="30", label="30 minutes"),
                                selector.SelectOptionDict(value="60", label="60 minutes (Hourly)"),
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )
