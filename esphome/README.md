# Plumio Hogar — firmware for ESP32 room sensors

A cheap ESP32 in each room turns Home Assistant into something that knows **which room
each Plumio tag is in**. It runs ESPHome as a Bluetooth proxy: it hears the tags (and
any other Bluetooth device) and passes them to Home Assistant, where
[Bermuda](https://github.com/agittins/bermuda) works out the room. The Plumio
integration then fills each tag's **Room** sensor and tells the Plumio app.

You buy the boards; this folder is the software.

## What to buy

| Part | What for | Notes |
|---|---|---|
| **ESP32 DevKit** (ESP32-WROOM-32) | One per room | The cheapest and enough for most rooms. Any "ESP32 DevKit V1" works. |
| **ESP32-S3 DevKitC** | Big rooms, busy houses | More memory for many Bluetooth devices at once. |
| **HLK-LD2410** mmWave radar (optional) | "Someone is in the room", even sitting still | Wire to GPIO16/17 and install the *presence* firmware. |
| USB power supply + **data** USB cable | Power and the first install | A charge-only cable will not be seen by the installer. |

Plan on one board per room you care about. A room without one still works, but tags in
it are placed in the nearest room that has one.

## Install

**From the browser (easiest).** Open the installer, plug the ESP32 into your computer and
press *Install*. It flashes the firmware and asks for your Wi-Fi.

→ <https://www.useplumio.com/room-sensors>

(Chrome or Edge on a computer. [`.github/workflows/firmware.yml`](../.github/workflows/firmware.yml)
compiles the firmware and publishes it to the website; until it has run, the page says
"Coming soon".)

**From the ESPHome dashboard.** Add a new device with one of these files, or adopt the
board after a browser install:

| File | Board |
|---|---|
| [`plumio-hogar.yaml`](plumio-hogar.yaml) | ESP32 DevKit |
| [`plumio-hogar-s3.yaml`](plumio-hogar-s3.yaml) | ESP32-S3 DevKitC |
| [`plumio-hogar-presencia.yaml`](plumio-hogar-presencia.yaml) | ESP32 DevKit + HLK-LD2410 on GPIO16 (RX) / GPIO17 (TX) |

The shared parts live in [`packages/`](packages/).

No Wi-Fi yet, or it changed? The board opens its own hotspot, **Plumio Hogar**: join it
from a phone and pick the network.

## Then, in Home Assistant

1. **Settings → Devices & services**: the board shows up as discovered. Add it.
2. Open the new device and **assign it to its area** (Kitchen, Bedroom…). The area name is
   the room name everyone will see.
3. Install **Bermuda** from HACS and add it. The Plumio integration adds your tags to
   Bermuda's list on its own (Plumio → Configure, if you'd rather not).
4. A few minutes later each tag's **Room** sensor says where it is, and so does the
   Plumio app.

## Placing the boards

- Middle of the room, at table height or higher, away from metal and the fridge.
- One per room beats two in one room and none next door: Bermuda decides by which board
  hears a tag loudest.
- Walls matter less than distance; doors left open matter more than you'd think. If a
  tag flips between two rooms, move one board a little further from the shared wall.
