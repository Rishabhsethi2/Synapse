from enum import Enum
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class PredictionMode(str, Enum):
    """Execution mode for predictions."""
    LIVE = "LIVE"
    REPLAY = "REPLAY"
    SIMULATION = "SIMULATION"
    FALLBACK = "FALLBACK"


class DataQuality(str, Enum):
    """Quality of data used for prediction."""
    FULL = "FULL"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    FALLBACK = "FALLBACK"


class StabilityState(str, Enum):
    """Stability of ETA forecast."""
    STABLE = "STABLE"
    SETTLING = "SETTLING"
    VOLATILE = "VOLATILE"


class EventType(str, Enum):
    """Types of operational events."""
    TSR = "TSR"
    BLOCK = "BLOCK"
    UNSCHEDULED_STOP = "UNSCHEDULED_STOP"
    SIGNAL = "SIGNAL"
    WEATHER = "WEATHER"
    CONGESTION = "CONGESTION"
    OTHER = "OTHER"


class Direction(str, Enum):
    """Direction of contribution to delay."""
    INCREASING_DELAY = "INCREASING_DELAY"
    DECREASING_DELAY = "DECREASING_DELAY"
    NEUTRAL = "NEUTRAL"


class Station(BaseModel):
    """Railway station entity."""
    code: str = Field(..., description="Station code (e.g. NDLS)")
    full_name: str = Field(..., description="Station full name")
    zone: str = Field(..., description="Railway zone")
    latitude: float | None = Field(None, description="Station latitude")
    longitude: float | None = Field(None, description="Station longitude")
    address: str | None = Field(None, description="Station address")


class RailwaySection(BaseModel):
    """A segment of track between two stations."""
    from_station: str = Field(..., description="Starting station code")
    to_station: str = Field(..., description="Ending station code")
    distance_km: float = Field(..., description="Distance in kilometers")
    typical_running_time_minutes: float | None = Field(None, description="Typical running time in minutes")


class ScheduleStop(BaseModel):
    """A scheduled stop for a train."""
    station_no: int = Field(..., description="Sequence number of the station in the route")
    station_code: str = Field(..., description="Station code")
    arrival_day: int = Field(..., description="Day of arrival (1-indexed)")
    arrival_time: str | None = Field(None, description="Scheduled arrival time (HH:MM:SS)")
    departure_day: int = Field(..., description="Day of departure (1-indexed)")
    departure_time: str | None = Field(None, description="Scheduled departure time (HH:MM:SS)")
    distance_from_origin_km: float = Field(..., description="Cumulative distance from origin in km")


class Route(BaseModel):
    """The route of a train, represented as a sequence of scheduled stops."""
    train_no: str = Field(..., description="Train number")
    stops: list[ScheduleStop] = Field(..., description="Sequence of scheduled stops")


class Train(BaseModel):
    """A railway train entity."""
    train_no: str = Field(..., description="Train number")
    train_name: str = Field(..., description="Train name")
    type_code: str = Field(..., description="Train type code (e.g. RAJDHANI, SHATABDI)")


class TrainState(BaseModel):
    """Current state of a running train."""
    train_id: str = Field(..., description="Train ID/Number")
    timestamp: datetime = Field(..., description="Timestamp of the state observation (Asia/Kolkata)")
    current_station_index: int = Field(..., description="Index of the current or last passed station")
    current_station_code: str = Field(..., description="Code of the current or last passed station")
    current_delay_minutes: float = Field(..., description="Current delay in minutes")
    speed: float | None = Field(None, description="Current speed in km/h")
    data_freshness_seconds: float = Field(..., description="Freshness of the data in seconds")
    source: str = Field(..., description="Data source: LIVE/REPLAY/SIMULATED")
    source_timestamp: datetime = Field(..., description="Timestamp from the source (Asia/Kolkata)")


class NetworkState(BaseModel):
    """Current state of a railway section."""
    timestamp: datetime = Field(..., description="Timestamp of the network state (Asia/Kolkata)")
    section_id: str = Field(..., description="Identifier for the railway section")
    occupying_train_ids: list[str] = Field(default_factory=list, description="Trains currently occupying the section")
    preceding_train_id: str | None = Field(None, description="Train immediately preceding in the section")
    following_train_ids: list[str] = Field(default_factory=list, description="Trains following in the section")
    headway_minutes: float | None = Field(None, description="Headway between trains in minutes")
    congestion_score: float | None = Field(None, description="Congestion score (e.g., 0.0 to 1.0)")
    data_freshness_seconds: float = Field(..., description="Freshness of the state data in seconds")


class HistoricalObservation(BaseModel):
    """Historical running data for a train at a station."""
    train_no: str = Field(..., description="Train number")
    date: str = Field(..., description="Date of operation (YYYY-MM-DD)")
    station_code: str = Field(..., description="Station code")
    station_no: int = Field(..., description="Sequence number of the station")
    scheduled_arrival: datetime | None = Field(None, description="Scheduled arrival datetime")
    actual_arrival: datetime | None = Field(None, description="Actual arrival datetime")
    delay_minutes: float | None = Field(None, description="Delay in minutes at arrival/departure")
    scheduled_departure: datetime | None = Field(None, description="Scheduled departure datetime")
    actual_departure: datetime | None = Field(None, description="Actual departure datetime")


class WeatherObservation(BaseModel):
    """Weather condition at a specific station."""
    station_code: str = Field(..., description="Station code")
    timestamp: datetime = Field(..., description="Observation timestamp (Asia/Kolkata)")
    temperature_c: float | None = Field(None, description="Temperature in Celsius")
    rainfall_mm: float | None = Field(None, description="Rainfall in mm")
    visibility_km: float | None = Field(None, description="Visibility in kilometers")
    weather_code: str | None = Field(None, description="Weather condition code")
    is_severe: bool | None = Field(None, description="Indicates if the weather is severe")


class OperationalEvent(BaseModel):
    """Operational event affecting railway operations (TSR, blocks, etc.)."""
    event_id: str = Field(..., description="Unique event identifier")
    event_type: EventType = Field(..., description="Type of the operational event")
    section_id: str | None = Field(None, description="Affected railway section, if applicable")
    station_code: str | None = Field(None, description="Affected station, if applicable")
    start_time: datetime = Field(..., description="Event start time (Asia/Kolkata)")
    end_time: datetime | None = Field(None, description="Event end time (Asia/Kolkata)")
    description: str = Field(..., description="Detailed description of the event")
    severity: str = Field(..., description="Severity level of the event")


class Prediction(BaseModel):
    """ETA Prediction for a train at a future station."""
    train_id: str = Field(..., description="Train ID/Number")
    generated_at: datetime = Field(..., description="When the prediction was generated (Asia/Kolkata)")
    model_version: str = Field(..., description="Model version used for prediction")
    station_code: str = Field(..., description="Target station code")
    station_no: int = Field(..., description="Sequence number of the target station")
    predicted_arrival: datetime = Field(..., description="Predicted ETA (Asia/Kolkata)")
    predicted_delay_minutes: float = Field(..., description="Predicted delay in minutes")
    lower_bound: datetime | None = Field(None, description="Lower bound of ETA (Asia/Kolkata)")
    upper_bound: datetime | None = Field(None, description="Upper bound of ETA (Asia/Kolkata)")
    prediction_interval_minutes: float | None = Field(None, description="Size of the prediction interval in minutes")
    data_quality: DataQuality = Field(..., description="Quality of data at time of prediction")
    prediction_mode: PredictionMode = Field(..., description="Execution mode of the prediction")


class PredictionRevision(BaseModel):
    """Revision history for an ETA prediction."""
    train_id: str = Field(..., description="Train ID/Number")
    station_code: str = Field(..., description="Target station code")
    timestamp: datetime = Field(..., description="Time of the revision (Asia/Kolkata)")
    previous_eta: datetime = Field(..., description="Previous ETA (Asia/Kolkata)")
    new_eta: datetime = Field(..., description="New ETA (Asia/Kolkata)")
    change_minutes: float = Field(..., description="Change in ETA in minutes")
    contributing_factors: list[str] = Field(default_factory=list, description="Factors that caused the revision")
    model_version: str = Field(..., description="Model version used")


class AttributionFactor(BaseModel):
    """A single factor contributing to predicted delay."""
    name: str = Field(..., description="Name of the feature/factor")
    contribution_minutes: float = Field(..., description="Contribution to delay in minutes")
    direction: Direction = Field(..., description="Direction of the contribution")
    methodology: str = Field("MODEL_FEATURE_CONTRIBUTION", description="Methodology used to calculate contribution")


class Attribution(BaseModel):
    """Attribution of predicted delay to various factors."""
    train_id: str = Field(..., description="Train ID/Number")
    station_code: str = Field(..., description="Target station code")
    generated_at: datetime = Field(..., description="When the attribution was generated (Asia/Kolkata)")
    factors: list[AttributionFactor] = Field(default_factory=list, description="List of contributing factors")


class WhatIfScenario(BaseModel):
    """A What-If scenario simulating different operational conditions."""
    scenario_id: str = Field(..., description="Scenario identifier")
    train_id: str = Field(..., description="Target train ID")
    created_at: datetime = Field(..., description="Creation time of the scenario (Asia/Kolkata)")
    modifications: dict[str, Any] = Field(default_factory=dict, description="Simulated modifications (e.g. TSR introduced)")
    baseline_prediction: dict[str, Any] = Field(default_factory=dict, description="Original prediction")
    counterfactual_prediction: dict[str, Any] = Field(default_factory=dict, description="Prediction under modifications")
    delta_minutes: dict[str, float] = Field(default_factory=dict, description="Difference in delays (counterfactual - baseline)")
    methodology: str = Field(..., description="Methodology used for counterfactual analysis")


class RiskAssessment(BaseModel):
    """Assessment of operational risks on a section."""
    section_id: str = Field(..., description="Railway section identifier")
    generated_at: datetime = Field(..., description="Time of assessment (Asia/Kolkata)")
    risk_score: float = Field(..., description="Overall risk score")
    expected_marginal_delay: float = Field(..., description="Expected additional delay")
    uncertainty_growth: float = Field(..., description="Growth in uncertainty over the section")
    congestion_factor: float = Field(..., description="Multiplier for congestion impact")
    historical_volatility: float = Field(..., description="Historical volatility on this section")
    contributing_factors: list[str] = Field(default_factory=list, description="Factors contributing to the risk")


class DataQualityState(BaseModel):
    """State of input data quality for predictions."""
    train_id: str = Field(..., description="Target train ID")
    last_update: datetime = Field(..., description="Last update time (Asia/Kolkata)")
    stale_inputs: list[str] = Field(default_factory=list, description="Inputs that are stale")
    fresh_inputs: list[str] = Field(default_factory=list, description="Inputs that are fresh")
    live_features: list[str] = Field(default_factory=list, description="Features using live data")
    fallback_features: list[str] = Field(default_factory=list, description="Features using fallback/imputed data")
    model_version: str = Field(..., description="Model version")
    data_mode: str = Field(..., description="Data mode: LIVE/REPLAY/SIMULATED")


class ForecastStability(BaseModel):
    """Stability metrics of recent ETA predictions."""
    train_id: str = Field(..., description="Target train ID")
    station_code: str = Field(..., description="Target station code")
    recent_revisions: list[PredictionRevision] = Field(default_factory=list, description="Recent prediction revisions")
    stability_index: StabilityState = Field(..., description="Current stability state")
    variance_minutes: float = Field(..., description="Variance of recent predictions in minutes")


class FeederSyncWindow(BaseModel):
    """Synchronization window for feeder connecting trains."""
    train_id: str = Field(..., description="Target train ID")
    destination_station: str = Field(..., description="Connecting station code")
    eta_point: datetime = Field(..., description="Point ETA estimate (Asia/Kolkata)")
    window_start: datetime = Field(..., description="Start of the sync window (Asia/Kolkata)")
    window_end: datetime = Field(..., description="End of the sync window (Asia/Kolkata)")
    confidence_methodology: str = Field(..., description="Methodology used to calculate the window")
