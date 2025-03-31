from typing import Any
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import voluptuous as vol
from .const import DOMAIN, NAME, DEBUG_MODE, CONF_SELENIUM
from .stw_consumption import get_water_usage

CANNOT_CONNECT = "cannot_connect"
INVALID_AUTH = "invalid_auth"


class STWaterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if DEBUG_MODE:
            # In debug mode, create entry with dummy credentials
            return self.async_create_entry(
                title=NAME,
                data={CONF_USERNAME: "debug_user", CONF_PASSWORD: "debug_pass", CONF_SELENIUM: "http://selenium:4444"},
            )

        if user_input is not None:
            try:
                result = await self.hass.async_add_executor_job(
                    get_water_usage,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_SELENIUM]
                )
                if result:
                    return self.async_create_entry(
                        title=NAME,
                        data=user_input,
                    )
                else:
                    errors["base"] = INVALID_AUTH
            except Exception:
                errors["base"] = CANNOT_CONNECT

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_SELENIUM, default="http://selenium:4444"): str,
                }
            ),
            errors=errors,
        )
