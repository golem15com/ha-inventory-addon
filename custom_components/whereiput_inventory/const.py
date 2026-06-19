"""Constants for the whereiput.it Inventory integration."""

DOMAIN = "whereiput_inventory"

# Self-host-first default: prefill the local docker-compose APP_PORT (8088) on
# the same host. The token API path is ``/api/v1/inventory``. Most users must
# change this to their own whereiput.it server's IP/hostname.
# http:// is accepted only for local/private hosts; public hosts require https.
DEFAULT_URL = "http://localhost:8088"

CONF_BASE_URL = "base_url"
CONF_TOKEN = "token"
CONF_AREAS = "areas"

DEFAULT_PER_PAGE = 5
