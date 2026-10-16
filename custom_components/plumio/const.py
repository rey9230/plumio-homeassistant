"""Constants for the Plumio integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "plumio"

DEFAULT_API_URL = "https://api.useplumio.com"

CONF_API_URL = "api_url"
CONF_TOKEN = "token"
CONF_LINK_ID = "link_id"
CONF_NEST_ID = "nest_id"

# Options
CONF_MAX_GPS_ACCURACY = "max_gps_accuracy"
CONF_HOME_FROM_PLACES = "home_from_places"
DEFAULT_MAX_GPS_ACCURACY = 200
DEFAULT_HOME_FROM_PLACES = True
# Rooms: which sensor says where each tag is (tag id -> entity id), and whether to
# ask Bermuda to track the Nest's tags.
CONF_ROOM_SOURCES = "room_sources"
CONF_BERMUDA_AUTO_ADD = "bermuda_auto_add"
DEFAULT_BERMUDA_AUTO_ADD = True

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.EVENT,
    Platform.SENSOR,
]

# The stream is the source of truth; polling only covers for it.
POLL_INTERVAL_STREAM_UP = timedelta(minutes=10)
POLL_INTERVAL_STREAM_DOWN = timedelta(seconds=60)

# The server sends a heartbeat every 25 s; three missed ones mean the socket is dead.
STREAM_READ_TIMEOUT = 90
STREAM_BACKOFF_MIN = 1.0
STREAM_BACKOFF_MAX = 120.0

# The iBeacon UUID every Plumio tag sends (major = model, minor = unit number).
PLUMIO_IBEACON_UUID = "a923b4a3931044499732a63c687d4576"
BERMUDA_DOMAIN = "bermuda"
BERMUDA_CONFIGURED_DEVICES = "configured_devices"
# Plumio forgets a tag's room after 20 minutes without hearing it again.
ROOM_REFRESH_INTERVAL = timedelta(minutes=5)

# A member is "not reporting" after this long without a fix (matches the server).
STALE_AFTER = timedelta(minutes=30)

# Fired on the Home Assistant bus for every Plumio event.
EVENT_PLUMIO = "plumio_event"

EVENT_MEMBER = "member"
EVENT_RESYNC = "resync"
EVENT_ARRIVAL = "arrival"
EVENT_DEPARTURE = "departure"
EVENT_CHECKIN = "checkin"
EVENT_SOS = "sos"
EVENT_SOS_RESOLVED = "sos_resolved"
EVENT_CRASH = "crash"
EVENT_SPEED_ALERT = "speed_alert"
EVENT_LOW_BATTERY = "low_battery"
EVENT_TRIP_STARTED = "trip_started"
EVENT_TRIP_ENDED = "trip_ended"
EVENT_TRIP_COMPLETED = "trip_completed"
EVENT_SECURITY = "security"
EVENT_MEMBER_STALE = "member_stale"
EVENT_MEMBER_BACK = "member_back"
EVENT_TAG_SEEN = "tag_seen"

# What a member's event entity can emit.
MEMBER_EVENT_TYPES: list[str] = [
    EVENT_ARRIVAL,
    EVENT_DEPARTURE,
    EVENT_CHECKIN,
    EVENT_SOS,
    EVENT_SOS_RESOLVED,
    EVENT_CRASH,
    EVENT_SPEED_ALERT,
    EVENT_LOW_BATTERY,
    EVENT_TRIP_STARTED,
    EVENT_TRIP_ENDED,
    EVENT_TRIP_COMPLETED,
    EVENT_SECURITY,
    EVENT_MEMBER_STALE,
    EVENT_MEMBER_BACK,
]

PLACE_TYPE_HOME = "HOME"

ATTR_MEMBER_ID = "member_id"
ATTR_PLACE_ID = "place_id"
ATTR_NEST_ID = "nest_id"

# Where a free Nest is told what Premium adds.
PREMIUM_URL = "https://www.useplumio.com/home-assistant"
