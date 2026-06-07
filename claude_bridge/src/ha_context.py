"""Fetch HA entity states and format a compact context block for Nova."""

from __future__ import annotations

import os

import httpx

RELEVANT_DOMAINS = {
    "light",
    "switch",
    "climate",
    "media_player",
    "sensor",
    "binary_sensor",
    "person",
    "device_tracker",
    "cover",
    "input_boolean",
    "input_select",
    "alarm_control_panel",
    "lock",
    "fan",
    "vacuum",
}

_SENSOR_SKIP_PREFIXES = (
    "sensor.sun_",
    "sensor.time",
    "sensor.date",
    "sensor.uptime",
    "sensor.last_boot",
)

_BORING_STATES = {"unavailable", "unknown", "none"}


async def get_ha_context(
    ha_url: str,
    token: str,
    max_entities: int | None = None,
) -> str | None:
    """Return a compact newline-delimited summary of home state, or None on failure."""
    if not token:
        return None

    if max_entities is None:
        max_entities = int(os.environ.get("HA_ENTITIES_MAX", "120"))

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(
                f"{ha_url}/api/states",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            states: list[dict] = resp.json()
    except Exception:
        return None

    lines: list[str] = []
    for entity in states:
        if len(lines) >= max_entities:
            break

        eid: str = entity.get("entity_id", "")
        domain = eid.split(".")[0]

        if domain not in RELEVANT_DOMAINS:
            continue
        if any(eid.startswith(p) for p in _SENSOR_SKIP_PREFIXES):
            continue

        state: str = entity.get("state", "unknown")
        attrs: dict = entity.get("attributes", {})
        name: str = attrs.get("friendly_name") or eid

        # Skip sensors stuck in boring states to reduce noise
        if domain == "sensor" and state in _BORING_STATES:
            continue

        extra = ""
        if domain == "climate":
            target = attrs.get("temperature")
            current = attrs.get("current_temperature")
            extra = f" (target {target}°, current {current}°)"
        elif domain == "media_player" and state not in ("off", "idle", "standby"):
            title = attrs.get("media_title") or attrs.get("media_album_name")
            if title:
                extra = f" — {title}"
        elif domain == "person":
            zone = attrs.get("friendly_name_zone") or state
            extra = f" ({zone})"
        elif domain in ("lock", "cover"):
            extra = f" ({state})"

        lines.append(f"  {name}: {state}{extra}")

    return "\n".join(lines) if lines else None
