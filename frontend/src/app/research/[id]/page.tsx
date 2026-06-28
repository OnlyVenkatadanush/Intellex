"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

interface LogMessage {
  agent_name: string;
  agent_role: string;
  message: string;
  log_type: string;
}

interface Citation {
  id: string;
  source_title: string;
  source_url: string;
  citation_format: string;
  quote?: string;
}

interface Finding {
  id: string;
  claim: string;
  confidence_score: number;
  source_count: number;
  source_quality_score: number;
  verification_status: string;
  consensus_rationale?: string;
  citations: Citation[];
}

interface SessionDetail {
  id: string;
  original_query: string;
  status: string;
  report_markdown?: string;
  findings: Finding[];
}

interface GraphNode {
  id: string;
  label: string;
  type: string;
  confidence?: number;
  verification?: string;
}

interface GraphEdge {
  source: string;
  target: string;
  type: string;
  id?: string;
}

interface ReplayStep {
  step_index: number;
  agent_name: string;
  agent_role: string;
  started_at: string | null;
  events: Array<{ id: string; message: string; log_type: string; timestamp: string | null }>;
}

type TabType = "report" | "findings" | "graph" | "replay";

const NODE_TYPE_COLORS: Record<string, string> = {
  QUERY: "var(--accent-purple)",
  CONCEPT: "hsl(220, 70%, 60%)",
  SOURCE: "var(--accent-cyan)",
  FINDING: "var(--success)",
  DEBATE: "var(--warning)",
};

const VERIFICATION_COLORS: Record<string, string> = {
  VERIFIED: "var(--success)",
  CONTRADICTED: "var(--error)",
  INSUFFICIENT_EVIDENCE: "var(--warning)",
};

function ConfidenceBar({ score }: { score: number }) {
  const pct = Math.min(100, Math.max(0, score));
  const color = pct >= 75 ? "var(--success)" : pct >= 50 ? "var(--warning)" : "var(--error)";
  return (
    <div style={{ position: "relative", height: "6px", background: "var(--bg-primary)", borderRadius: "3px", overflow: "hidden" }}>
      <div style={{
        position: "absolute", left: 0, top: 0, bottom: 0,
        width: `${pct}%`, background: color,
        borderRadius: "3px", transition: "width 0.8s ease"
      }} />
    </div>
  );
}

function SimpleGraph({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  if (!nodes.length) {
    return (
      <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", textAlign: "center", padding: "2rem" }}>
        Graph will appear after research completes.
      </p>
    );
  }

  // Circular layout
  const cx = 250, cy = 120, r = 90;
  const nonRoot = nodes.filter(n => n.id !== "root" && n.type !== "QUERY");
  const rootNode = nodes.find(n => n.id === "root" || n.type === "QUERY");

  const positions: Record<string, { x: number; y: number }> = {};
  if (rootNode) positions[rootNode.id] = { x: cx, y: 25 };

  nonRoot.forEach((n, i) => {
    const angle = (i / Math.max(nonRoot.length, 1)) * 2 * Math.PI - Math.PI / 2;
    positions[n.id] = {
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle) + 20
    };
  });

  return (
    <svg width="100%" height="230" viewBox="0 0 500 230" style={{ overflow: "visible" }}>
      {edges.slice(0, 20).map((e, i) => {
        const s = positions[e.source];
        const t = positions[e.target];
        if (!s || !t) return null;
        const strokeColor = e.type === "CONTRADICTS" ? "var(--error)"
          : e.type === "SUPPORTS" ? "var(--success)"
          : "var(--border-color)";
        return (
          <g key={i}>
            <line x1={s.x} y1={s.y} x2={t.x} y2={t.y}
              stroke={strokeColor} strokeWidth="1.5" strokeDasharray={e.type === "CONTRADICTS" ? "4 2" : "none"} opacity="0.6" />
          </g>
        );
      })}
      {nodes.map(n => {
        const p = positions[n.id];
        if (!p) return null;
        const color = NODE_TYPE_COLORS[n.type] || "var(--text-muted)";
        const size = n.type === "QUERY" ? 16 : 11;
        return (
          <g key={n.id}>
            <circle cx={p.x} cy={p.y} r={size} fill={color} opacity="0.9"
              style={{ filter: `drop-shadow(0 0 5px ${color})` }} />
            <text x={p.x} y={p.y + size + 12} textAnchor="middle"
              fill="var(--text-secondary)" fontSize="7.5" fontFamily="Inter">
              {n.label.slice(0, 18)}{n.label.length > 18 ? "…" : ""}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function ResearchWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const session_id = params.id as string;

  const [session, setSession] = useState<SessionDetail | null>(null);
  const [logs, setLogs] = useState<LogMessage[]>([]);
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; edges: GraphEdge[] }>({ nodes: [], edges: [] });
  const [replaySteps, setReplaySteps] = useState<ReplayStep[]>([]);
  const [running, setRunning] = useState(false);
  const [citationFormat, setCitationFormat] = useState<"APA" | "IEEE">("IEEE");
  const [uploadStatus, setUploadStatus] = useState("");
  const [activeTab, setActiveTab] = useState<TabType>("report");
  const [activeReplayStep, setActiveReplayStep] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const getToken = () => localStorage.getItem("intellex_token") ?? "";

  const fetchSessionDetails = useCallback(async (token: string) => {
    const res = await fetch(`${API_BASE}/api/sessions/${session_id}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (res.status === 401) { router.push("/login"); return; }
    if (!res.ok) return;
    setSession(await res.json());
  }, [session_id, router]);

  const fetchGraph = useCallback(async (token: string) => {
    const res = await fetch(`${API_BASE}/api/sessions/${session_id}/graph`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (res.ok) setGraphData(await res.json());
  }, [session_id]);

  const fetchReplay = useCallback(async (token: string) => {
    const res = await fetch(`${API_BASE}/api/sessions/${session_id}/replay`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (res.ok) {
      const data = await res.json();
      setReplaySteps(data.timeline || []);
    }
  }, [session_id]);

  useEffect(() => {
    const token = getToken();
    if (!token) { router.push("/login"); return; }
    Promise.all([
      fetchSessionDetails(token),
      fetchGraph(token),
      fetchReplay(token)
    ]);
  }, [session_id, router, fetchSessionDetails, fetchGraph, fetchReplay]);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const handleStartResearch = async () => {
    setRunning(true);
    setLogs([]);
    const token = getToken();
    if (!token) return;

    try {
      const url = `${API_BASE}/api/sessions/${session_id}/research?citation_format=${citationFormat}`;
      const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error("Research stream failed.");

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("data:")) {
            try {
              const parsed: LogMessage = JSON.parse(line.substring(5).trim());
              setLogs(prev => [...prev, parsed]);
            } catch { /* ignore malformed SSE */ }
          }
        }
      }

      // Refresh all data after pipeline completes
      await Promise.all([
        fetchSessionDetails(token),
        fetchGraph(token),
        fetchReplay(token)
      ]);
      setActiveTab("findings");
    } catch (err) {
      console.error(err);
    } finally {
      setRunning(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadStatus("Uploading...");
    const token = getToken();

    const formData = new FormData();
    formData.append("file", file);
    formData.append("session_id", session_id);

    try {
      const res = await fetch(`${API_BASE}/api/documents/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Upload failed.");
      }
      const data = await res.json();
      setUploadStatus(`✓ Parsed: ${data.filename} (${(data.size_bytes / 1024).toFixed(1)} KB, ${data.extracted_chars} chars)`);
      setTimeout(() => setUploadStatus(""), 5000);
    } catch (err: any) {
      setUploadStatus(`✗ ${err.message}`);
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const tabStyle = (tab: TabType) => ({
    padding: "0.5rem 1.25rem", fontSize: "0.88rem", fontWeight: "500",
    background: activeTab === tab ? "var(--accent-purple)" : "transparent",
    color: activeTab === tab ? "white" : "var(--text-muted)",
    border: `1px solid ${activeTab === tab ? "var(--accent-purple)" : "var(--border-color)"}`,
    borderRadius: "8px", cursor: "pointer", transition: "all 0.2s ease"
  });

  return (
    <>
      <nav className="navbar">
        <div className="logo-container" onClick={() => router.push("/")} style={{ cursor: "pointer" }}>
          <div className="logo-icon">IX</div>
          <span className="brand-name">Intellex Workspace</span>
        </div>
        <div className="nav-links">
          <button
            onClick={() => router.push("/")}
            className="btn"
            style={{ width: "auto", background: "none", border: "1px solid var(--border-color)", padding: "0.35rem 1rem", fontSize: "0.85rem" }}
          >
            ← Dashboard
          </button>
        </div>
      </nav>

      <div style={{ padding: "1.5rem 2rem", flex: 1, display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1.5rem", flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: "280px" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "600", letterSpacing: "0.08em" }}>
              Research Inquiry
            </span>
            <h1 style={{ fontSize: "1.6rem", marginTop: "0.3rem", lineHeight: "1.4" }}>
              {session?.original_query || "Loading..."}
            </h1>
            {session?.status && (
              <span style={{
                display: "inline-block", marginTop: "0.5rem",
                fontSize: "0.78rem", fontWeight: "600",
                color: VERIFICATION_COLORS[session.status] || "var(--text-muted)",
                background: "var(--bg-tertiary)", padding: "0.2rem 0.75rem", borderRadius: "12px"
              }}>
                Status: {session.status}
              </span>
            )}
          </div>

          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexShrink: 0 }}>
            <select
              value={citationFormat}
              onChange={(e) => setCitationFormat(e.target.value as "APA" | "IEEE")}
              className="form-input"
              style={{ width: "auto", padding: "0.5rem 1rem" }}
              disabled={running}
            >
              <option value="IEEE">IEEE</option>
              <option value="APA">APA</option>
            </select>
            <button
              id="execute-research-btn"
              onClick={handleStartResearch}
              className="btn btn-primary"
              style={{ width: "auto", padding: "0.6rem 1.5rem" }}
              disabled={running || session?.status === "COMPLETED"}
            >
              {running ? (
                <span style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{
                    width: "13px", height: "13px", border: "2px solid rgba(255,255,255,0.3)",
                    borderTopColor: "white", borderRadius: "50%", animation: "spin 0.8s linear infinite"
                  }} />
                  Running...
                </span>
              ) : session?.status === "COMPLETED" ? "✓ Completed" : "⚡ Execute Agents"}
            </button>
          </div>
        </div>

        {/* Main Workspace Grid */}
        <div className="workspace-grid">
          {/* LEFT: File Upload + Live Agent Log */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            {/* File Upload */}
            <div className="workspace-panel" style={{ minHeight: "160px", maxHeight: "200px" }}>
              <div className="panel-title">Source File Ingestion</div>
              <div className="file-dropzone" onClick={() => fileInputRef.current?.click()}>
                <p style={{ fontSize: "0.88rem" }}>Drop files or click to upload</p>
                <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                  PDF, DOCX, TXT, CSV · Max 10 MB
                </span>
                <input type="file" ref={fileInputRef} style={{ display: "none" }}
                  onChange={handleFileUpload} accept=".pdf,.docx,.txt,.csv,.png,.jpg,.jpeg" />
              </div>
              {uploadStatus && (
                <div style={{
                  fontSize: "0.82rem", textAlign: "center",
                  color: uploadStatus.startsWith("✓") ? "var(--success)" : uploadStatus.startsWith("✗") ? "var(--error)" : "var(--accent-cyan)"
                }}>
                  {uploadStatus}
                </div>
              )}
            </div>

            {/* Agent Activity Log */}
            <div className="workspace-panel" style={{ flex: 1 }}>
              <div className="panel-title">
                Agent Activity Timeline
                {running && (
                  <span style={{
                    width: "8px", height: "8px", borderRadius: "50%", background: "var(--success)",
                    display: "inline-block", marginLeft: "0.5rem",
                    boxShadow: "0 0 6px var(--success)", animation: "pulse-dot 1s ease infinite"
                  }} />
                )}
              </div>
              <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {logs.length === 0 ? (
                  <p style={{ color: "var(--text-muted)", fontSize: "0.88rem", textAlign: "center", marginTop: "2rem" }}>
                    No activity yet. Click "Execute Agents" to start.
                  </p>
                ) : (
                  <div className="timeline-list">
                    {logs.map((log, idx) => (
                      <div key={idx} className={`timeline-item ${idx === logs.length - 1 && running ? "active" : ""}`}>
                        <div className="timeline-dot" />
                        <div style={{
                          fontSize: "0.73rem", fontWeight: "600",
                          color: log.log_type === "ERROR" ? "var(--error)"
                            : log.log_type === "WARNING" ? "var(--warning)"
                            : "var(--accent-purple)"
                        }}>
                          {log.agent_name} · {log.agent_role}
                        </div>
                        <p style={{ fontSize: "0.83rem", color: "var(--text-primary)", marginTop: "0.15rem", lineHeight: "1.4" }}>
                          {log.message}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
                <div ref={logsEndRef} />
              </div>
            </div>
          </div>

          {/* RIGHT: Tab panel for Report / Findings / Graph / Replay */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {/* Tab bar */}
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              {(["report", "findings", "graph", "replay"] as TabType[]).map(tab => (
                <button key={tab} style={tabStyle(tab)} onClick={() => setActiveTab(tab)}>
                  {tab === "report" ? "📄 Report"
                    : tab === "findings" ? `🔍 Findings (${session?.findings?.length ?? 0})`
                    : tab === "graph" ? "🕸 Knowledge Graph"
                    : "⏮ Replay"}
                </button>
              ))}
            </div>

            {/* Tab Content */}
            <div className="workspace-panel" style={{ flex: 1, maxHeight: "calc(100vh - 320px)", overflowY: "auto" }}>
              {/* ── Report Tab ── */}
              {activeTab === "report" && (
                <div className="report-body">
                  {session?.report_markdown ? (
                    session.report_markdown.split("\n").map((line, idx) => {
                      if (line.startsWith("# ")) return <h1 key={idx}>{line.slice(2)}</h1>;
                      if (line.startsWith("## ")) return <h2 key={idx}>{line.slice(3)}</h2>;
                      if (line.startsWith("### ")) return <h3 key={idx}>{line.slice(4)}</h3>;
                      if (line.startsWith("- ")) return <li key={idx} style={{ marginLeft: "1.25rem" }}>{line.slice(2)}</li>;
                      if (line.startsWith("|")) return (
                        <div key={idx} style={{ fontFamily: "monospace", fontSize: "0.8rem", background: "var(--bg-tertiary)", padding: "0.25rem 0.5rem", borderLeft: "2px solid var(--accent-purple)", marginBottom: "2px" }}>
                          {line}
                        </div>
                      );
                      return <p key={idx}>{line}</p>;
                    })
                  ) : (
                    <p style={{ color: "var(--text-muted)", textAlign: "center", marginTop: "4rem" }}>
                      No report yet. Execute the agent pipeline above.
                    </p>
                  )}
                </div>
              )}

              {/* ── Findings Tab ── */}
              {activeTab === "findings" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  {!session?.findings?.length ? (
                    <p style={{ color: "var(--text-muted)", textAlign: "center", marginTop: "3rem" }}>
                      No findings yet.
                    </p>
                  ) : session.findings.map((f, idx) => (
                    <div key={f.id || idx} style={{
                      background: "var(--bg-primary)", border: "1px solid var(--border-color)",
                      borderRadius: "10px", padding: "1.25rem",
                      borderLeft: `3px solid ${VERIFICATION_COLORS[f.verification_status] || "var(--text-muted)"}`
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                        <span style={{ fontSize: "0.73rem", color: "var(--accent-purple)", fontWeight: "700", textTransform: "uppercase" }}>
                          Finding #{idx + 1}
                        </span>
                        <span style={{
                          fontSize: "0.73rem", fontWeight: "600", padding: "0.15rem 0.6rem",
                          borderRadius: "12px", border: `1px solid ${VERIFICATION_COLORS[f.verification_status] || "var(--text-muted)"}`,
                          color: VERIFICATION_COLORS[f.verification_status] || "var(--text-muted)"
                        }}>
                          {f.verification_status}
                        </span>
                      </div>
                      <p style={{ fontSize: "0.9rem", marginBottom: "0.75rem", lineHeight: "1.6" }}>{f.claim}</p>
                      <ConfidenceBar score={f.confidence_score} />
                      <div style={{ display: "flex", gap: "1.5rem", marginTop: "0.5rem", fontSize: "0.78rem", color: "var(--text-muted)" }}>
                        <span>Confidence: <strong style={{ color: "var(--text-primary)" }}>{f.confidence_score}%</strong></span>
                        <span>Sources: <strong style={{ color: "var(--text-primary)" }}>{f.source_count}</strong></span>
                        <span>Quality: <strong style={{ color: "var(--text-primary)" }}>{f.source_quality_score}/10</strong></span>
                      </div>
                      {f.consensus_rationale && (
                        <p style={{
                          marginTop: "0.75rem", fontSize: "0.8rem", color: "var(--text-muted)",
                          background: "var(--bg-tertiary)", padding: "0.5rem 0.75rem", borderRadius: "6px", lineHeight: "1.5"
                        }}>
                          <strong>Audit:</strong> {f.consensus_rationale}
                        </p>
                      )}
                      {f.citations?.length > 0 && (
                        <div style={{ marginTop: "0.75rem" }}>
                          {f.citations.slice(0, 2).map((c, ci) => (
                            <div key={c.id || ci} style={{ fontSize: "0.78rem", color: "var(--text-muted)", padding: "0.25rem 0" }}>
                              📎 {c.source_url ? (
                                <a href={c.source_url} target="_blank" rel="noopener noreferrer"
                                  style={{ color: "var(--accent-cyan)", textDecoration: "none" }}>
                                  {c.source_title}
                                </a>
                              ) : c.source_title}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* ── Knowledge Graph Tab ── */}
              {activeTab === "graph" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <SimpleGraph nodes={graphData.nodes} edges={graphData.edges} />
                  {/* Legend */}
                  <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    {Object.entries(NODE_TYPE_COLORS).map(([type, color]) => (
                      <span key={type} style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                        <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: color, display: "inline-block" }} />
                        {type}
                      </span>
                    ))}
                  </div>
                  <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                    {graphData.nodes.length} nodes · {graphData.edges.length} edges
                  </p>
                </div>
              )}

              {/* ── Replay Timeline Tab ── */}
              {activeTab === "replay" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  {!replaySteps.length ? (
                    <p style={{ color: "var(--text-muted)", textAlign: "center", marginTop: "3rem" }}>
                      No replay data. Execute the research pipeline to generate a timeline.
                    </p>
                  ) : replaySteps.map((step, idx) => (
                    <div key={idx}
                      onClick={() => setActiveReplayStep(activeReplayStep === idx ? null : idx)}
                      style={{
                        background: "var(--bg-primary)", border: `1px solid ${activeReplayStep === idx ? "var(--accent-purple)" : "var(--border-color)"}`,
                        borderRadius: "10px", padding: "1rem", cursor: "pointer",
                        transition: "border-color 0.2s ease"
                      }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <div>
                          <span style={{ fontSize: "0.73rem", color: "var(--accent-purple)", fontWeight: "700" }}>
                            Step {step.step_index}
                          </span>
                          <span style={{ marginLeft: "0.5rem", fontSize: "0.88rem", fontWeight: "600" }}>
                            {step.agent_name}
                          </span>
                          <span style={{ marginLeft: "0.5rem", fontSize: "0.78rem", color: "var(--text-muted)" }}>
                            · {step.agent_role}
                          </span>
                        </div>
                        <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                          {step.events.length} events {activeReplayStep === idx ? "▲" : "▼"}
                        </span>
                      </div>
                      {activeReplayStep === idx && (
                        <div style={{ marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                          {step.events.map((ev, ei) => (
                            <div key={ei} style={{
                              fontSize: "0.82rem", padding: "0.4rem 0.75rem",
                              background: "var(--bg-tertiary)", borderRadius: "6px",
                              color: ev.log_type === "ERROR" ? "var(--error)" : ev.log_type === "WARNING" ? "var(--warning)" : "var(--text-secondary)"
                            }}>
                              {ev.message}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse-dot { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
      `}</style>
    </>
  );
}
