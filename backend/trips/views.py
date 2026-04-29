from __future__ import annotations

import logging
import math
from datetime import UTC, datetime, timedelta

import requests as http_requests
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from . import hos_engine, route_service
from .serializers import TripPlanRequestSerializer

logger = logging.getLogger(__name__)


class TripPlanThrottle(AnonRateThrottle):
    rate = "10/minute"


class TripPlanView(APIView):
    """POST /api/trip-plan — compute a HOS-compliant trip schedule."""

    throttle_classes = [TripPlanThrottle]

    def post(self, request: Request) -> Response:
        ser = TripPlanRequestSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        data = ser.validated_data
        cur = data["current_location"]
        pickup = data["pickup_location"]
        dropoff = data["dropoff_location"]
        cycle_used = data["current_cycle_used"]

        coords = [
            [cur["lon"], cur["lat"]],
            [pickup["lon"], pickup["lat"]],
            [dropoff["lon"], dropoff["lat"]],
        ]

        try:
            directions = route_service.get_directions(coords)
        except http_requests.HTTPError as exc:
            logger.error("ORS directions failed: %s", exc)
            return Response(
                {"error": f"Routing service error: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except http_requests.ConnectionError:
            return Response(
                {"error": "Could not connect to routing service. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except http_requests.Timeout:
            return Response(
                {"error": "Routing service timed out. Please try again."},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )

        total_dist = directions["distance_miles"]
        total_dur = directions["duration_hours"]

        d1 = _haversine(cur["lat"], cur["lon"], pickup["lat"], pickup["lon"])
        d2 = _haversine(pickup["lat"], pickup["lon"], dropoff["lat"], dropoff["lon"])
        ratio = d1 / (d1 + d2) if (d1 + d2) > 0 else 0.5
        leg1_dist = total_dist * ratio
        leg1_dur = total_dur * ratio
        leg2_dist = total_dist - leg1_dist
        leg2_dur = total_dur - leg1_dur

        geometry = directions["geometry"]
        decoded = _decode_polyline(geometry) if isinstance(geometry, str) else geometry

        def point_interpolator(mile_marker: float) -> dict:
            return route_service.interpolate_point_on_route(decoded, total_dist, mile_marker)

        now = datetime.now(UTC).replace(second=0, microsecond=0)
        minute_round = ((now.minute + 14) // 15) * 15
        if minute_round >= 60:
            start = now.replace(minute=0) + timedelta(hours=1)
        else:
            start = now.replace(minute=minute_round)
        if start.hour < 6:
            start = start.replace(hour=6, minute=0)

        schedule = hos_engine.plan_trip(
            current_to_pickup_miles=leg1_dist,
            current_to_pickup_hours=leg1_dur,
            pickup_to_dropoff_miles=leg2_dist,
            pickup_to_dropoff_hours=leg2_dur,
            current_cycle_used=cycle_used,
            start_time=start,
            current_location_name=cur.get("name", "Start"),
            current_location_lat=cur["lat"],
            current_location_lon=cur["lon"],
            pickup_location_name=pickup.get("name", "Pickup"),
            pickup_location_lat=pickup["lat"],
            pickup_location_lon=pickup["lon"],
            dropoff_location_name=dropoff.get("name", "Dropoff"),
            dropoff_location_lat=dropoff["lat"],
            dropoff_location_lon=dropoff["lon"],
            point_interpolator=point_interpolator,
        )

        return Response(
            {
                "route": {
                    "total_distance_miles": round(total_dist, 1),
                    "total_duration_hours": round(total_dur, 2),
                    "geometry": decoded,
                },
                "stops": schedule["stops"],
                "daily_logs": schedule["daily_logs"],
            }
        )


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles between two lat/lon points."""
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _decode_polyline(encoded: str) -> list[list[float]]:
    """Decode a Google-style encoded polyline to [[lon, lat], ...]."""
    coords = []
    index = 0
    lat = 0
    lng = 0

    while index < len(encoded):
        for is_lng in (False, True):
            shift = 0
            result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if (result & 1) else (result >> 1)
            if is_lng:
                lng += delta
            else:
                lat += delta

        coords.append([lng / 1e5, lat / 1e5])

    return coords
