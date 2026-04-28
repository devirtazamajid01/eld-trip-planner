"""HOS (Hours of Service) trip-scheduling engine.

Rules implemented (property-carrying CMV, 70 hr / 8 day, no adverse conditions):
    - 11-hour driving limit per shift
    - 14-hour on-duty window per shift (clock starts at first on-duty, off-duty
      does NOT pause it)
    - 30-minute break required after 8 cumulative hours of driving
    - 70-hour / 8-day cycle limit
    - 10 consecutive hours off-duty between shifts
    - 34-hour restart when cycle is exhausted

Assessment-specific:
    - Fuel stop every 1 000 miles (30 min on-duty not driving)
    - 1 hour on-duty not driving at pickup
    - 1 hour on-duty not driving at dropoff
    - Pre-trip inspection: 15 min on-duty not driving
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

# ── Constants ────────────────────────────────────────────────────────────────

MAX_DRIVING_BEFORE_BREAK = 8.0  # hours
BREAK_DURATION = 0.5  # 30 min
MAX_DRIVING_PER_SHIFT = 11.0  # hours
MAX_DUTY_WINDOW = 14.0  # hours
OFF_DUTY_REQUIRED = 10.0  # hours
CYCLE_LIMIT = 70.0  # hours (70-hr / 8-day rule, simplified as cumulative bucket)
RESTART_DURATION = 34.0  # hours (resets 70-hr cycle)
FUEL_INTERVAL_MILES = 1000.0
FUEL_STOP_DURATION = 0.5  # hours
PICKUP_DURATION = 1.0  # hours
DROPOFF_DURATION = 1.0  # hours
PRE_TRIP_DURATION = 0.25  # 15 min
AVG_SPEED_MPH = 55.0  # fallback when we don't have precise step data


# ── Data classes ─────────────────────────────────────────────────────────────


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
    date: str  # YYYY-MM-DD
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


# ── Driver state tracker ────────────────────────────────────────────────────


@dataclass
class DriverState:
    current_time: datetime
    driving_since_break: float = 0.0
    driving_this_shift: float = 0.0
    duty_window_start: datetime | None = None
    cycle_used: float = 0.0
    miles_since_fuel: float = 0.0
    total_miles: float = 0.0
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
        return max(
            0.0,
            min(
                self.driving_remaining_before_break,
                self.driving_remaining_this_shift,
                self.duty_window_remaining,
                self.cycle_remaining,
            ),
        )

    def start_shift(self) -> None:
        self.duty_window_start = self.current_time
        self.driving_this_shift = 0.0
        self.driving_since_break = 0.0
        self.on_shift = True

    def end_shift(self) -> None:
        self.on_shift = False
        self.duty_window_start = None


# ── Main scheduler ───────────────────────────────────────────────────────────


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
    point_interpolator=None,
) -> dict[str, Any]:
    """Schedule the full trip respecting all HOS constraints."""

    total_route_miles = current_to_pickup_miles + pickup_to_dropoff_miles
    if total_route_miles <= 0:
        total_route_miles = 1.0

    avg_speed_leg1 = (
        current_to_pickup_miles / current_to_pickup_hours
        if current_to_pickup_hours > 0
        else AVG_SPEED_MPH
    )
    avg_speed_leg2 = (
        pickup_to_dropoff_miles / pickup_to_dropoff_hours
        if pickup_to_dropoff_hours > 0
        else AVG_SPEED_MPH
    )

    state = DriverState(
        current_time=start_time,
        cycle_used=min(current_cycle_used, CYCLE_LIMIT),
    )

    events: list[ScheduleEvent] = []
    stops: list[Stop] = []

    def _loc_at_mile(mile: float) -> dict[str, Any]:
        if point_interpolator:
            return point_interpolator(mile)
        frac = mile / total_route_miles if total_route_miles else 0
        lat = current_location_lat + frac * (dropoff_location_lat - current_location_lat)
        lon = current_location_lon + frac * (dropoff_location_lon - current_location_lon)
        return {"lat": round(lat, 6), "lon": round(lon, 6)}

    def _name_at_mile(mile: float) -> str:
        if mile <= 0:
            return current_location_name
        if mile >= total_route_miles:
            return dropoff_location_name
        if abs(mile - current_to_pickup_miles) < 5:
            return pickup_location_name
        loc = _loc_at_mile(mile)
        return f"Mile {mile:.0f} ({loc['lat']:.2f}, {loc['lon']:.2f})"

    def _avg_speed_at_mile(mile: float) -> float:
        return avg_speed_leg1 if mile < current_to_pickup_miles else avg_speed_leg2

    def _add_event(
        etype: str, duration_hrs: float, name: str = "", desc: str = ""
    ) -> ScheduleEvent:
        loc = _loc_at_mile(state.total_miles)
        ev = ScheduleEvent(
            event_type=etype,
            start_time=state.current_time,
            end_time=state.current_time + timedelta(hours=duration_hrs),
            location_name=name or _name_at_mile(state.total_miles),
            location_lat=loc["lat"],
            location_lon=loc["lon"],
            mile_marker=state.total_miles,
            description=desc,
        )
        events.append(ev)
        state.current_time = ev.end_time
        return ev

    def _ensure_on_shift() -> None:
        if not state.on_shift:
            state.start_shift()

    def _add_stop(stop_type: str, event_type: str, duration_hrs: float, desc: str) -> None:
        """Create an event + stop entry at the current location. DRY helper."""
        loc = _loc_at_mile(state.total_miles)
        name = _name_at_mile(state.total_miles)
        arrival = state.current_time
        _add_event(event_type, duration_hrs, name=name, desc=desc)
        stops.append(
            Stop(
                stop_type=stop_type,
                location_name=name,
                location_lat=loc["lat"],
                location_lon=loc["lon"],
                arrival_time=arrival,
                departure_time=state.current_time,
                mile_marker=state.total_miles,
            )
        )

    def _take_rest(duration_hrs: float, stop_type: str, desc: str) -> None:
        state.end_shift()
        _add_stop(stop_type, "off_duty", duration_hrs, desc)

    def _take_30min_break() -> None:
        _add_stop("rest_30min", "off_duty", BREAK_DURATION, "30-min rest break")
        state.driving_since_break = 0.0

    def _take_fuel_stop() -> None:
        _add_stop("fuel", "on_duty_nd", FUEL_STOP_DURATION, "Fuel stop")
        state.cycle_used += FUEL_STOP_DURATION
        state.miles_since_fuel = 0.0

    def _take_10hr_rest() -> None:
        _take_rest(OFF_DUTY_REQUIRED, "rest_10hr", "10-hr off-duty rest")
        state.start_shift()

    def _take_34hr_restart() -> None:
        _take_rest(RESTART_DURATION, "restart_34hr", "34-hr restart (cycle reset)")
        state.cycle_used = 0.0
        state.start_shift()

    def _check_cycle_restart() -> None:
        if state.cycle_remaining <= 0.5:
            _take_34hr_restart()

    def _drive_miles(miles_to_drive: float) -> None:
        """Drive a chunk, inserting mandatory stops as needed."""
        remaining = miles_to_drive

        while remaining > 0.01:
            _ensure_on_shift()

            speed = _avg_speed_at_mile(state.total_miles)
            if speed <= 0:
                speed = AVG_SPEED_MPH

            if state.cycle_remaining < 0.5:
                _take_34hr_restart()
                continue

            if state.driving_remaining_this_shift < 0.1 or state.duty_window_remaining < 0.1:
                _take_10hr_rest()
                continue

            max_drive_hrs = state.max_drivable_hours()
            max_drive_miles_by_hos = max_drive_hrs * speed

            miles_until_fuel = FUEL_INTERVAL_MILES - state.miles_since_fuel
            if miles_until_fuel <= 0:
                miles_until_fuel = FUEL_INTERVAL_MILES

            drivable_miles = min(remaining, max_drive_miles_by_hos, miles_until_fuel)

            if drivable_miles < 0.1:
                if state.driving_remaining_before_break < 0.1:
                    _take_30min_break()
                elif state.driving_remaining_this_shift < 0.1 or state.duty_window_remaining < 0.1:
                    _take_10hr_rest()
                elif state.cycle_remaining < 0.5:
                    _take_34hr_restart()
                continue

            drive_hours = drivable_miles / speed
            name = _name_at_mile(state.total_miles)
            _add_event("driving", drive_hours, name=name, desc="Driving")

            state.driving_since_break += drive_hours
            state.driving_this_shift += drive_hours
            state.cycle_used += drive_hours
            state.total_miles += drivable_miles
            state.miles_since_fuel += drivable_miles
            remaining -= drivable_miles

            if state.miles_since_fuel >= FUEL_INTERVAL_MILES - 0.1 and remaining > 0.1:
                _take_fuel_stop()

            if state.driving_since_break >= MAX_DRIVING_BEFORE_BREAK - 0.01 and remaining > 0.1:
                _take_30min_break()

        # After finishing a driving leg, if 8hr break clock is at limit, take break
        # before any subsequent on-duty work (pickup/dropoff)
        if state.driving_since_break >= MAX_DRIVING_BEFORE_BREAK - 0.01:
            _take_30min_break()

    # ── Off-duty time before trip starts (fill from midnight) ────────────
    midnight = start_time.replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=start_time.tzinfo
    )
    if start_time > midnight:
        events.append(
            ScheduleEvent(
                event_type="off_duty",
                start_time=midnight,
                end_time=start_time,
                location_name=current_location_name,
                location_lat=current_location_lat,
                location_lon=current_location_lon,
                mile_marker=0,
                description="Off duty before shift",
            )
        )

    # ── Pre-trip inspection ──────────────────────────────────────────────
    _ensure_on_shift()
    _add_event(
        "on_duty_nd", PRE_TRIP_DURATION, name=current_location_name, desc="Pre-trip inspection"
    )
    state.cycle_used += PRE_TRIP_DURATION

    # ── Drive to pickup ──────────────────────────────────────────────────
    if current_to_pickup_miles > 0.1:
        _drive_miles(current_to_pickup_miles)

    # ── Pickup ───────────────────────────────────────────────────────────
    _ensure_on_shift()
    _check_cycle_restart()
    if state.duty_window_remaining < PICKUP_DURATION + 0.5:
        _take_10hr_rest()
    arrival = state.current_time
    _add_event("on_duty_nd", PICKUP_DURATION, name=pickup_location_name, desc="Loading at pickup")
    state.cycle_used += PICKUP_DURATION
    # Pickup is on-duty, NOT off-duty — does not reset the 30-min break clock
    stops.append(
        Stop(
            stop_type="pickup",
            location_name=pickup_location_name,
            location_lat=pickup_location_lat,
            location_lon=pickup_location_lon,
            arrival_time=arrival,
            departure_time=state.current_time,
            mile_marker=state.total_miles,
        )
    )

    # ── Drive to dropoff ─────────────────────────────────────────────────
    if pickup_to_dropoff_miles > 0.1:
        _drive_miles(pickup_to_dropoff_miles)

    # ── Dropoff ──────────────────────────────────────────────────────────
    _ensure_on_shift()
    _check_cycle_restart()
    if state.duty_window_remaining < DROPOFF_DURATION + 0.1:
        _take_10hr_rest()
    arrival = state.current_time
    _add_event(
        "on_duty_nd", DROPOFF_DURATION, name=dropoff_location_name, desc="Unloading at dropoff"
    )
    state.cycle_used += DROPOFF_DURATION
    stops.append(
        Stop(
            stop_type="dropoff",
            location_name=dropoff_location_name,
            location_lat=dropoff_location_lat,
            location_lon=dropoff_location_lon,
            arrival_time=arrival,
            departure_time=state.current_time,
            mile_marker=state.total_miles,
        )
    )

    # ── Fill remaining day as off-duty ───────────────────────────────────
    end_of_day = state.current_time.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
        days=1
    )
    if state.current_time < end_of_day:
        _add_event(
            "off_duty",
            (end_of_day - state.current_time).total_seconds() / 3600,
            name=dropoff_location_name,
            desc="Off duty after trip",
        )

    # ── Build daily logs ─────────────────────────────────────────────────
    total_route_hours = current_to_pickup_hours + pickup_to_dropoff_hours
    if total_route_hours <= 0:
        total_route_hours = total_route_miles / AVG_SPEED_MPH
    daily_logs = _build_daily_logs(events, total_route_miles, total_route_hours)

    return {
        "stops": [s.to_dict() for s in stops],
        "daily_logs": [dl.to_dict() for dl in daily_logs],
        "events": [
            {
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
            for e in events
        ],
    }


# ── Daily log builder ────────────────────────────────────────────────────────

STATUS_MAP = {
    "off_duty": "off_duty",
    "sleeper": "sleeper_berth",
    "driving": "driving",
    "on_duty_nd": "on_duty_not_driving",
}


def _build_daily_logs(
    events: list[ScheduleEvent],
    total_route_miles: float = 0,
    total_route_hours: float = 0,
) -> list[DailyLog]:
    """Slice events into calendar-day log sheets."""
    if not events:
        return []

    first_day = events[0].start_time.date()
    last_day = events[-1].end_time.date()

    logs: list[DailyLog] = []
    current_date = first_day

    while current_date <= last_day:
        tz = events[0].start_time.tzinfo
        day_start = datetime(current_date.year, current_date.month, current_date.day, tzinfo=tz)
        day_end = day_start + timedelta(days=1)

        entries: list[dict[str, Any]] = []
        remarks: list[dict[str, str]] = []
        totals = {"off_duty": 0.0, "sleeper_berth": 0.0, "driving": 0.0, "on_duty_not_driving": 0.0}
        day_driving_hours = 0.0
        last_status = None

        for ev in events:
            if ev.end_time <= day_start or ev.start_time >= day_end:
                continue

            clipped_start = max(ev.start_time, day_start)
            clipped_end = min(ev.end_time, day_end)

            if clipped_start >= clipped_end:
                continue

            status = STATUS_MAP.get(ev.event_type, "off_duty")
            hours = (clipped_end - clipped_start).total_seconds() / 3600

            start_str = f"{clipped_start.hour:02d}:{clipped_start.minute:02d}"
            end_str = f"{clipped_end.hour:02d}:{clipped_end.minute:02d}"
            if clipped_end == day_end:
                end_str = "24:00"

            entries.append(
                {
                    "status": status,
                    "start": start_str,
                    "end": end_str,
                    "duration_hours": round(hours, 4),
                    "location": ev.location_name,
                }
            )

            totals[status] = totals.get(status, 0) + hours

            if status != last_status:
                remarks.append(
                    {
                        "time": start_str,
                        "location": ev.location_name,
                        "status": status,
                    }
                )
                last_status = status

            if ev.event_type == "driving":
                day_driving_hours += hours

        avg_speed = total_route_miles / total_route_hours if total_route_hours > 0 else 55.0
        day_miles = day_driving_hours * avg_speed

        log = DailyLog(
            date=current_date.isoformat(),
            total_miles=round(day_miles, 1),
            entries=entries,
            remarks=remarks,
            total_hours=totals,
        )
        if entries:
            logs.append(log)
        current_date += timedelta(days=1)

    return logs
