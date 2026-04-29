"""HOS (Hours of Service) trip-scheduling engine.

Rules implemented (property-carrying CMV, 70 hr / 8 day, no adverse conditions):
    - 11-hour driving limit per shift
    - 14-hour on-duty window per shift (clock starts at first on-duty, off-duty
      does NOT pause it)
    - 30-minute break required after 8 cumulative hours of driving
    - 70-hour / 8-day cycle limit (simplified cumulative bucket)
    - 10 consecutive hours off-duty between shifts
    - 34-hour restart when cycle is exhausted

Assessment-specific:
    - Fuel stop every 1,000 miles (30 min on-duty not driving)
    - 1 hour on-duty not driving at pickup and dropoff
    - Pre-trip inspection: 15 min on-duty not driving
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

# ── HOS constants (49 CFR Part 395) ─────────────────────────────────────────

MAX_DRIVING_BEFORE_BREAK: float = 8.0  # hours before mandatory 30-min break
BREAK_DURATION: float = 0.5  # 30 min
MAX_DRIVING_PER_SHIFT: float = 11.0  # hours per shift
MAX_DUTY_WINDOW: float = 14.0  # consecutive on-duty window hours
OFF_DUTY_REQUIRED: float = 10.0  # minimum off-duty between shifts
CYCLE_LIMIT: float = 70.0  # hours in rolling 8-day cycle
RESTART_DURATION: float = 34.0  # hours off-duty to reset cycle
FUEL_INTERVAL_MILES: float = 1000.0
FUEL_STOP_DURATION: float = 0.5  # hours
PICKUP_DURATION: float = 1.0  # hours
DROPOFF_DURATION: float = 1.0  # hours
PRE_TRIP_DURATION: float = 0.25  # 15 min
AVG_SPEED_MPH: float = 55.0  # fallback speed


# ── Value objects ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LocationPoint:
    """Immutable geographic point with a display name."""

    lat: float
    lon: float
    name: str


@dataclass(frozen=True)
class TripConfig:
    """All inputs needed to schedule a trip. Immutable by design."""

    current: LocationPoint
    pickup: LocationPoint
    dropoff: LocationPoint
    leg1_miles: float
    leg1_hours: float
    leg2_miles: float
    leg2_hours: float
    cycle_used: float
    start_time: datetime
    point_interpolator: Callable[[float], dict[str, float]] | None = None

    @property
    def total_miles(self) -> float:
        return self.leg1_miles + self.leg2_miles

    @property
    def total_hours(self) -> float:
        hrs = self.leg1_hours + self.leg2_hours
        return hrs if hrs > 0 else self.total_miles / AVG_SPEED_MPH

    @property
    def avg_speed_leg1(self) -> float:
        return self.leg1_miles / self.leg1_hours if self.leg1_hours > 0 else AVG_SPEED_MPH

    @property
    def avg_speed_leg2(self) -> float:
        return self.leg2_miles / self.leg2_hours if self.leg2_hours > 0 else AVG_SPEED_MPH


# ── Data transfer objects ─────────────────────────────────────────────────────


@dataclass
class ScheduleEvent:
    event_type: str  # driving | on_duty_nd | off_duty | sleeper
    start_time: datetime
    end_time: datetime
    location_name: str = ""
    location_lat: float = 0.0
    location_lon: float = 0.0
    mile_marker: float = 0.0
    description: str = ""

    @property
    def duration_hours(self) -> float:
        return (self.end_time - self.start_time).total_seconds() / 3600


@dataclass
class Stop:
    stop_type: str  # pickup | dropoff | fuel | rest_30min | rest_10hr | restart_34hr
    location_name: str
    location_lat: float
    location_lon: float
    arrival_time: datetime
    departure_time: datetime
    mile_marker: float

    @property
    def duration_hours(self) -> float:
        return (self.departure_time - self.arrival_time).total_seconds() / 3600

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.stop_type,
            "location": {
                "lat": self.location_lat,
                "lon": self.location_lon,
                "name": self.location_name,
            },
            "arrival_time": self.arrival_time.isoformat(),
            "departure_time": self.departure_time.isoformat(),
            "duration_hours": round(self.duration_hours, 2),
            "mile_marker": round(self.mile_marker, 1),
        }


@dataclass
class DailyLog:
    date: str
    total_miles: float = 0.0
    entries: list[dict[str, Any]] = field(default_factory=list)
    remarks: list[dict[str, str]] = field(default_factory=list)
    total_hours: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "total_miles": round(self.total_miles, 1),
            "entries": self.entries,
            "remarks": self.remarks,
            "total_hours": {k: round(v, 2) for k, v in self.total_hours.items()},
        }


# ── Driver state (encapsulated mutation) ─────────────────────────────────────


@dataclass
class DriverState:
    """Tracks all HOS counters for the driver at any point in time."""

    current_time: datetime
    driving_since_break: float = 0.0
    driving_this_shift: float = 0.0
    duty_window_start: datetime | None = None
    cycle_used: float = 0.0
    miles_since_fuel: float = 0.0
    odometer: float = 0.0
    on_shift: bool = False

    @property
    def duty_window_elapsed(self) -> float:
        if self.duty_window_start is None:
            return 0.0
        return (self.current_time - self.duty_window_start).total_seconds() / 3600

    @property
    def driving_remaining_before_break(self) -> float:
        return max(0.0, MAX_DRIVING_BEFORE_BREAK - self.driving_since_break)

    @property
    def driving_remaining_this_shift(self) -> float:
        return max(0.0, MAX_DRIVING_PER_SHIFT - self.driving_this_shift)

    @property
    def duty_window_remaining(self) -> float:
        return max(0.0, MAX_DUTY_WINDOW - self.duty_window_elapsed)

    @property
    def cycle_remaining(self) -> float:
        return max(0.0, CYCLE_LIMIT - self.cycle_used)

    def max_drivable_hours(self) -> float:
        """Minimum of all active HOS limits expressed in hours."""
        return max(
            0.0,
            min(
                self.driving_remaining_before_break,
                self.driving_remaining_this_shift,
                self.duty_window_remaining,
                self.cycle_remaining,
            ),
        )

    def begin_shift(self) -> None:
        self.duty_window_start = self.current_time
        self.driving_this_shift = 0.0
        self.driving_since_break = 0.0
        self.on_shift = True

    def end_shift(self) -> None:
        self.on_shift = False
        self.duty_window_start = None

    def advance(self, hours: float) -> None:
        self.current_time += timedelta(hours=hours)

    def log_driving(self, hours: float, miles: float) -> None:
        self.driving_since_break += hours
        self.driving_this_shift += hours
        self.cycle_used += hours
        self.odometer += miles
        self.miles_since_fuel += miles

    def log_on_duty(self, hours: float) -> None:
        self.cycle_used += hours

    def reset_break_clock(self) -> None:
        self.driving_since_break = 0.0

    def reset_fuel_clock(self) -> None:
        self.miles_since_fuel = 0.0

    def reset_cycle(self) -> None:
        self.cycle_used = 0.0


# ── Scheduler (Single Responsibility: orchestrates HOS stops) ─────────────────


class TripScheduler:
    """Schedules a trip segment-by-segment, inserting HOS-mandated stops.

    Responsibilities:
        - Track driver state
        - Insert mandatory breaks, rests, fuel stops
        - Record events and stops chronologically

    Does NOT handle:
        - Route geometry or geocoding (route_service.py)
        - API serialization (views.py)
        - Daily log rendering (logDrawing.ts)
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
        """Execute the full trip schedule and return results."""
        self._add_pre_shift_off_duty()
        self._ensure_on_shift()
        self._record_on_duty_event(PRE_TRIP_DURATION, self._cfg.current.name, "Pre-trip inspection")
        self._state.log_on_duty(PRE_TRIP_DURATION)

        if self._cfg.leg1_miles > 0.1:
            self._drive(self._cfg.leg1_miles, self._cfg.avg_speed_leg1)

        self._handle_waypoint(
            stop_type="pickup",
            location=self._cfg.pickup,
            duration=PICKUP_DURATION,
            desc="Loading at pickup",
        )

        if self._cfg.leg2_miles > 0.1:
            self._drive(self._cfg.leg2_miles, self._cfg.avg_speed_leg2)

        self._handle_waypoint(
            stop_type="dropoff",
            location=self._cfg.dropoff,
            duration=DROPOFF_DURATION,
            desc="Unloading at dropoff",
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

    # ── HOS stop actions (Open/Closed: each action is a discrete method) ─────

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

    # ── Event/stop recording helpers ──────────────────────────────────────────

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

    Thin adapter that builds a ``TripConfig`` and delegates to ``TripScheduler``.
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
