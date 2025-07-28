"""Config flow for Eufy S1 Pro Robot Vacuum integration."""
import logging
import voluptuous as vol
from typing import Any, Dict, Optional

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN, CONF_DEVICE_ID, CONF_LOCAL_KEY, CONF_IP_ADDRESS, DEFAULT_NAME
from .coordinator import EufyS1ProCoordinator

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
    vol.Required(CONF_DEVICE_ID): str,
    vol.Required(CONF_LOCAL_KEY): str,
    vol.Optional(CONF_IP_ADDRESS): str,
})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eufy S1 Pro Robot Vacuum."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", 
                data_schema=STEP_USER_DATA_SCHEMA,
                description_placeholders={
                    "setup_url": "https://github.com/yourrepo/eufy-s1-pro-homeassistant#setup"
                }
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Check if already configured
            await self.async_set_unique_id(info["device_id"])
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", 
            data_schema=STEP_USER_DATA_SCHEMA, 
            errors=errors,
            description_placeholders={
                "setup_url": "https://github.com/yourrepo/eufy-s1-pro-homeassistant#setup"
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Eufy S1 Pro."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_IP_ADDRESS,
                    default=self.config_entry.data.get(CONF_IP_ADDRESS, "")
                ): str,
            })
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""


async def validate_input(hass: HomeAssistant, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the user input allows us to connect."""
    
    device_id = data[CONF_DEVICE_ID]
    local_key = data[CONF_LOCAL_KEY]
    ip_address = data.get(CONF_IP_ADDRESS)
    
    # Create coordinator to test connection
    coordinator = EufyS1ProCoordinator(
        hass=hass,
        device_id=device_id,
        local_key=local_key,
        ip_address=ip_address,
    )
    
    try:
        # Try to connect and get data
        await coordinator.async_config_entry_first_refresh()
        
        # Clean up
        await coordinator.async_disconnect()
        
        # Return info that you want to store in the config entry.
        return {
            "title": data[CONF_NAME],
            "device_id": device_id,
        }
        
    except Exception as ex:
        _LOGGER.error("Failed to connect to vacuum: %s", ex)
        if "auth" in str(ex).lower() or "key" in str(ex).lower():
            raise InvalidAuth from ex
        else:
            raise CannotConnect from ex