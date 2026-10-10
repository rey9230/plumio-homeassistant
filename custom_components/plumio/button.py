"""Buttons: ask for a fresh location, make a phone ring."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .actions import run_action
from .const import DOMAIN
from .coordinator import PlumioConfigEntry, PlumioCoordinator
from .entity import MemberEntity, NestEntity, async_add_as_they_appear


async def async_setup_entry(
    hass: HomeAssistant, entry: PlumioConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([RefreshAllButton(coordinator)])
    async_add_as_they_appear(
        coordinator,
        async_add_entities,
        members=lambda user_id: [RequestLocationButton(coordinator, user_id), RingButton(coordinator, user_id)],
    )


def _actions_allowed(coordinator: PlumioCoordinator) -> bool:
    return bool(coordinator.data.capabilities.get("actions"))


class RequestLocationButton(MemberEntity, ButtonEntity):
    """Wake this member's phone for a fresh fix."""

    def __init__(self, coordinator: PlumioCoordinator, user_id: str) -> None:
        super().__init__(coordinator, user_id, "request_location")

    @property
    def available(self) -> bool:
        return super().available and _actions_allowed(self.coordinator)

    async def async_press(self) -> None:
        sent = await run_action(self.coordinator.client.request_location(self.user_id))
        if not sent:
            # Paused, asked seconds ago, or no phone to reach: say so instead of pretending.
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="location_not_requested")


class RingButton(MemberEntity, ButtonEntity):
    """Make this member's phone ring, to find it."""

    def __init__(self, coordinator: PlumioCoordinator, user_id: str) -> None:
        super().__init__(coordinator, user_id, "ring")

    @property
    def available(self) -> bool:
        return super().available and _actions_allowed(self.coordinator)

    async def async_press(self) -> None:
        await run_action(self.coordinator.client.ring(self.user_id))


class RefreshAllButton(NestEntity, ButtonEntity):
    """Ask everyone in the Nest for a fresh fix."""

    def __init__(self, coordinator: PlumioCoordinator) -> None:
        super().__init__(coordinator, "refresh_all")

    @property
    def available(self) -> bool:
        return super().available and _actions_allowed(self.coordinator)

    async def async_press(self) -> None:
        await run_action(self.coordinator.client.request_location())
