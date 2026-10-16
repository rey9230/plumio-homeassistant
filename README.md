# Plumio for Home Assistant

Your family's location in Home Assistant, pushed live from your [Plumio](https://www.useplumio.com) Nest.

- **Live, not polled.** Arrivals and departures reach your automations in seconds over a persistent connection, with a polling fallback if it drops.
- **No password.** Home Assistant shows a code; the Nest's admin approves it in the Plumio app with their fingerprint or PIN. The link can be removed from the app at any time.
- **Privacy is respected, not worked around.** Someone who pauses sharing has no location here (the tracker goes *unknown*, never "last seen at…"). Someone sharing an approximate area shows that area. The admin can leave any member out.

## Install

1. In HACS, add this repository as a custom repository (category *Integration*) and install **Plumio**.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → Plumio**.
4. On the phone of the Nest's admin, scan the code shown (or open Plumio → Nest → Integrations and type it), and approve.
5. Press **Submit** in Home Assistant.

Only an admin of the Nest can link it. Everyone in the Nest is told when it is linked or unlinked.

## What you get

| Device | Entities |
|---|---|
| Each member | Device tracker (home / away) · battery · charging · place · at place since · last seen · online · sharing location · SOS · not reporting · events |
| Each member (Premium) | Position on the map · speed · activity · driving · distance from home · approximate area · security alert · last trip distance, top speed, end time and driving events · *Request location* and *Ring phone* buttons |
| The Nest | Members home · anyone home · everyone home · plan · live connection · *Refresh everyone* button |
| Each place | Members here (with names) · occupied |
| Each tag (Premium) | Device tracker of where it was last heard · battery voltage · last seen · **room** (see below) |

A Plumio place of type *Home* counts as `home` without configuring a zone (can be turned off in the options).

### Which room each tag is in

A phone can only say a tag is *at home*. Home Assistant can say *in the kitchen*: put a
Bluetooth proxy in each room and let [Bermuda](https://github.com/agittins/bermuda) work
out which one hears the tag best.

1. **One ESP32 per room** running ESPHome's Bluetooth proxy (see
   [`esphome/`](esphome/README.md) for a ready-made firmware you install from the browser).
   Assign each proxy to its area in Home Assistant.
2. **Install Bermuda** from HACS.
3. That's it. Plumio adds your tags to Bermuda's list of devices to track (switch it
   off in the options if you'd rather do it yourself), finds the Area sensor Bermuda
   creates for each one, and fills the tag's **Room** sensor.

The room also reaches the Plumio app, so the family sees *Keys · Kitchen, 2 min ago*
on their phones. Home Assistant repeats it every 5 minutes while the tag is still
there; if it stops (Home Assistant offline, tag out of range), the app forgets the
room after 20 minutes and goes back to the last place a phone heard it.

Using something other than Bermuda (ESPresense, room-assistant, a template)? Any sensor
whose state is a room name works: pick it per tag in **Settings → Devices & services →
Plumio → Configure**.

### Day route card

A dashboard card that draws where a member went on a given day: the route, each trip between two stops, and the stops, with arrows to move between days. It reads the day from Plumio, so it also shows the days before the Nest was linked. Needs Premium.

Add it from the dashboard's card picker (*Plumio — Day route*), or by hand:

```yaml
type: custom:plumio-route-card
entity: device_tracker.camila
```

Nothing to install: the card comes with the integration.

### Free and Premium

On a free Nest, Home Assistant knows **who is home**, **which place each person is in**, **arrivals and departures**, **battery** and **SOS** — all live. That is enough for "lights on when the first person arrives".

Plumio Premium on the Nest owner's account adds the live position on the map, speed and activity, driving, trips, tags and the actions. On a free Nest those entities are still created, shown as *unavailable*, and a notice in *Settings → Repairs* says what Premium unlocks. They come alive on their own when the owner upgrades; nothing to reconfigure.

### Events

Each member has an event entity, and every event is also fired on the bus as `plumio_event`:

`arrival` · `departure` · `sos` · `sos_resolved` · `crash` · `low_battery` · `member_stale` · `member_back`

and, with Premium: `checkin` · `speed_alert` · `security` · `trip_started` · `trip_ended` · `trip_completed` · `tag_seen`

```yaml
automation:
  - alias: Lights on when the first person gets home
    triggers:
      - trigger: state
        entity_id: binary_sensor.casa_anyone_home
        to: "on"
    actions:
      - action: light.turn_on
        target:
          entity_id: light.entrance

  - alias: Tell me when Camila's phone is running low
    triggers:
      - trigger: event
        event_type: plumio_event
        event_data:
          type: low_battery
          member_name: Camila
    actions:
      - action: notify.mobile_app
        data:
          message: "Camila is at {{ trigger.event.data.batteryLevel }}%"
```

### Blueprints

Ready-made automations: import one, pick the people, tags and lights from menus, done. Every one of them also leaves room for your own actions.

| | Blueprint | What it does | Needs |
|---|---|---|---|
| [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Frey9230%2Fplumio-homeassistant%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplumio%2Farrival_home.yaml) | **Someone arrives home** | Entrance lights, gate, alarm. Optionally only the first one, only after dark, and only once the door sensor sees them walk in. | Free |
| [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Frey9230%2Fplumio-homeassistant%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplumio%2Fhouse_empty.yaml) | **Last one out / first one in** | Everything off when the house has been empty for a while; your welcome scene when the first one is back. | Free |
| [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Frey9230%2Fplumio-homeassistant%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplumio%2Fplace_alert.yaml) | **Arrives at or leaves a place** | "Camila arrived at School", for one place or all of them. | Free |
| [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Frey9230%2Fplumio-homeassistant%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplumio%2Fsos_alarm.yaml) | **SOS at home** | Critical notification with the map, lights red, siren and a spoken announcement. Undone when the SOS is resolved. | Free |
| [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Frey9230%2Fplumio-homeassistant%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplumio%2Fcrash_alert.yaml) | **Crash detected** | Critical notification with where it happened, and an announcement at home. | Free |
| [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Frey9230%2Fplumio-homeassistant%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplumio%2Fnot_reporting.yaml) | **A member stopped reporting** | Their phone has been silent for 30 minutes, and when it is back. | Free |
| [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Frey9230%2Fplumio-homeassistant%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplumio%2Flow_battery.yaml) | **Low battery** | Members' phones, and tags' coin cells before they die. | Tags: Premium |
| [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Frey9230%2Fplumio-homeassistant%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplumio%2Fdriving_report.yaml) | **Driving alerts and trip summary** | Speeding, and a summary at the end of each trip (optionally only trips with incidents). | Premium |
| [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Frey9230%2Fplumio-homeassistant%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplumio%2Fforgot_tag.yaml) | **You left without your keys** | You left home and your keys (wallet, backpack) did not. | Premium |
| [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Frey9230%2Fplumio-homeassistant%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplumio%2Ftag_left_home.yaml) | **A tag left home without its owner** | The car keys left home while their owner is still there. | Premium |
| [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Frey9230%2Fplumio-homeassistant%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplumio%2Ftag_reminder.yaml) | **Don't forget it** | At 7:30 on school days, if the backpack is still home (or still in the bedroom), say it on the phones and out loud. | Premium |

Notifications go to any notify action you name (`notify.mobile_app_pixel_8`, or a group such as `notify.family` to reach everyone). SOS and crash alerts are sent as critical notifications, which ring even on silent.

### Actions

| Action | What it does |
|---|---|
| `plumio.request_location` | Wakes a member's phone for a fresh fix |
| `plumio.ring_phone` / `plumio.stop_ring` | Makes a phone ring to find it |
| `plumio.create_place` / `update_place` / `delete_place` | Manages the Nest's places |
| `plumio.import_zones` | Copies your Home Assistant zones into the Nest as places |
| `plumio.get_trips` / `get_driving_summary` / `get_day_timeline` | Return data for templates and scripts |

Actions and trip data need Plumio Premium on the Nest owner's account (see *Free and Premium* above), and the admin can switch actions off for the integration from the app.

## Good to know

- Tags cannot be made to ring: they have no buzzer. Only phones ring.
- Children under 13 never expose trips, and their history is limited to two days, whatever the plan.
- If the link is removed from the app, or the admin who created it stops administering the Nest, Home Assistant asks you to link again.

## Development

```bash
pip install -r requirements_test.txt
pytest
python scripts/gen_translations.py   # every string lives there, in seven languages
```
