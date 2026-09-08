import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactElement, ReactNode } from "react";
import { apiClient, type IncidentApiClient } from "./api/client";
import type { Incident, IncidentDetail, TimelineEvent, TriageStats } from "./types/domain";
import { severityClass, statusClass, toneClass } from "./utils/classNames";
import { formatNumber, formatTime } from "./utils/format";
import "./styles.css";

type DashboardView = "incidents" | "live" | "timeline" | "root";

interface DashboardState {
  stats: TriageStats | null;
  incidents: Incident[];
  timeline: TimelineEvent[];
  selectedIncidentId: number | null;
  selectedIncidentDetail: IncidentDetail | null;
}

interface AppProps {
  client?: IncidentApiClient;
}

interface ViewCopy {
  title: string;
  meta: string;
}

const viewCopy: Record<DashboardView, ViewCopy> = {
  incidents: {
    title: "Incident View",
    meta: "Top active incidents ranked by severity and confidence. Click a row to update the selected incident.",
  },
  live: {
    title: "Live Event Stream",
    meta: "Latest correlated signals across deploys, anomalies, and incident generation.",
  },
  timeline: {
    title: "Timeline View",
    meta: "Ordered system activity for quick temporal correlation across services.",
  },
  root: {
    title: "Root Cause Panel",
    meta: "Dependency-aware candidates and supporting evidence for the selected incident.",
  },
};

const dashboardViews: { id: DashboardView; title: string; description: string }[] = [
  { id: "incidents", title: "Incident View", description: "Prioritized incidents and severity" },
  { id: "live", title: "Live Event Stream", description: "Latest correlated telemetry" },
  { id: "timeline", title: "Timeline View", description: "Deploys, anomalies, and incident order" },
  { id: "root", title: "Root Cause Panel", description: "Ranked candidates and evidence" },
];

const initialState: DashboardState = {
  stats: null,
  incidents: [],
  timeline: [],
  selectedIncidentId: null,
  selectedIncidentDetail: null,
};

function fallbackText(value: string | null, fallback = "-"): string {
  return value === null || value.length === 0 ? fallback : value;
}

export default function App({ client = apiClient }: AppProps): ReactElement {
  const [activeView, setActiveView] = useState<DashboardView>("incidents");
  const [dashboard, setDashboard] = useState<DashboardState>(initialState);

  const selectedIncident = useMemo(
    () => dashboard.incidents.find((incident) => incident.id === dashboard.selectedIncidentId) ?? null,
    [dashboard.incidents, dashboard.selectedIncidentId],
  );

  const loadIncidentDetail = useCallback(
    async (incidentId: number, signal?: AbortSignal): Promise<IncidentDetail> => client.getIncidentDetail(incidentId, signal),
    [client],
  );

  const refresh = useCallback(
    async (signal?: AbortSignal): Promise<void> => {
      const [stats, incidents, timeline] = await Promise.all([
        client.getTriageStats(signal),
        client.listIncidents(signal),
        client.listTimeline(signal),
      ]);

      const nextSelectedIncidentId =
        incidents.length === 0
          ? null
          : dashboard.selectedIncidentId && incidents.some((incident) => incident.id === dashboard.selectedIncidentId)
            ? dashboard.selectedIncidentId
            : incidents[0]?.id ?? null;

      const selectedIncidentDetail = nextSelectedIncidentId
        ? await loadIncidentDetail(nextSelectedIncidentId, signal)
        : null;

      setDashboard({
        stats,
        incidents,
        timeline,
        selectedIncidentId: nextSelectedIncidentId,
        selectedIncidentDetail,
      });
    },
    [client, dashboard.selectedIncidentId, loadIncidentDetail],
  );

  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal).catch(() => undefined);

    const intervalId = window.setInterval(() => {
      void refresh().catch(() => undefined);
    }, 4000);

    return () => {
      controller.abort();
      window.clearInterval(intervalId);
    };
  }, [refresh]);

  const selectIncident = async (incidentId: number, openRoot = false): Promise<void> => {
    const selectedIncidentDetail = await loadIncidentDetail(incidentId);
    setDashboard((current) => ({
      ...current,
      selectedIncidentId: incidentId,
      selectedIncidentDetail,
    }));

    if (openRoot) {
      setActiveView("root");
    }
  };

  const stats = dashboard.stats;
  const copy = viewCopy[activeView];

  return (
    <main className="wrap">
      <header className="hero">
        <h1>Incident Intelligence Platform</h1>
      </header>

      <section className="grid4">
        <MetricCard label="System Status">
          <div className="v" data-testid="system-status-text">
            {stats ? stats.system_status.toUpperCase() : "-"}
          </div>
          <div className={`status ${stats ? statusClass(stats.system_status) : "healthy"}`}>
            {stats ? stats.system_status.toUpperCase() : "HEALTHY"}
          </div>
        </MetricCard>
        <MetricCard label="Active Incidents" value={stats ? String(stats.open_incidents) : "-"} />
        <MetricCard label="Active Anomalies (20m)" value={stats ? String(stats.active_anomalies) : "-"} />
        <MetricCard label="Est. MTTR (min)" value={stats ? formatNumber(stats.mttr_minutes_estimate, 1) : "-"} />
      </section>

      <section className="workspace">
        <article className="card toolbar">
          <div>
            <div className="eyebrow">Workspace</div>
            <h2>Signal Triage Console</h2>
          </div>

          <div className="view-switch" role="tablist" aria-label="Dashboard views">
            {dashboardViews.map((view) => (
              <button
                aria-selected={view.id === activeView}
                className={`view-btn ${view.id === activeView ? "active" : ""}`}
                key={view.id}
                onClick={() => {
                  setActiveView(view.id);
                }}
                role="tab"
                type="button"
              >
                <strong>{view.title}</strong>
                <small>{view.description}</small>
              </button>
            ))}
          </div>
        </article>

        <SelectionStrip
          detail={dashboard.selectedIncidentDetail}
          incident={selectedIncident}
          onOpenRoot={() => {
            setActiveView("root");
          }}
        />

        <article className="card panel-shell">
          <div className="panel-head">
            <div>
              <div className="eyebrow">Active View</div>
              <h3>{copy.title}</h3>
              <div className="panel-meta">{copy.meta}</div>
            </div>
            <button
              className="ghost-btn"
              disabled={!dashboard.selectedIncidentId}
              onClick={() => {
                setActiveView("root");
              }}
              type="button"
            >
              Open Root Cause Panel
            </button>
          </div>
          <div className="panel-body">
            <PanelBody
              activeView={activeView}
              incidents={dashboard.incidents}
              selectedIncidentDetail={dashboard.selectedIncidentDetail}
              selectedIncidentId={dashboard.selectedIncidentId}
              timeline={dashboard.timeline}
              onSelectIncident={selectIncident}
            />
          </div>
        </article>
      </section>
    </main>
  );
}

interface MetricCardProps {
  label: string;
  value?: string;
  children?: ReactNode;
}

function MetricCard({ label, value, children }: MetricCardProps): ReactElement {
  return (
    <article className="card">
      <div className="k">{label}</div>
      {children ?? <div className="v">{value}</div>}
    </article>
  );
}

interface SelectionStripProps {
  incident: Incident | null;
  detail: IncidentDetail | null;
  onOpenRoot: () => void;
}

function SelectionStrip({ incident, detail, onOpenRoot }: SelectionStripProps): ReactElement {
  const selected = detail ?? incident;

  if (!selected) {
    return (
      <article className="card selection-strip">
        <div className="selection-main">
          <div className="eyebrow">Selected Incident</div>
          <div className="selection-title">No active incidents</div>
          <div className="selection-sub">Waiting for correlated failures or anomaly signals.</div>
        </div>
      </article>
    );
  }

  return (
    <article className="card selection-strip">
      <div className="selection-main">
        <div className="eyebrow">Selected Incident</div>
        <div className="selection-title">
          #{selected.id} {selected.service}
        </div>
        <div className="selection-sub">{selected.title ? selected.title : "No title available"}</div>
      </div>
      <div className="selection-metric">
        <span>Severity</span>
        <strong>
          <span className={`badge ${severityClass(selected.severity)}`}>{selected.severity}</span>
        </strong>
      </div>
      <div className="selection-metric">
        <span>Linked Events</span>
        <strong>{selected.linked_events}</strong>
      </div>
      <div className="selection-metric">
        <span>Probable Root Cause</span>
        <strong>{fallbackText(selected.probable_root_cause)}</strong>
      </div>
      <div className="selection-actions">
        <button className="ghost-btn" onClick={onOpenRoot} type="button">
          Open Root Cause
        </button>
      </div>
    </article>
  );
}

interface PanelBodyProps {
  activeView: DashboardView;
  incidents: Incident[];
  selectedIncidentDetail: IncidentDetail | null;
  selectedIncidentId: number | null;
  timeline: TimelineEvent[];
  onSelectIncident: (incidentId: number, openRoot?: boolean) => Promise<void>;
}

function PanelBody({
  activeView,
  incidents,
  selectedIncidentDetail,
  selectedIncidentId,
  timeline,
  onSelectIncident,
}: PanelBodyProps): ReactElement {
  if (activeView === "incidents") {
    return (
      <IncidentTable incidents={incidents} selectedIncidentId={selectedIncidentId} onSelectIncident={onSelectIncident} />
    );
  }
  if (activeView === "live") {
    return <LiveFeed timeline={timeline} />;
  }
  if (activeView === "timeline") {
    return <Timeline timeline={timeline} />;
  }
  return <RootCausePanel detail={selectedIncidentDetail} />;
}

interface IncidentTableProps {
  incidents: Incident[];
  selectedIncidentId: number | null;
  onSelectIncident: (incidentId: number, openRoot?: boolean) => Promise<void>;
}

function IncidentTable({ incidents, selectedIncidentId, onSelectIncident }: IncidentTableProps): ReactElement {
  if (!incidents.length) {
    return <div className="empty">No incidents yet. Inject failures or wait for anomaly correlation.</div>;
  }

  return (
    <>
      <table className="tbl">
        <thead>
          <tr>
            <th>ID</th>
            <th>Service</th>
            <th>Severity</th>
            <th>Score</th>
            <th>Probable Root Cause</th>
            <th>Events</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {incidents.slice(0, 12).map((incident) => (
            <tr
              className={`clickable ${incident.id === selectedIncidentId ? "selected" : ""}`}
              key={incident.id}
              onClick={() => {
                void onSelectIncident(incident.id);
              }}
            >
              <td>#{incident.id}</td>
              <td>{incident.service}</td>
              <td>
                <span className={`badge ${severityClass(incident.severity)}`}>{incident.severity}</span>
              </td>
              <td>{formatNumber(incident.severity_score, 1)}</td>
              <td>{fallbackText(incident.probable_root_cause)}</td>
              <td>{incident.linked_events}</td>
              <td>
                <button
                  className="mini-btn"
                  onClick={(event) => {
                    event.stopPropagation();
                    void onSelectIncident(incident.id, true);
                  }}
                  type="button"
                >
                  Inspect
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="table-note">
        Click any incident row to change the selected incident. Use Inspect to jump directly into root-cause analysis.
      </div>
    </>
  );
}

interface TimelineProps {
  timeline: TimelineEvent[];
}

function LiveFeed({ timeline }: TimelineProps): ReactElement {
  if (!timeline.length) {
    return <div className="empty">No live events available yet.</div>;
  }

  return (
    <div className="stream-list">
      {timeline.slice(0, 16).map((item) => (
        <div className="stream-item" key={`${item.kind}-${item.service}-${item.timestamp}-${item.title}`}>
          <div className="stream-top">
            <strong>{item.service}</strong>
            <span className={`tone ${toneClass(item.kind)}`}>{item.kind}</span>
          </div>
          <div className="item-title">{item.title}</div>
          <div className="muted item-meta">
            {formatTime(item.timestamp)}
            {item.score !== null ? ` | score ${formatNumber(item.score, 2)}` : ""}
          </div>
        </div>
      ))}
    </div>
  );
}

function Timeline({ timeline }: TimelineProps): ReactElement {
  if (!timeline.length) {
    return <div className="empty">No timeline activity available yet.</div>;
  }

  return (
    <div className="timeline-shell">
      <div className="timeline-list">
        {timeline.slice(0, 18).map((item) => (
          <div className="timeline-item" key={`${item.kind}-${item.service}-${item.timestamp}-${item.title}`}>
            <div className="timeline-top">
              <strong>{item.title}</strong>
              <span className={`tone ${toneClass(item.kind)}`}>{item.kind}</span>
            </div>
            <div className="muted item-meta">
              {item.service} | {formatTime(item.timestamp)}
            </div>
            <div className="muted item-detail">
              {item.score !== null ? `Correlation score ${formatNumber(item.score, 2)}` : "No score attached"}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

interface RootCausePanelProps {
  detail: IncidentDetail | null;
}

function RootCausePanel({ detail }: RootCausePanelProps): ReactElement {
  if (!detail) {
    return <div className="empty">Select an incident from Incident View to inspect probable root causes.</div>;
  }

  return (
    <div className="root-layout">
      <div className="root-summary">
        <RootBox label="Incident" value={`#${String(detail.id)} ${detail.service}`} />
        <RootBox label="Severity" value={detail.severity} />
        <RootBox label="Probable Root Cause" value={fallbackText(detail.probable_root_cause)} />
        <RootBox label="Confidence" value={formatNumber(detail.confidence, 2)} />
      </div>

      <div>
        <h4 className="section-title">Ranked Candidates</h4>
        <div className="root-table">
          <div className="root-row head">
            <div>Service</div>
            <div>Score</div>
            <div>Confidence</div>
          </div>
          {detail.root_cause_ranking.length ? (
            detail.root_cause_ranking.map((candidate) => (
              <div className="root-row" key={candidate.service}>
                <div>{candidate.service}</div>
                <div>{formatNumber(candidate.score, 2)}</div>
                <div>{formatNumber(candidate.confidence, 2)}</div>
              </div>
            ))
          ) : (
            <div className="root-row">
              <div>-</div>
              <div>-</div>
              <div>-</div>
            </div>
          )}
        </div>
      </div>

      <div>
        <h4 className="section-title">Supporting Evidence</h4>
        <div className="evidence-list">
          {detail.recent_event_messages.length ? (
            detail.recent_event_messages.slice(0, 6).map((message) => (
              <div className="evidence-item" key={message}>
                {message}
              </div>
            ))
          ) : (
            <div className="evidence-item">No recent event messages captured for this incident.</div>
          )}
        </div>
      </div>
    </div>
  );
}

interface RootBoxProps {
  label: string;
  value: string;
}

function RootBox({ label, value }: RootBoxProps): ReactElement {
  return (
    <div className="root-box">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
