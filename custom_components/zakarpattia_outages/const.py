"""Settings shared by the integration and its data parser."""

from datetime import timedelta
from zoneinfo import ZoneInfo

DOMAIN = "zakarpattia_outages"
CONF_QUEUE = "queue"
CONF_GRID_SENSOR = "grid_sensor"
CONF_INVERT_GRID = "invert_grid"
EVENT_SCHEDULE_CHANGED = f"{DOMAIN}_schedule_changed"
PANEL_PATH = "zakarpattia-outages"
CARD_URL = f"/{DOMAIN}/schedule-card.js"
QUEUES = tuple(f"{queue}.{subqueue}" for queue in range(1, 7) for subqueue in (1, 2))

KYIV = ZoneInfo("Europe/Kyiv")
UPDATE_INTERVAL = timedelta(minutes=10)
SOURCE_URL = (
    "https://raw.githubusercontent.com/yaroslav2901/OE_OUTAGE_DATA/"
    "main/data/Zakarpattiaoblenerho.json"
)
