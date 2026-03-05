"""Constants for the Bamartech integration."""

DOMAIN = "bamartech"

# Config entry keys (credentials supplied by the user)
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Fixed backend — not configurable by the user
DEFAULT_HOST = "lentecdesignbamw.com.pl"
DEFAULT_PORT = 9001

# MQTT reconnect behaviour
WS_RECONNECT_DELAY = 5        # seconds between reconnect attempts
WS_MAX_RECONNECT_ATTEMPTS = 10

# ---------------------------------------------------------------------------
# Output bitmasks — byte 2 of the 11-byte device state packet
# ---------------------------------------------------------------------------
BITMASK_BLOWER   = 0x01   # Dmuchawa
BITMASK_PUMP     = 0x02   # Pompa
BITMASK_SOLENOID = 0x04   # Elektrozawór
BITMASK_OUTPUT   = 0x08   # Wyjście
