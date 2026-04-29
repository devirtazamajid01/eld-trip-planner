"""HOS(Hours of Service) trip-scheduling engine.

Imports domain models from ``hos_models`` and contains only scheduling logic:
  - ``TripScheduler`` — orchestrates the trip, inserts HOS-mandated stops
  - ``plan_trip()``   — public adapter with flat signature for ``views.py``
  - ``_build_daily_logs()`` — pure function: slices events into daily log sheets
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from .hos_models import (
    AVG_SPEED_MPH,
    BREAK_DURATION,
    CYCLE_LIMIT,
    DROPOFF_DURATION,
    FUEL_INTERVAL_MILES,
    FUEL_STOP_DURATION,
    MAX_DRIVING_BEFORE_BREAK,
    OFF_DUTY_REQUIRED,
    PICKUP_DURATION,
    PRE_TRIP_DURATION,
    RESTART_DURATION,
    DailyLog,
    DriverState,
    LocationPoint,
    ScheduleEvent,
    Stop,
    TripConfig,
)

# ── Scheduler ────────────────────────────────────────────────────────────────


class TripScheduler:
    """Schedules a trip segment-by-segment, inserting HOS-mandated stops.

    Responsibilities:
        - Track driver state via ``DriverState``
        - Insert mandatory breaks, rests, and fuel stops
        - Record events and stops chronologically

    Does NOT handle:
        - Route geometry or geocoding  →  route_service.py
        - API request/response         →  views.py
        - Daily log canvas rendering   →  logDrawing.ts (frontend)
    """

    def __init__(self, config: TripConfig) -> None:
        self._cfg = config
        self._state = DriverState(
            current_time=config.start_time,
            cycle_used=min(config.cycle_used, CYCLE_LIMIT),
        )
        self._events: list[ScheduleEvent] = []
        self._stops: list[Stop] = []

    # ── Public interface ──────────────────────────────────────────────────────

    def run(self) -> dict[str, Any]:
        """Execute the full trip schedule and return stops, daily logs, and events."""
        self._add_pre_shift_off_duty()
        self._ensure_on_shift()
        self._record_on_duty_event(PRE_TRIP_DURATION, self._cfg.current.name, "Pre-trip inspection")
        self._state.log_on_duty(PRE_TRIP_DURATION)

        if self._cfg.leg1_miles > 0.1:
            self._drive(self._cfg.leg1_miles, self._cfg.avg_speed_leg1)

        self._handle_waypoint("pickup", self._cfg.pickup, PICKUP_DURATION, "Loading at pickup")

        if self._cfg.leg2_miles > 0.1:
            self._drive(self._cfg.leg2_miles, self._cfg.avg_speed_leg2)

        self._handle_waypoint(
            "dropoff", self._cfg.dropoff, DROPOFF_DURATION, "Unloading at dropoff"
        )

        self._fill_remainder_of_day()

        daily_logs = _build_daily_logs(self._events, self._cfg.total_miles, self._cfg.total_hours)

        return {
            "stops": [s.to_dict() for s in self._stops],
            "daily_logs": [dl.to_dict() for dl in daily_logs],
            "events": [self._event_to_dict(e) for e in self._events],
        }

    # ── Private scheduling methods ────────────────────────────────────────────

    def _drive(self, miles_to_drive: float, speed: float) -> None:
        """Drive a distance, inserting mandatory HOS stops as needed."""
        remaining = miles_to_drive

        while remaining > 0.01:
            self._ensure_on_shift()

            if self._state.cycle_remaining < 0.5:
                self._take_34hr_restart()
                continue

            if (
                self._state.driving_remaining_this_shift < 0.1
                or self._state.duty_window_remaining < 0.1
            ):
                self._take_10hr_rest()
                continue

            miles_until_fuel = FUEL_INTERVAL_MILES - self._state.miles_since_fuel
            if miles_until_fuel <= 0:
                miles_until_fuel = FUEL_INTERVAL_MILES

            max_drive_hrs = self._state.max_drivable_hours()
            drivable = min(remaining, max_drive_hrs * speed, miles_until_fuel)

            if drivable < 0.1:
                self._resolve_constraint()
                continue

            drive_hours = drivable / speed
            self._record_driving_event(drive_hours)
            self._state.log_driving(drive_hours, drivable)
            remaining -= drivable

            if self._state.miles_since_fuel >= FUEL_INTERVAL_MILES - 0.1 and remaining > 0.1:
                self._take_fuel_stop()

            if (
                self._state.driving_since_break >= MAX_DRIVING_BEFORE_BREAK - 0.01
                and remaining > 0.1
            ):
                self._take_30min_break()

        if self._state.driving_since_break >= MAX_DRIVING_BEFORE_BREAK - 0.01:
            self._take_30min_break()

    def _resolve_constraint(self) -> None:
        """Determine which HOS constraint is binding and service it."""
        if self._state.driving_remaining_before_break < 0.1:
            self._take_30min_break()
        elif (
            self._state.driving_remaining_this_shift < 0.1
            or self._state.duty_window_remaining < 0.1
        ):
            self._take_10hr_rest()
        else:
            self._take_34hr_restart()

    def _handle_waypoint(
        self,
        stop_type: str,
        location: LocationPoint,
        duration: float,
        desc: str,
    ) -> None:
        """Record a pickup or dropoff: ensures shift capacity then logs on-duty time."""
        self._ensure_on_shift()
        if self._state.cycle_remaining <= 0.5:
            self._take_34hr_restart()
        if self._state.duty_window_remaining < duration + 0.5:
            self._take_10hr_rest()

        arrival = self._state.current_time
        self._record_on_duty_event(duration, location.name, desc)
        self._state.log_on_duty(duration)
        self._stops.append(
            Stop(
                stop_type=stop_type,
                location_name=location.name,
                location_lat=location.lat,
                location_lon=location.lon,
                arrival_time=arrival,
                departure_time=self._state.current_time,
                mile_marker=self._state.odometer,
            )
        )

    # ── HOS stop actions (each action is one discrete method) ────────────────

    def _take_30min_break(self) -> None:
        self._add_off_duty_stop("rest_30min", BREAK_DURATION, "30-min rest break")
        self._state.reset_break_clock()

    def _take_fuel_stop(self) -> None:
        self._add_on_duty_stop("fuel", FUEL_STOP_DURATION, "Fuel stop")
        self._state.log_on_duty(FUEL_STOP_DURATION)
        self._state.reset_fuel_clock()

    def _take_10hr_rest(self) -> None:
        self._state.end_shift()
        self._add_off_duty_stop("rest_10hr", OFF_DUTY_REQUIRED, "10-hr off-duty rest")
        self._state.begin_shift()

    def _take_34hr_restart(self) -> None:
        self._state.end_shift()
        self._add_off_duty_stop("restart_34hr", RESTART_DURATION, "34-hr restart (cycle reset)")
        self._state.reset_cycle()
        self._state.begin_shift()

    # ── Event and stop recording helpers ─────────────────────────────────────

    def _add_off_duty_stop(self, stop_type: str, duration: float, desc: str) -> None:
        loc = self._loc_at_odometer()
        name = self._name_at_odometer()
        arrival = self._state.current_time
        self._append_event("off_duty", duration, name, desc)
        self._stops.append(
            Stop(
                stop_type=stop_type,
                location_name=name,
                location_lat=loc["lat"],
                location_lon=loc["lon"],
                arrival_time=arrival,
                departure_time=self._state.current_time,
                mile_marker=self._state.odometer,
            )
        )

    def _add_on_duty_stop(self, stop_type: str, duration: float, desc: str) -> None:
        loc = self._loc_at_odometer()
        name = self._name_at_odometer()
        arrival = self._state.current_time
        self._append_event("on_duty_nd", duration, name, desc)
        self._stops.append(
            Stop(
                stop_type=stop_type,
                location_name=name,
                location_lat=loc["lat"],
                location_lon=loc["lon"],
                arrival_time=arrival,
                departure_time=self._state.current_time,
                mile_marker=self._state.odometer,
            )
        )

    def _record_driving_event(self, hours: float) -> None:
        self._append_event("driving", hours, self._name_at_odometer(), "Driving")

    def _record_on_duty_event(self, hours: float, name: str, desc: str) -> None:
        self._append_event("on_duty_nd", hours, name, desc)

    def _append_event(self, etype: str, hours: float, name: str, desc: str) -> None:
        loc = self._loc_at_odometer()
        ev = ScheduleEvent(
            event_type=etype,
            start_time=self._state.current_time,
            end_time=self._state.current_time + timedelta(hours=hours),
            location_name=name,
            location_lat=loc["lat"],
            location_lon=loc["lon"],
            mile_marker=self._state.odometer,
            description=desc,
        )
        self._events.append(ev)
        self._state.advance(hours)

    # ── Utility methods ───────────────────────────────────────────────────────

    def _ensure_on_shift(self) -> None:
        if not self._state.on_shift:
            self._state.begin_shift()

    def _loc_at_odometer(self) -> dict[str, float]:
        if self._cfg.point_interpolator:
            return self._cfg.point_interpolator(self._state.odometer)
        frac = self._state.odometer / self._cfg.total_miles if self._cfg.total_miles else 0
        lat = self._cfg.current.lat + frac * (self._cfg.dropoff.lat - self._cfg.current.lat)
        lon = self._cfg.current.lon + frac * (self._cfg.dropoff.lon - self._cfg.current.lon)
        return {"lat": round(lat, 6), "lon": round(lon, 6)}

    def _name_at_odometer(self) -> str:
        odometer = self._state.odometer
        if odometer <= 0:
            return self._cfg.current.name
        if odometer >= self._cfg.total_miles:
            return self._cfg.dropoff.name
        if abs(odometer - self._cfg.leg1_miles) < 5:
            return self._cfg.pickup.name
        loc = self._loc_at_odometer()
        return f"Mile {odometer:.0f} ({loc['lat']:.2f}, {loc['lon']:.2f})"

    def _add_pre_shift_off_duty(self) -> None:
        """Fill from midnight to shift start as off-duty on the first log sheet."""
        start = self._cfg.start_time
        midnight = start.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=start.tzinfo)
        if start > midnight:
            self._events.append(
                ScheduleEvent(
                    event_type="off_duty",
                    start_time=midnight,
                    end_time=start,
                    location_name=self._cfg.current.name,
                    location_lat=self._cfg.current.lat,
                    location_lon=self._cfg.current.lon,
                    mile_marker=0,
                    description="Off duty before shift",
                )
            )

    def _fill_remainder_of_day(self) -> None:
        """Pad last calendar day to midnight so log totals equal 24 hrs."""
        now = self._state.current_time
        end_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        if now < end_of_day:
            remaining = (end_of_day - now).total_seconds() / 3600
            self._append_event("off_duty", remaining, self._cfg.dropoff.name, "Off duty after trip")

    @staticmethod
    def _event_to_dict(e: ScheduleEvent) -> dict[str, Any]:
        return {
            "event_type": e.event_type,
            "start_time": e.start_time.isoformat(),
            "end_time": e.end_time.isoformat(),
            "location_name": e.location_name,
            "location_lat": e.location_lat,
            "location_lon": e.location_lon,
            "mile_marker": round(e.mile_marker, 1),
            "description": e.description,
            "duration_hours": round(e.duration_hours, 4),
        }


# ── Public entry point ────────────────────────────────────────────────────────


def plan_trip(
    current_to_pickup_miles: float,
    current_to_pickup_hours: float,
    pickup_to_dropoff_miles: float,
    pickup_to_dropoff_hours: float,
    current_cycle_used: float,
    start_time: datetime,
    current_location_name: str,
    current_location_lat: float,
    current_location_lon: float,
    pickup_location_name: str,
    pickup_location_lat: float,
    pickup_location_lon: float,
    dropoff_location_name: str,
    dropoff_location_lat: float,
    dropoff_location_lon: float,
    point_interpolator: Callable[[float], dict[str, float]] | None = None,
) -> dict[str, Any]:
    """Schedule a HOS-compliant trip and return stops, daily logs, and events.

    Thin adapter: builds a ``TripConfig`` and delegates to ``TripScheduler``.
    The flat signature is preserved so ``views.py`` requires no changes.
    """
    config = TripConfig(
        current=LocationPoint(current_location_lat, current_location_lon, current_location_name),
        pickup=LocationPoint(pickup_location_lat, pickup_location_lon, pickup_location_name),
        dropoff=LocationPoint(dropoff_location_lat, dropoff_location_lon, dropoff_location_name),
        leg1_miles=max(current_to_pickup_miles, 0.0),
        leg1_hours=max(current_to_pickup_hours, 0.0),
        leg2_miles=max(pickup_to_dropoff_miles, 0.0),
        leg2_hours=max(pickup_to_dropoff_hours, 0.0),
        cycle_used=current_cycle_used,
        start_time=start_time,
        point_interpolator=point_interpolator,
    )
    return TripScheduler(config).run()


# ── Daily log builder (pure function, no side effects) ───────────────────────

_STATUS_MAP: dict[str, str] = {
    "off_duty": "off_duty",
    "sleeper": "sleeper_berth",
    "driving": "driving",
    "on_duty_nd": "on_duty_not_driving",
}


def _build_daily_logs(
    events: list[ScheduleEvent],
    total_route_miles: float,
    total_route_hours: float,
) -> list[DailyLog]:
    """Pure function: slice events into one DailyLog per calendar day."""
    if not events:
        return []

    tz = events[0].start_time.tzinfo
    first_day = events[0].start_time.date()
    last_day = events[-1].end_time.date()
    avg_speed = total_route_miles / total_route_hours if total_route_hours > 0 else AVG_SPEED_MPH

    logs: list[DailyLog] = []
    current_date = first_day

    while current_date <= last_day:
        log = _build_single_day_log(current_date, tz, events, avg_speed)
        if log.entries:
            logs.append(log)
        current_date += timedelta(days=1)

    return logs


def _build_single_day_log(
    date: Any,
    tz: Any,
    events: list[ScheduleEvent],
    avg_speed: float,
) -> DailyLog:
    """Build one DailyLog for a single calendar day."""
    day_start = datetime(date.year, date.month, date.day, tzinfo=tz)
    day_end = day_start + timedelta(days=1)

    entries: list[dict[str, Any]] = []
    remarks: list[dict[str, str]] = []
    totals = {"off_duty": 0.0, "sleeper_berth": 0.0, "driving": 0.0, "on_duty_not_driving": 0.0}
    day_driving_hours = 0.0
    last_status: str | None = None

    for ev in events:
        if ev.end_time <= day_start or ev.start_time >= day_end:
            continue

        clipped_start = max(ev.start_time, day_start)
        clipped_end = min(ev.end_time, day_end)
        if clipped_start >= clipped_end:
            continue

        status = _STATUS_MAP.get(ev.event_type, "off_duty")
        hours = (clipped_end - clipped_start).total_seconds() / 3600
        start_str = f"{clipped_start.hour:02d}:{clipped_start.minute:02d}"
        end_str = (
            "24:00"
            if clipped_end == day_end
            else f"{clipped_end.hour:02d}:{clipped_end.minute:02d}"
        )

        entries.append(
            {
                "status": status,
                "start": start_str,
                "end": end_str,
                "duration_hours": round(hours, 4),
                "location": ev.location_name,
            }
        )
        totals[status] = totals.get(status, 0.0) + hours

        if status != last_status:
            remarks.append({"time": start_str, "location": ev.location_name, "status": status})
            last_status = status

        if ev.event_type == "driving":
            day_driving_hours += hours

    return DailyLog(
        date=date.isoformat(),
        total_miles=round(day_driving_hours * avg_speed, 1),
        entries=entries,
        remarks=remarks,
        total_hours=totals,
    )
