"""Constants for the BLANCO Smart Home Cloud integration."""

from datetime import timedelta

DOMAIN = "blanco_smart_home"
INTEGRATION_VERSION = "0.1.0"

CONF_APP_ID = "app_id"
CONF_APP_LOCALE = "app_locale"
CONF_DEV_ID = "dev_id"
CONF_DEV_TYPE = "dev_type"
CONF_SERIAL = "serial"
CONF_SERVICE_CODE = "service_code"
CONF_TOKEN_TYPE = "token_type"

DATA_SYSTEM = "system"
DATA_STATUS = "status"
DATA_SETTINGS = "settings"
DATA_ERRORS = "errors"
DATA_ACTIONS = "actions"
DATA_HISTORY = "history"
DATA_API_STATUS = "api_status"
DATA_AVAILABLE = "available"

UPDATE_INTERVAL = timedelta(seconds=60)
HISTORY_UPDATE_INTERVAL = timedelta(minutes=15)
