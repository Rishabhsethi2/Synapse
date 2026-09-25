"use client";

import { useState, useCallback } from "react";

// Routed through Next.js so the browser never needs to know Docker's internal host.
const API = "";
const NAVY = "#0f1f3d";
const NAVY_LIGHT = "#1a3460";

/* ── Types ─────────────────────────────────────────────────── */
interface Weather { condition: string; temperature_c: number; rainfall_mm: number; visibility_km: number; severity: { severity_score: number; severity_level: string; factors: string[] } }
interface Section { terrain: string; track: string; tunnels: number; bridges: number; speed_limit: number }
interface Explanation { contribution_minutes: number; direction: string; icon: string; description: string }
interface StationPred { station_code: string; station_name: string; station_no: number; distance_km: number; scheduled_arrival: string | null; predicted_delay: number; lower_bound: number; upper_bound: number; explanations: Explanation[]; weather?: Weather; section?: Section; status: string }
interface OtherTrain { train_no: string; train_name: string; current_station: string; delay: number }
interface LiveStatus { train_no: string; train_name: string; source: string; source_name: string; destination: string; destination_name: string; current_station: string; current_station_name: string; delay: number; distance_from_source: number; total_distance: number; status_as_of: string; is_corridor: boolean }
interface TrackResult { live: LiveStatus; predictions: StationPred[]; passed_stations: StationPred[]; weather_source: string; other_trains: OtherTrain[]; methodology: string; total_stations: number; stations_passed: number; stations_remaining: number }

/* ── Design tokens ─────────────────────────────────────────── */
const delay = (d: number) => {
  if (d > 30) return { text: "#b91c1c", bg: "#fff1f2", border: "#fecaca", dot: "#ef4444", badge: "#fee2e2", label: "Heavily delayed" };
  if (d > 15) return { text: "#b45309", bg: "#fffbeb", border: "#fde68a", dot: "#f59e0b", badge: "#fef3c7", label: "Delayed" };
  if (d > 5)  return { text: "#a16207", bg: "#fefce8", border: "#fef08a", dot: "#eab308", badge: "#fefce8", label: "Slightly late" };
  return { text: "#047857", bg: "#f0fdf4", border: "#bbf7d0", dot: "#10b981", badge: "#dcfce7", label: "On time" };
};

/* ── SVG icons ─────────────────────────────────────────────── */
const ICON_MAP: Record<string, string> = {
  rain: "🌧️", fog: "🌫️", cloud: "☁️", train: "🚄",
  mountain: "⛰️", track: "🛤️", tunnel: "🚇", bridge: "🌉",
  clock: "🕒", star: "⭐", speed: "⚡", info: "📊",
};

function SearchIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>;
}
function ArrowIcon() {
  return <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>;
}
function ChevronIcon({ open }: { open: boolean }) {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}><path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7"/></svg>;
}
function SpinnerIcon() {
  return <svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.37 0 0 5.37 0 12h4z"/></svg>;
}

/* ── Train illustration ────────────────────────────────────── */
function TrainIllustration() {
  return (
    <svg width="220" height="72" viewBox="0 0 220 72" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
      {/* Rails */}
      <line x1="0" y1="62" x2="220" y2="62" stroke="#cbd5e1" strokeWidth="1.5"/>
      <line x1="0" y1="68" x2="220" y2="68" strokeWidth="1.5" stroke="#cbd5e1"/>
      {[0,20,40,60,80,100,120,140,160,180,200].map(x => (
        <line key={x} x1={x+8} y1="62" x2={x+8} y2="68" stroke="#cbd5e1" strokeWidth="1"/>
      ))}
      {/* Train body */}
      <rect x="28" y="22" width="120" height="36" rx="7" fill={NAVY} />
      <rect x="28" y="22" width="120" height="36" rx="7" fill="url(#navyGrad)" />
      {/* Windows */}
      {[40, 62, 84, 106, 124].map((x, i) => (
        <rect key={i} x={x} y="30" width={i === 4 ? 10 : 14} height="10" rx="2" fill="#334d7a" stroke="#4a6fa5" strokeWidth="0.5"/>
      ))}
      {/* Front nose */}
      <path d="M148 24 L166 33 L166 47 L148 56 Z" fill={NAVY_LIGHT} rx="2"/>
      <rect x="158" y="35" width="6" height="6" rx="1" fill="#7ea8d8" opacity="0.9"/>
      {/* Headlight */}
      <circle cx="167" cy="38" r="3" fill="#fbbf24" opacity="0.95"/>
      {/* Wheels */}
      {[50, 80, 110, 140].map(cx => (
        <g key={cx}>
          <circle cx={cx} cy="62" r="6" fill="#1e3a5f" stroke="#334d7a" strokeWidth="1"/>
          <circle cx={cx} cy="62" r="2.5" fill="#4a6fa5"/>
        </g>
      ))}
      {/* Speed lines */}
      {[16, 22, 28].map((y, i) => (
        <line key={i} x1={20 - i * 4} y1={y} x2={28 - i * 4} y2={y} stroke="#93c5fd" strokeWidth="1.2" opacity={0.6 - i * 0.15}/>
      ))}
      <defs>
        <linearGradient id="navyGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1a3460"/>
          <stop offset="100%" stopColor="#0f1f3d"/>
        </linearGradient>
      </defs>
    </svg>
  );
}

/* ── Helpers ─────────────────────────────────────────────── */
function getTodayIST(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" }); // YYYY-MM-DD
}

function dateToStartDay(dateStr: string): number {
  // IRCTC API: startDay=0 means train started today, 1=yesterday, 2=day before
  const chosen = new Date(dateStr);
  const today = new Date(getTodayIST());
  const diffMs = today.getTime() - chosen.getTime();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));
  return Math.max(0, Math.min(2, diffDays)); // clamp 0-2
}

function apiErrorMessage(status: number, payload: unknown): string {
  const detail = typeof payload === "object" && payload !== null && "detail" in payload
    ? String(payload.detail)
    : "Could not track this train right now.";
  if (status === 503 && detail.toLowerCase().includes("quota")) {
    return "Live status service quota is currently unavailable. Please try again later.";
  }
  return detail;
}

/* ── Main ───────────────────────────────────────────────────── */
export default function TrackTrainPage() {
  const [trainNo, setTrainNo] = useState("");
  const [trackDate, setTrackDate] = useState(getTodayIST());
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TrackResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  const handleTrack = useCallback(async () => {
    const no = trainNo.trim();
    if (!/^\d{5}$/.test(no)) {
      setError("Enter a valid 5-digit train number, for example 10103.");
      return;
    }
    setLoading(true); setError(null); setResult(null); setExpandedIdx(null);
    const startDay = dateToStartDay(trackDate);
    try {
      const res = await fetch(`${API}/api/corridor/track`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ train_no: no, start_day: startDay }),
      });
      if (res.ok) {
        setResult(await res.json());
      } else {
        const err: unknown = await res.json().catch(() => null);
        if (res.status === 404) {
          setError(`Train ${no} was not found running on ${trackDate}. If this train runs only on specific days, try a different date.`);
        } else {
          setError(apiErrorMessage(res.status, err));
        }
      }
    } catch {
      setError("Cannot reach the backend server. Make sure it is running on port 8000.");
    }
    setLoading(false);
  }, [trainNo, trackDate]);


  const pct = result ? Math.round((result.live.distance_from_source / (result.live.total_distance || 1)) * 100) : 0;
  const d = result ? delay(result.live.delay) : null;

  return (
    <div className="space-y-6 pb-20">

      {/* ── Hero ─────────────────────────────── */}
      <div className="rounded-2xl overflow-hidden relative" style={{ background: `linear-gradient(135deg, ${NAVY} 0%, ${NAVY_LIGHT} 100%)` }}>
        {/* Subtle dot grid */}
        <div className="absolute inset-0 opacity-[0.07] pointer-events-none" style={{
          backgroundImage: "radial-gradient(circle, white 1px, transparent 1px)",
          backgroundSize: "24px 24px",
        }}/>
        <div className="relative z-10 px-10 pt-10 pb-7 flex items-end justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-widest mb-3" style={{ color: "#7ea8d8" }}>
              Live Delay Intelligence
            </p>
            <h1 className="text-4xl font-bold text-white leading-tight">
              Track any train.<br />
              <span style={{ color: "#93c5fd" }}>Predict every stop.</span>
            </h1>
            <p className="text-base mt-4 max-w-md leading-relaxed" style={{ color: "#b4c4dd" }}>
              Real-time status from IRCTC, ML-powered delay forecasts, live weather and SHAP explanations.
            </p>
          </div>
          <div className="hidden md:block opacity-90 pb-2">
            <TrainIllustration />
          </div>
        </div>

        {/* Search bar — inside hero */}
        <div className="relative z-10 px-10 pb-10">
          <div className="flex gap-3 max-w-2xl">
            <div className="relative flex-1">
              <div className="absolute left-4 top-1/2 -translate-y-1/2" style={{ color: "#94a3b8" }}>
                <SearchIcon />
              </div>
              <input
                type="text"
                value={trainNo}
                onChange={e => setTrainNo(e.target.value.replace(/\D/g, "").slice(0, 5))}
                onKeyDown={e => e.key === "Enter" && handleTrack()}
                placeholder="Train number — e.g. 10103"
                inputMode="numeric"
                maxLength={5}
                aria-label="Five-digit train number"
                className="w-full pl-11 pr-4 py-4 rounded-xl text-base font-medium outline-none transition-all"
                style={{
                  background: "rgba(255,255,255,0.1)",
                  border: "1px solid rgba(255,255,255,0.2)",
                  color: "white",
                  backdropFilter: "blur(8px)",
                }}
                onFocus={e => { e.target.style.background = "rgba(255,255,255,0.18)"; e.target.style.borderColor = "rgba(255,255,255,0.4)"; }}
                onBlur={e => { e.target.style.background = "rgba(255,255,255,0.1)"; e.target.style.borderColor = "rgba(255,255,255,0.2)"; }}
              />
            </div>
            {/* Date picker */}
            <input
              type="date"
              value={trackDate}
              max={getTodayIST()}
              min={(() => { const d = new Date(); d.setDate(d.getDate() - 2); return d.toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" }); })()}
              onChange={e => setTrackDate(e.target.value)}
              className="hidden sm:block px-4 py-4 rounded-xl text-base font-medium outline-none transition-all"
              style={{
                background: "rgba(255,255,255,0.1)",
                border: "1px solid rgba(255,255,255,0.2)",
                color: "white",
                backdropFilter: "blur(8px)",
                colorScheme: "dark",
                minWidth: 140,
              }}
              title="Select journey date (up to 2 days back)"
              aria-label="Journey date"
            />
            <button
              type="button"
              onClick={handleTrack}
              disabled={loading || !trainNo.trim()}
              className="px-7 py-4 rounded-xl font-semibold text-base flex items-center gap-2 transition-all active:scale-[0.97] disabled:opacity-40"
              style={{ background: "#93c5fd", color: NAVY }}
            >
              {loading ? <SpinnerIcon /> : <ArrowIcon />}
              {loading ? "Tracking..." : "Track"}
            </button>
          </div>
          <p className="text-sm mt-3" style={{ color: "rgba(180,196,221,0.8)" }}>
            Change date for trains that run on specific days (e.g. Tejas runs Tue/Thu/Sat)
          </p>
          <div className="flex items-center gap-2 mt-3 flex-wrap">
            <span className="text-xs" style={{ color: "rgba(180,196,221,0.8)" }}>Try:</span>
            {["10103", "10104"].map((number) => (
              <button key={number} type="button" onClick={() => setTrainNo(number)}
                className="rounded-md px-2.5 py-1.5 text-xs font-mono font-semibold transition-colors hover:bg-white/15"
                style={{ border: "1px solid rgba(255,255,255,0.2)", color: "#bfdbfe" }}>
                {number}
              </button>
            ))}
          </div>
        </div>

      </div>

      {/* ── Error ────────────────────────────── */}
      {error && (
        <div className="rounded-xl px-5 py-4 text-sm animate-fade-in flex items-start gap-3"
          style={{ background: "#fff1f2", border: "1px solid #fecaca", color: "#991b1b" }}>
          <span className="flex-shrink-0 mt-0.5">⚠</span>
          <span>{error}</span>
        </div>
      )}

      {/* ── Results ──────────────────────────── */}
      {result && (
        <div className="space-y-4 stagger animate-fade-up">

          {/* Train header card */}
          <div className="bg-white rounded-2xl overflow-hidden animate-fade-up" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(15,31,61,0.06)", border: "1px solid #e8e8e4" }}>
            {/* Status bar at top */}
            <div className="h-1.5 w-full" style={{ background: d?.dot }} />
            <div className="p-7">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-mono font-bold px-2.5 py-1 rounded-lg" style={{ background: "#f1f5f9", color: "#475569" }}>
                      {result.live.train_no}
                    </span>
                    {result.live.is_corridor && (
                      <span className="text-xs font-semibold px-2.5 py-1 rounded-lg" style={{ background: "#eff6ff", color: "#1d4ed8" }}>
                        Mumbai - Goa Corridor
                      </span>
                    )}
                    <span className="text-xs font-medium px-2.5 py-1 rounded-lg" style={{ background: d?.badge, color: d?.text }}>
                      {d?.label}
                    </span>
                  </div>
                  <h2 className="text-2xl font-bold mt-3 truncate" style={{ color: NAVY }}>
                    {result.live.train_name}
                  </h2>
                  <div className="text-base mt-1.5 flex items-center gap-1.5" style={{ color: "#64748b" }}>
                    <span>{result.live.source_name}</span>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                    <span>{result.live.destination_name}</span>
                  </div>
                </div>
                {/* Delay badge */}
                <div className="text-right flex-shrink-0">
                  <div className="text-4xl font-bold tabular-nums leading-none" style={{ color: d?.text }}>
                    {result.live.delay > 0 ? `+${result.live.delay}` : "0"}
                  </div>
                  <div className="text-base font-medium mt-1" style={{ color: d?.text, opacity: 0.8 }}>
                    {result.live.delay > 0 ? "min late" : "On time"}
                  </div>
                </div>
              </div>

              {/* Current position */}
              <div className="mt-6 rounded-xl p-5 grid grid-cols-3 gap-5" style={{ background: "#f8f9fb" }}>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#94a3b8" }}>Current station</p>
                  <p className="text-base font-semibold mt-1.5 leading-snug" style={{ color: NAVY }}>{result.live.current_station_name}</p>
                  <p className="text-xs font-mono mt-1" style={{ color: "#94a3b8" }}>{result.live.current_station}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#94a3b8" }}>Distance</p>
                  <p className="text-base font-semibold mt-1.5" style={{ color: NAVY }}>{result.live.distance_from_source} km</p>
                  <p className="text-xs mt-1" style={{ color: "#94a3b8" }}>of {result.live.total_distance} km</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#94a3b8" }}>Updated</p>
                  <p className="text-base font-medium mt-1.5 leading-snug" style={{ color: "#475569" }}>{result.live.status_as_of}</p>
                </div>
              </div>

              {/* Progress bar */}
              <div className="mt-4">
                <div className="flex justify-between text-[11px] mb-1.5" style={{ color: "#94a3b8" }}>
                  <span>{result.live.source}</span>
                  <span className="font-medium">{pct}% completed</span>
                  <span>{result.live.destination}</span>
                </div>
                <div className="w-full rounded-full h-2 overflow-hidden" style={{ background: "#e2e8f0" }}>
                  <div className="h-full rounded-full transition-all duration-700"
                    style={{ width: `${pct}%`, background: `linear-gradient(90deg, ${NAVY_LIGHT}, ${NAVY})` }} />
                </div>
              </div>
            </div>
          </div>

          {/* Other trains on route */}
          {result.live.is_corridor && result.other_trains.length > 0 && (
            <div className="bg-white rounded-2xl p-6 animate-fade-up" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.06)", border: "1px solid #e8e8e4" }}>
              <p className="text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "#94a3b8" }}>Other trains on this corridor</p>
              <div className="space-y-3">
                {result.other_trains.map(t => {
                  const td = delay(t.delay);
                  return (
                    <div key={t.train_no} className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: td.dot }} />
                      <span className="text-sm font-mono font-bold" style={{ color: "#64748b" }}>{t.train_no}</span>
                      <span className="text-base flex-1 truncate" style={{ color: "#374151" }}>{t.train_name}</span>
                      <span className="text-sm" style={{ color: "#94a3b8" }}>at {t.current_station}</span>
                      <span className="text-base font-semibold tabular-nums" style={{ color: td.text }}>+{t.delay}m</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Weather strip */}
          {result.predictions.some(p => p.weather) && (
            <div className="bg-white rounded-2xl p-6 animate-fade-up" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.06)", border: "1px solid #e8e8e4" }}>
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#94a3b8" }}>Weather along route</p>
                <span className="text-xs font-medium px-2.5 py-1 rounded-md" style={{ background: "#f0fdf4", color: "#15803d" }}>Live · Open-Meteo</span>
              </div>
              <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
                {result.predictions.filter(p => p.weather).map(p => {
                  const sev = p.weather!.severity?.severity_level || "CLEAR";
                  const sevStyles = {
                    SEVERE:   { bg: "#fff1f2", border: "#fecaca", label: "#dc2626" },
                    MODERATE: { bg: "#fffbeb", border: "#fde68a", label: "#b45309" },
                    MILD:     { bg: "#fefce8", border: "#fef08a", label: "#a16207" },
                    CLEAR:    { bg: "#f8f9fb", border: "#e2e8f0", label: "#475569" },
                  }[sev] || { bg: "#f8f9fb", border: "#e2e8f0", label: "#475569" };
                  return (
                    <div key={p.station_code} className="flex-shrink-0 rounded-xl px-4 py-3 text-center min-w-[92px]"
                      style={{ background: sevStyles.bg, border: `1px solid ${sevStyles.border}` }}>
                      <p className="text-xs font-mono font-bold" style={{ color: NAVY }}>{p.station_code}</p>
                      <p className="text-xs mt-1" style={{ color: sevStyles.label }}>{p.weather!.condition}</p>
                      <p className="text-xs" style={{ color: "#94a3b8" }}>{p.weather!.temperature_c}°C</p>
                      {(p.weather!.rainfall_mm || 0) > 0 && (
                        <p className="text-[10px] font-semibold mt-0.5" style={{ color: "#2563eb" }}>{p.weather!.rainfall_mm}mm</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Predictions */}
          {result.predictions.length > 0 && (
            <div className="bg-white rounded-2xl overflow-hidden animate-fade-up" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.06)", border: "1px solid #e8e8e4" }}>
              <div className="px-7 py-5 flex items-center justify-between" style={{ borderBottom: "1px solid #f1f5f9" }}>
                <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#94a3b8" }}>
                  Upcoming stations · {result.predictions.length} stops
                </p>
                <p className="text-xs" style={{ color: "#94a3b8" }}>Click any stop for analysis</p>
              </div>

              {/* Timeline */}
              <div className="divide-y" style={{ borderColor: "#f8f9fb" }}>
                {result.predictions.map((p, idx) => {
                  const td = delay(p.predicted_delay);
                  const isOpen = expandedIdx === idx;
                  const isLast = idx === result.predictions.length - 1;

                  return (
                    <div key={p.station_code}>
                      <button
                        className="w-full text-left transition-colors"
                        onClick={() => setExpandedIdx(isOpen ? null : idx)}
                        style={{ background: isOpen ? "#f8f9fb" : "white" }}
                        onMouseEnter={e => { if (!isOpen) (e.currentTarget as HTMLElement).style.background = "#fafafa"; }}
                        onMouseLeave={e => { if (!isOpen) (e.currentTarget as HTMLElement).style.background = "white"; }}
                      >
                        <div className="flex items-center gap-5 px-7 py-5">
                          {/* Station dot + line */}
                          <div className="flex flex-col items-center gap-0 self-stretch flex-shrink-0" style={{ width: 20 }}>
                            <div className="w-3 h-3 rounded-full border-2 flex-shrink-0"
                              style={{ background: isLast ? td.dot : "white", borderColor: td.dot }} />
                            {!isLast && <div className="w-px flex-1 mt-1" style={{ background: "#e2e8f0" }} />}
                          </div>

                          {/* Station info */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-base font-bold font-mono" style={{ color: NAVY }}>{p.station_code}</span>
                              <span className="text-base" style={{ color: "#475569" }}>{p.station_name}</span>
                              {p.scheduled_arrival && (
                                <span className="text-sm" style={{ color: "#94a3b8" }}>sch {p.scheduled_arrival}</span>
                              )}
                            </div>
                            <div className="text-sm mt-1" style={{ color: "#94a3b8" }}>{p.distance_km} km from origin</div>
                          </div>

                          {/* Delay */}
                          <div className="text-right flex items-center gap-3 flex-shrink-0">
                            <div>
                              <div className="text-base font-bold tabular-nums" style={{ color: td.text }}>+{p.predicted_delay}m</div>
                              <div className="text-xs tabular-nums mt-1" style={{ color: "#94a3b8" }}>{p.lower_bound}–{p.upper_bound}m</div>
                            </div>
                            <div style={{ color: "#cbd5e1" }}>
                              <ChevronIcon open={isOpen} />
                            </div>
                          </div>
                        </div>
                      </button>

                      {/* Expanded analysis */}
                      <div className="overflow-hidden transition-all duration-300 ease-in-out" style={{ maxHeight: isOpen ? 800 : 0, opacity: isOpen ? 1 : 0 }}>
                        <div className="px-6 pb-5 pt-1">
                          <div className="rounded-xl p-4 space-y-3" style={{ background: "#f8f9fb", border: "1px solid #f1f5f9" }}>

                            {/* Header */}
                            <div className="flex items-center justify-between">
                              <p className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "#94a3b8" }}>
                                Delay factors at {p.station_name}
                              </p>
                              <span className="text-xs font-bold px-2 py-0.5 rounded" style={{ background: td.badge, color: td.text }}>
                                +{p.predicted_delay}m predicted · {p.lower_bound}–{p.upper_bound}m range
                              </span>
                            </div>

                            {/* SHAP reasons — primary content */}
                            {p.explanations?.length > 0 ? (
                              <div className="space-y-1.5">
                                {p.explanations.map((e, i) => {
                                  const isInc = e.direction === "INCREASING";
                                  return (
                                    <div key={i} className="flex items-start gap-3 px-3 py-2.5 rounded-lg"
                                      style={{ background: isInc ? "#fff1f2" : "#f0fdf4", border: `1px solid ${isInc ? "#fecaca" : "#bbf7d0"}` }}>
                                      <span className="flex-shrink-0 text-base mt-0.5">{ICON_MAP[e.icon] || ICON_MAP.info}</span>
                                      <span className="flex-1 text-[13px] leading-snug" style={{ color: "#374151" }}>{e.description}</span>
                                      <span className="font-bold text-sm tabular-nums flex-shrink-0 mt-0.5" style={{ color: isInc ? "#dc2626" : "#059669" }}>
                                        {e.contribution_minutes > 0 ? "+" : ""}{e.contribution_minutes}m
                                      </span>
                                    </div>
                                  );
                                })}
                              </div>
                            ) : (
                              <p className="text-xs" style={{ color: "#94a3b8" }}>
                                A detailed explanation is not available for this stop. The ETA uses the latest live delay and historical running-time patterns.
                              </p>
                            )}

                            {/* Context: weather + section */}
                            {p.weather && p.section && (
                              <div className="grid grid-cols-2 gap-2 pt-1">
                                <div className="rounded-lg px-3 py-2.5" style={{ background: "white", border: "1px solid #f1f5f9" }}>
                                  <p className="text-[10px] font-semibold uppercase tracking-wide mb-1" style={{ color: "#94a3b8" }}>Live weather</p>
                                  <p className="text-sm font-medium" style={{ color: "#1e293b" }}>{p.weather.condition} · {p.weather.temperature_c}°C</p>
                                  <p className="text-xs mt-0.5" style={{ color: "#94a3b8" }}>
                                    {(p.weather.rainfall_mm || 0) > 0 ? `${p.weather.rainfall_mm}mm rain · ` : "No rain · "}
                                    Vis {p.weather.visibility_km || 10}km
                                  </p>
                                  {p.weather.severity?.factors?.length > 0 && (
                                    <p className="text-xs mt-1 font-medium" style={{ color: "#b45309" }}>{p.weather.severity.factors.join(", ")}</p>
                                  )}
                                </div>
                                <div className="rounded-lg px-3 py-2.5" style={{ background: "white", border: "1px solid #f1f5f9" }}>
                                  <p className="text-[10px] font-semibold uppercase tracking-wide mb-1" style={{ color: "#94a3b8" }}>Track section</p>
                                  <p className="text-sm font-medium capitalize" style={{ color: "#1e293b" }}>{p.section.terrain} · {p.section.track} track</p>
                                  <p className="text-xs mt-0.5" style={{ color: "#94a3b8" }}>
                                    {[p.section.tunnels > 0 && `${p.section.tunnels} tunnels`, p.section.bridges > 0 && `${p.section.bridges} bridges`, `${p.section.speed_limit} km/h`].filter(Boolean).join(" · ")}
                                  </p>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>


                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Methodology footnote */}
          <p className="text-[11px] px-1 leading-relaxed animate-fade-up" style={{ color: "#94a3b8" }}>
            {result.methodology}
          </p>
        </div>
      )}

      {/* ── Empty state ───────────────────────── */}
      {!result && !loading && !error && (
        <div className="text-center py-20 animate-fade-in">
          <div className="flex justify-center mb-6 opacity-30">
            <TrainIllustration />
          </div>
          <p className="text-sm font-medium" style={{ color: "#94a3b8" }}>Enter a train number to begin tracking</p>
          <p className="text-xs mt-1" style={{ color: "#cbd5e1" }}>Works with any IRCTC train across India</p>
        </div>
      )}
    </div>
  );
}
