"""ESP Web Tools manifest for one Plumio Hogar image.

Usage: firmware_manifest.py <name> <chip family> <version>  (prints the JSON)
"""

from __future__ import annotations

import json
import sys


def manifest(name: str, chip: str, version: str) -> dict:
    return {
        "name": "Plumio Hogar",
        "version": version,
        # After installing, the installer offers to add it to Home Assistant.
        "home_assistant_domain": "esphome",
        "new_install_prompt_erase": True,
        "builds": [{"chipFamily": chip, "parts": [{"path": f"{name}.factory.bin", "offset": 0}]}],
    }


if __name__ == "__main__":
    print(json.dumps(manifest(*sys.argv[1:4]), indent=2))
