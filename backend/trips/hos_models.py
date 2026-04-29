"""Domain models and value objects for HOS trip scheduling.

These are intentionally separated from the engine logic because:
  - Models are stable; engine logic changes more frequently
  - Models can be imported and tested independently
  - Keeps each file at a manageable, readable size
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

# ── HOS constants ─────────────────────────────────────────

MAX_DRIVING_BEFORE_BREAK: float = 8.0  # hours before mandatory 30-min break
BREAK_DURATION: float = 0.5  # 30 min
MAX_DRIVING_PER_SHIFT: float = 11.0  # hours per shift
MAX_DUTY_WINDOW: float = 14.0  # consecutive on-duty window hours
OFF_DUTY_REQUIRED: float = 10.0  # minimum off-duty between shifts
CYCLE_LIMIT: float = 70.0  # hours in rolling 8-day cycle (simplified cumulative)
RESTART_DURATION: float = 34.0  # hours off-duty to reset cycle
FUEL_INTERVAL_MILES: float = 1000.0
FUEL_STOP_DURATION: float = 0.5  # hours
PICKUP_DURATION: float = 1.0  # hours
DROPOFF_DURATION: float = 1.0  # hours
PRE_TRIP_DURATION: float = 0.25  # 15 min
AVG_SPEED_MPH: float = 55.0  # fallback speed


# ── Value objects (immutable inputs) ─────────────────────────────────────────


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


# ── Data transfer objects (mutable records) ───────────────────────────────────


@dataclass
class ScheduleEvent:
    """A single time-bounded activity in the driver's schedule."""

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
    """A named stop along the route with arrival/departure times."""

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
    """One calendar day's ELD log sheet data."""

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


# ── Driver state (encapsulated mutable counters) ──────────────────────────────


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
