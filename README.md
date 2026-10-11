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
| Each tag (Premium) | Device tracker of where it was last heard · battery voltage · last seen |

A Plumio place of type *Home* counts as `home` without configuring a zone (can be turned off in the options).

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
