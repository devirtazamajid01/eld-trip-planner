"""Wrapper around OpenRouteService directions API."""

from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

ORS_BASE = "https://api.openrouteservice.org"


def get_directions(
    coordinates: list[list[float]],
) -> dict[str, Any]:
    """Fetch driving directions from ORS.

    Args:
        coordinates: list of [lon, lat] pairs (ORS uses lon,lat order).

    Returns:
        Dict with ``distance_miles``, ``duration_hours``, ``geometry``
        (GeoJSON LineString coords), and ``steps`` (maneuver list).
    """
    api_key = settings.ORS_API_KEY
    if not api_key:
        raise ValueError("ORS_API_KEY is not configured. Set it in the environment.")

    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json; charset=utf-8",
    }
    body = {
        "coordinates": coordinates,
        "instructions": True,
        "geometry": True,
        "units": "mi",
    }

    # Try heavy-vehicle profile first, fall back to driving-car
    for profile in ("driving-hcv", "driving-car"):
        url = f"{ORS_BASE}/v2/directions/{profile}"
        resp = requests.post(url, json=body, headers=headers, timeout=30)
        if resp.status_code == 200:
            break
        logger.warning(
            "ORS profile %s returned %s: %s",
            profile,
            resp.status_code,
            resp.text[:200],
        )

    if resp.status_code != 200:
        try:
            err_body = resp.json()
            err_msg = err_body.get("error", {}).get("message", resp.text[:300])
        except Exception:
            err_msg = resp.text[:300]
        raise ValueError(f"Route not found: {err_msg}")

    data = resp.json()

    route = data["routes"][0]
    summary = route["summary"]

    steps: list[dict[str, Any]] = []
    cumulative_distance = 0.0
    cumulative_duration = 0.0

    for segment in route["segments"]:
        for step in segment["steps"]:
            step_dist = step["distance"]
            step_dur = step["duration"] / 3600
            cumulative_distance += step_dist
            cumulative_duration += step_dur
            steps.append(
                {
                    "instruction": step.get("instruction", ""),
                    "distance_miles": round(step_dist, 2),
                    "duration_hours": round(step_dur, 4),
                    "cumulative_distance_miles": round(cumulative_distance, 2),
                    "cumulative_duration_hours": round(cumulative_duration, 4),
                    "way_points": step.get("way_points", []),
                }
            )

    geometry_coords = route["geometry"]

    return {
        "distance_miles": round(summary["distance"], 2),
        "duration_hours": round(summary["duration"] / 3600, 2),
        "geometry": geometry_coords,
        "steps": steps,
    }


def geocode(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Forward-geocode a place name via ORS."""
    api_key = settings.ORS_API_KEY
    if not api_key:
        raise ValueError("ORS_API_KEY is not configured.")

    url = f"{ORS_BASE}/geocode/search"
    params = {
        "api_key": api_key,
        "text": query,
        "size": limit,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    results: list[dict[str, Any]] = []
    for feature in data.get("features", []):
        coords = feature["geometry"]["coordinates"]
        results.append(
            {
                "lon": coords[0],
                "lat": coords[1],
                "name": feature["properties"].get("label", ""),
            }
        )
    return results


def interpolate_point_on_route(
    geometry: list[list[float]],
    total_distance_miles: float,
    target_miles: float,
) -> dict[str, float]:
    """Find the approximate lat/lon at a given mile marker along a route."""
    if target_miles <= 0:
        return {"lon": geometry[0][0], "lat": geometry[0][1]}
    if target_miles >= total_distance_miles:
        return {"lon": geometry[-1][0], "lat": geometry[-1][1]}

    fraction = target_miles / total_distance_miles if total_distance_miles else 0
    total_points = len(geometry)
    target_index = fraction * (total_points - 1)
    idx = int(target_index)
    remainder = target_index - idx

    if idx >= total_points - 1:
        return {"lon": geometry[-1][0], "lat": geometry[-1][1]}

    p1 = geometry[idx]
    p2 = geometry[idx + 1]
    lon = p1[0] + remainder * (p2[0] - p1[0])
    lat = p1[1] + remainder * (p2[1] - p1[1])
    return {"lon": round(lon, 6), "lat": round(lat, 6)}


def reverse_geocode(lat: float, lon: float) -> str:
    """Best-effort reverse geocode to get a city/state label."""
    api_key = settings.ORS_API_KEY
    if not api_key:
        return f"{lat:.2f}, {lon:.2f}"
    try:
        url = f"{ORS_BASE}/geocode/reverse"
        params = {"api_key": api_key, "point.lat": lat, "point.lon": lon, "size": 1}
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        features = resp.json().get("features", [])
        if features:
            props = features[0]["properties"]
            city = props.get("locality", props.get("name", ""))
            state = props.get("region_a", props.get("region", ""))
            if city and state:
                return f"{city}, {state}"
            return props.get("label", f"{lat:.2f}, {lon:.2f}")
    except Exception:
        logger.exception("Reverse geocode failed")
    return f"{lat:.2f}, {lon:.2f}"
