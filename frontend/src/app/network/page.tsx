"use client";

import { useState, useEffect } from "react";

const API = "";
const NAVY = "#0f1f3d";

interface Station { code: string; name: string; short_name: string; lat: number; lon: number; km: number; zone: string; elevation_m: number; section_type: string }
interface SectionInfo { section_id: string; from_station: string; from_name: string; to_station: string; to_name: string; track: string; terrain: string; tunnels: number; bridges: number; speed_limit: number; risk: string }
interface Weather { condition: string; temperature_c: number; rainfall_mm: number; visibility_km: number; severity: { severity_score: number; severity_level: string; factors: string[] } }
interface TrackedTrain { train_no: string; train_name: string; current_station: string; delay: number; direction: string }

const terrainLabel: Record<string, string> = {
  urban: "Urban", junction: "Junction", transition: "Transition",
  ghat: "Western Ghats", coastal_ghat: "Coastal Ghats", coastal: "Coastal",
};

const riskStyle = (r: string) => r === "high"
  ? { bg: "#fff1f2", text: "#dc2626", border: "#fecaca" }
  : r === "medium"
  ? { bg: "#fffbeb", text: "#b45309", border: "#fde68a" }
  : { bg: "#f0fdf4", text: "#059669", border: "#bbf7d0" };

const delayStyle = (d: number) =>
  d > 15 ? "#ef4444" : d > 5 ? "#f59e0b" : "#10b981";

async function fetchJson(path: string) {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}

export default function NetworkPage() {
  const [stations, setStations] = useState<Station[]>([]);
  const [sections, setSections] = useState<SectionInfo[]>([]);
  const [weather, setWeather] = useState<Record<string, Weather>>({});
  const [liveTrains, setLiveTrains] = useState<TrackedTrain[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetchJson("/api/corridor/stations"),
      fetchJson("/api/corridor/sections"),
      fetchJson("/api/corridor/weather"),
      fetchJson("/api/corridor/live-trains"),
    ]).then(([st, sec, wx, lt]) => {
      setStations(st.stations || []);
      setSections(sec.sections || []);
      setWeather(wx.weather || {});
      setLiveTrains(lt.trains || []);
    }).catch(() => setError("Network data is unavailable. Start the backend and refresh this page.")).finally(() => setLoading(false));
  }, []);

  const fwdSections = sections.filter(s => {
    const fi = stations.findIndex(st => st.code === s.from_station);
    const ti = stations.findIndex(st => st.code === s.to_station);
    return fi >= 0 && ti >= 0 && fi < ti;
  });

  if (loading) {
    return (
      <div className="space-y-5 pb-20">
        {/* skeleton */}
        <div className="rounded-2xl h-40 shimmer" />
        <div className="rounded-2xl h-80 shimmer" />
        <div className="rounded-2xl h-64 shimmer" />
      </div>
    );
  }

  return (
    <div className="space-y-5 pb-20">

      {error && <div className="rounded-xl px-5 py-4 text-sm" style={{ background: "#fff1f2", border: "1px solid #fecaca", color: "#991b1b" }}>{error}</div>}

      {/* ── Hero ───────────────────────────────── */}
      <div className="rounded-2xl p-8 relative overflow-hidden" style={{
        background: `linear-gradient(135deg, ${NAVY} 0%, #1a3460 100%)`,
      }}>
        <div className="absolute inset-0 opacity-[0.06]" style={{
          backgroundImage: "radial-gradient(circle, white 1px, transparent 1px)",
          backgroundSize: "24px 24px",
        }}/>
        <div className="relative">
          <p className="text-xs font-semibold uppercase tracking-widest mb-2" style={{ color: "#7ea8d8" }}>
            Mumbai - Goa · Konkan Railway
          </p>
          <h1 className="text-2xl font-bold text-white">Corridor Network</h1>
          <div className="flex items-center gap-6 mt-4 flex-wrap">
            {[
              { label: "Stations", value: stations.length },
              { label: "Sections", value: fwdSections.length },
              { label: "Tracked trains", value: liveTrains.length },
            ].map(s => (
              <div key={s.label}>
                <div className="text-2xl font-bold text-white">{s.value}</div>
                <div className="text-xs mt-0.5" style={{ color: "#7ea8d8" }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Live trains ────────────────────────── */}
      {liveTrains.length > 0 && (
        <div className="bg-white rounded-2xl p-5" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.06)", border: "1px solid #e8e8e4" }}>
          <p className="text-[10px] font-semibold uppercase tracking-widest mb-3" style={{ color: "#94a3b8" }}>Currently tracked</p>
          <div className="space-y-2.5">
            {liveTrains.map(t => (
              <div key={t.train_no} className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: delayStyle(t.delay) }} />
                <span className="text-xs font-mono font-bold w-14" style={{ color: "#64748b" }}>{t.train_no}</span>
                <span className="text-sm flex-1 font-medium" style={{ color: "#1e293b" }}>{t.train_name}</span>
                <span className="text-xs px-2 py-0.5 rounded-md" style={{ background: "#f1f5f9", color: "#64748b" }}>
                  at {t.current_station}
                </span>
                <span className="text-sm font-bold tabular-nums" style={{ color: delayStyle(t.delay) }}>
                  {t.delay > 0 ? `+${t.delay}m` : "On time"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Station map + weather ──────────────── */}
      <div className="bg-white rounded-2xl overflow-hidden" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.06)", border: "1px solid #e8e8e4" }}>
        <div className="px-6 py-4 flex items-center justify-between" style={{ borderBottom: "1px solid #f1f5f9" }}>
          <p className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "#94a3b8" }}>Stations and weather</p>
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-md" style={{ background: "#f0fdf4", color: "#15803d" }}>Live · Open-Meteo</span>
        </div>

        <div className="divide-y" style={{ borderColor: "#f8f9fb" }}>
          {stations.map((st, i) => {
            const wx = weather[st.code];
            const sev = wx?.severity?.severity_level || "CLEAR";
            const sevStyle = { SEVERE: "#dc2626", MODERATE: "#b45309", MILD: "#a16207", CLEAR: "#94a3b8" }[sev] || "#94a3b8";
            const trainHere = liveTrains.filter(t => t.current_station === st.code);
            const isGhat = ["ghat", "coastal_ghat"].includes(st.section_type);

            return (
              <div key={st.code} className="flex items-center gap-4 px-6 py-3.5">
                {/* Timeline */}
                <div className="flex flex-col items-center self-stretch flex-shrink-0" style={{ width: 20 }}>
                  <div className={`w-3 h-3 rounded-full border-2 flex-shrink-0`}
                    style={{
                      borderColor: trainHere.length > 0 ? NAVY : "#cbd5e1",
                      background: trainHere.length > 0 ? NAVY : "white",
                    }} />
                  {i < stations.length - 1 && <div className="w-px flex-1 mt-1" style={{ background: "#e2e8f0" }} />}
                </div>

                {/* Station code */}
                <div className="w-14 flex-shrink-0">
                  <span className="text-xs font-mono font-bold" style={{ color: NAVY }}>{st.code}</span>
                  <div className="text-[10px] mt-0.5" style={{ color: "#94a3b8" }}>{st.km}km</div>
                </div>

                {/* Station name + badges */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium" style={{ color: "#1e293b" }}>{st.short_name}</span>
                    {isGhat && (
                      <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded" style={{ background: "#fef3c7", color: "#92400e" }}>
                        Ghat
                      </span>
                    )}
                    {trainHere.map(t => (
                      <span key={t.train_no} className="text-[10px] font-bold px-1.5 py-0.5 rounded text-white" style={{ background: NAVY }}>
                        {t.train_no}
                      </span>
                    ))}
                  </div>
                  <div className="text-[11px] mt-0.5" style={{ color: "#94a3b8" }}>
                    {terrainLabel[st.section_type] || st.section_type} · {st.zone}
                  </div>
                </div>

                {/* Weather */}
                {wx ? (
                  <div className="text-right flex-shrink-0">
                    <div className="text-xs font-medium" style={{ color: sevStyle }}>{wx.condition}</div>
                    <div className="text-[11px] tabular-nums mt-0.5" style={{ color: "#94a3b8" }}>
                      {wx.temperature_c}°C
                      {wx.rainfall_mm > 0 && <span className="ml-1.5 font-semibold" style={{ color: "#2563eb" }}>{wx.rainfall_mm}mm</span>}
                    </div>
                  </div>
                ) : (
                  <div className="text-[10px]" style={{ color: "#e2e8f0" }}>No data</div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Sections ──────────────────────────── */}
      <div className="bg-white rounded-2xl overflow-hidden" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.06)", border: "1px solid #e8e8e4" }}>
        <div className="px-6 py-4" style={{ borderBottom: "1px solid #f1f5f9" }}>
          <p className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "#94a3b8" }}>Section characteristics</p>
        </div>
        <div className="divide-y" style={{ borderColor: "#f8f9fb" }}>
          {fwdSections.map(s => {
            const rs = riskStyle(s.risk);
            const isOpen = activeSection === s.section_id;
            return (
              <div key={s.section_id}>
                <button
                  className="w-full text-left flex items-center gap-4 px-6 py-3.5 transition-colors"
                  style={{ background: isOpen ? "#f8f9fb" : "white" }}
                  onMouseEnter={e => { if (!isOpen) (e.currentTarget as HTMLElement).style.background = "#fafafa"; }}
                  onMouseLeave={e => { if (!isOpen) (e.currentTarget as HTMLElement).style.background = "white"; }}
                  onClick={() => setActiveSection(isOpen ? null : s.section_id)}
                >
                  <div className="min-w-[120px] flex-shrink-0">
                    <span className="text-xs font-mono font-bold" style={{ color: NAVY }}>{s.from_station}</span>
                    <span className="text-xs mx-1.5" style={{ color: "#cbd5e1" }}>→</span>
                    <span className="text-xs font-mono font-bold" style={{ color: NAVY }}>{s.to_station}</span>
                  </div>
                  <div className="flex-1 text-sm capitalize" style={{ color: "#475569" }}>
                    {terrainLabel[s.terrain] || s.terrain}
                  </div>
                  <div className="flex items-center gap-2 text-xs" style={{ color: "#94a3b8" }}>
                    <span>{s.track} track</span>
                    {s.tunnels > 0 && <span className="font-medium" style={{ color: "#475569" }}>{s.tunnels}T</span>}
                    {s.bridges > 0 && <span className="font-medium" style={{ color: "#475569" }}>{s.bridges}B</span>}
                    <span>{s.speed_limit}km/h</span>
                  </div>
                  <span className="text-xs font-semibold px-2.5 py-1 rounded-full flex-shrink-0"
                    style={{ background: rs.bg, color: rs.text, border: `1px solid ${rs.border}` }}>
                    {s.risk}
                  </span>
                </button>
                {/* Expanded detail */}
                <div className="overflow-hidden transition-all duration-200" style={{ maxHeight: isOpen ? 120 : 0, opacity: isOpen ? 1 : 0 }}>
                  <div className="px-6 pb-4 pt-1">
                    <div className="grid grid-cols-3 gap-3 rounded-xl p-4" style={{ background: "#f8f9fb" }}>
                      {[
                        { label: "Track type", value: s.track + " track" },
                        { label: "Terrain", value: terrainLabel[s.terrain] || s.terrain },
                        { label: "Speed limit", value: `${s.speed_limit} km/h` },
                        { label: "Tunnels", value: s.tunnels || "None" },
                        { label: "Bridges", value: s.bridges || "None" },
                        { label: "Risk level", value: s.risk },
                      ].map(f => (
                        <div key={f.label}>
                          <div className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: "#94a3b8" }}>{f.label}</div>
                          <div className="text-sm font-medium mt-0.5 capitalize" style={{ color: "#1e293b" }}>{f.value}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
