"use client";

import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { ReactFlow, Background, Controls } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { 
  Play, 
  Pause, 
  SkipBack, 
  SkipForward, 
  GitCompare, 
  X, 
  Link2, 
  Download,
  Copy,
  Printer,
  Check,
  Search,
  Filter,
  Sparkles,
  BookOpen,
  Activity,
  FileText
} from "lucide-react";

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
  authors?: string[];
  year?: string;
  journal?: string;
  doi?: string;
  source_type?: string;
}

interface Finding {
  id: string;
  finding_id?: string;
  claim: string;
  confidence_score: number;
  source_count: number;
  source_quality_score: number;
  verification_status: string;
  consensus_rationale?: string;
  supporting_sources?: string[];
  contradicting_sources?: string[];
  credibility_score?: number;
  reasoning_trace?: string;
  evidence_strength?: number;
  cross_source_agreement?: number;
  recency_score?: number;
  contradiction_penalty?: number;
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
  description?: string;
  metadata?: any;
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
  Topic: "#ffffff",
  Concept: "#c084fc",
  Source: "#38bdf8",
  Finding: "#10b981",
  Citation: "#f59e0b",
  Debate: "#f43f5e",
};

const VERIFICATION_COLORS: Record<string, string> = {
  VERIFIED: "#10b981",
  PARTIALLY_VERIFIED: "#38bdf8",
  CONFLICTING_EVIDENCE: "#f59e0b",
  INSUFFICIENT_EVIDENCE: "#ef4444",
  UNVERIFIED: "#a3a3a3",
};

const PIPELINE_STEPS = [
  { label: "CRO Planning", agent: "Chief Research Officer", icon: "🧠" },
  { label: "Evidence Retrieval", agent: "Evidence Layer", icon: "🌐" },
  { label: "Claim Synthesis", agent: "Analysis Agent", icon: "🔬" },
  { label: "Dialectic Debate", agent: "Debate & Contradiction Engine", icon: "⚡" },
  { label: "Fact Check Audit", agent: "Fact Checker", icon: "🛡" },
  { label: "Citation Indexing", agent: "Citation Broker", icon: "📚" },
  { label: "Knowledge Graph", agent: "Knowledge Graph Builder", icon: "🕸" },
  { label: "Dossier Assembly", agent: "Report Synthesis Agent", icon: "📄" },
];

function ConfidenceBar({ score }: { score: number }) {
  const pct = Math.min(100, Math.max(0, score));
  const color = pct >= 75 ? "#10b981" : pct >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ position: "relative", height: "6px", background: "#1c1c1c", borderRadius: "3px", overflow: "hidden" }}>
      <div style={{
        position: "absolute", left: 0, top: 0, bottom: 0,
        width: `${pct}%`, background: color,
        borderRadius: "3px", transition: "width 0.8s ease"
      }} />
    </div>
  );
}

function parseMarkdownReport(content: string) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let tableRows: string[] = [];
  let inTable = false;

  const flushTable = (keyPrefix: number) => {
    if (!tableRows.length) return;
    const headerRow = tableRows[0];
    const dataRows = tableRows.slice(2);
    
    const parseCells = (row: string) => row.split("|").filter((_, i, arr) => i > 0 && i < arr.length - 1).map(c => c.trim());
    const headers = parseCells(headerRow);

    elements.push(
      <div key={`table-${keyPrefix}`} style={{ overflowX: "auto", margin: "1.25rem 0", borderRadius: "8px", border: "1px solid var(--border-color)", background: "#050505" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
          <thead>
            <tr style={{ background: "#141414", borderBottom: "1px solid var(--border-color)", textAlign: "left" }}>
              {headers.map((h, hi) => (
                <th key={hi} style={{ padding: "0.85rem 1rem", fontWeight: "700", color: "#ffffff", letterSpacing: "0.02em" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dataRows.map((dr, dri) => {
              const cells = parseCells(dr);
              return (
                <tr key={dri} style={{ borderBottom: "1px solid #1a1a1a", background: dri % 2 === 0 ? "#000000" : "#090909" }}>
                  {cells.map((c, ci) => {
                    const isLink = c.includes("[") && c.includes("](") && c.includes(")");
                    return (
                      <td key={ci} style={{ padding: "0.75rem 1rem", color: "#e5e5e5", lineHeight: "1.5" }}>
                        {c.includes("[[") && c.includes("]]") ? (
                          <span style={{ color: "#ffffff", fontWeight: "700", textDecoration: "underline" }}>{c}</span>
                        ) : c.startsWith("**`") && c.endsWith("`**") ? (
                          <span style={{
                            padding: "0.2rem 0.6rem", borderRadius: "6px", fontSize: "0.75rem", fontWeight: "700",
                            background: "#171717", color: "#ffffff", border: "1px solid #333333"
                          }}>
                            {c.replace(/\*\*`|`\*\*/g, "")}
                          </span>
                        ) : c.startsWith("**") && c.endsWith("**") ? (
                          <strong style={{ color: "#ffffff", fontWeight: "700" }}>{c.replace(/\*\*/g, "")}</strong>
                        ) : isLink ? (
                          <span dangerouslySetInnerHTML={{
                            __html: c.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color:#ffffff;text-decoration:underline;font-weight:600;">$1 ↗</a>')
                          }} />
                        ) : (
                          c
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
    tableRows = [];
    inTable = false;
  };

  lines.forEach((line, idx) => {
    if (line.trim().startsWith("|")) {
      inTable = true;
      tableRows.push(line.trim());
    } else {
      if (inTable) flushTable(idx);
      if (line.startsWith("# ")) {
        elements.push(<h1 key={idx} style={{ fontSize: "1.85rem", fontWeight: "800", margin: "1.5rem 0 0.75rem", color: "#ffffff", letterSpacing: "-0.03em" }}>{line.slice(2)}</h1>);
      } else if (line.startsWith("## ")) {
        elements.push(<h2 key={idx} style={{ fontSize: "1.35rem", fontWeight: "700", margin: "1.5rem 0 0.5rem", color: "#ffffff", borderBottom: "1px solid var(--border-color)", paddingBottom: "0.4rem", letterSpacing: "-0.02em" }}>{line.slice(3)}</h2>);
      } else if (line.startsWith("### ")) {
        elements.push(<h3 key={idx} style={{ fontSize: "1.1rem", fontWeight: "700", margin: "1.1rem 0 0.35rem", color: "#ffffff" }}>{line.slice(4)}</h3>);
      } else if (line.startsWith("> ")) {
        elements.push(<blockquote key={idx} style={{ borderLeft: "3px solid #ffffff", paddingLeft: "1rem", margin: "0.75rem 0", color: "#d4d4d4", background: "#0d0d0d", padding: "0.6rem 1rem", borderRadius: "0 8px 8px 0", fontSize: "0.92rem" }}>{line.slice(2)}</blockquote>);
      } else if (line.startsWith("- ")) {
        const itemText = line.slice(2);
        elements.push(
          <li key={idx} style={{ marginLeft: "1.25rem", color: "#d4d4d4", lineHeight: "1.75", marginBottom: "0.35rem" }}>
            <span dangerouslySetInnerHTML={{
              __html: itemText
                .replace(/\*\*([^*]+)\*\*/g, '<strong style="color:#ffffff;font-weight:700;">$1</strong>')
                .replace(/`([^`]+)`/g, '<code style="background:#171717;border:1px solid #262626;padding:2px 6px;border-radius:4px;font-size:0.8rem;color:#ffffff;font-family:monospace;">$1</code>')
                .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color:#ffffff;text-decoration:underline;font-weight:600;">$1 ↗</a>')
            }} />
          </li>
        );
      } else if (line.trim() === "---") {
        elements.push(<hr key={idx} style={{ border: "none", borderTop: "1px solid var(--border-color)", margin: "1.5rem 0" }} />);
      } else if (line.trim()) {
        elements.push(
          <p key={idx} style={{ color: "#d4d4d4", lineHeight: "1.75", margin: "0.5rem 0" }}>
            <span dangerouslySetInnerHTML={{
              __html: line
                .replace(/\*\*([^*]+)\*\*/g, '<strong style="color:#ffffff;font-weight:700;">$1</strong>')
                .replace(/`([^`]+)`/g, '<code style="background:#171717;border:1px solid #262626;padding:2px 6px;border-radius:4px;font-size:0.8rem;color:#ffffff;font-family:monospace;">$1</code>')
                .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color:#ffffff;text-decoration:underline;font-weight:600;">$1 ↗</a>')
            }} />
          </p>
        );
      }
    }
  });
  if (inTable) flushTable(lines.length);
  return elements;
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
  const [findingFilter, setFindingFilter] = useState<string>("ALL");
  const [copyToast, setCopyToast] = useState(false);
  
  // Replay timeline playback state
  const [activeReplayStep, setActiveReplayStep] = useState<number | null>(null);
  const [playbackActive, setPlaybackActive] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);

  // Node details sidebar selection
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  // Session Comparison state
  const [sessionsList, setSessionsList] = useState<any[]>([]);
  const [selectedCompareSessionId, setSelectedCompareSessionId] = useState<string>("");
  const [comparisonResult, setComparisonResult] = useState<any>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const fetchSessionsList = useCallback(async (token: string) => {
    const res = await fetch(`${API_BASE}/api/sessions`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (res.ok) {
      const data = await res.json();
      setSessionsList(data.filter((s: any) => s.id !== session_id && s.status === "COMPLETED"));
    }
  }, [session_id]);

  useEffect(() => {
    const token = getToken();
    if (!token) { router.push("/login"); return; }
    fetchSessionDetails(token);
    fetchGraph(token);
    fetchReplay(token);
    fetchSessionsList(token);
  }, [session_id, router, fetchSessionDetails, fetchGraph, fetchReplay, fetchSessionsList]);

  // Compute current active agent index for the Stepper
  const currentPipelineIndex = useMemo(() => {
    if (session?.status === "COMPLETED") return 8;
    if (!logs.length) return -1;
    const lastLog = logs[logs.length - 1];
    const name = lastLog.agent_name.toLowerCase();
    if (name.includes("chief") || name.includes("cro")) return 0;
    if (name.includes("evidence") || name.includes("layer") || name.includes("retrieval")) return 1;
    if (name.includes("analysis") || name.includes("synthesizer")) return 2;
    if (name.includes("debate") || name.includes("contradiction")) return 3;
    if (name.includes("fact") || name.includes("checker") || name.includes("integrity")) return 4;
    if (name.includes("citation")) return 5;
    if (name.includes("graph")) return 6;
    if (name.includes("report") || name.includes("technical writer")) return 7;
    return 1;
  }, [logs, session?.status]);

  // Playback timer effect
  useEffect(() => {
    let timer: any;
    if (playbackActive && replaySteps.length) {
      timer = setInterval(() => {
        setActiveReplayStep(prev => {
          if (prev === null || prev >= replaySteps.length - 1) {
            setPlaybackActive(false);
            return replaySteps.length - 1;
          }
          return prev + 1;
        });
      }, 2500 / playbackSpeed);
    }
    return () => { if (timer) clearInterval(timer); };
  }, [playbackActive, playbackSpeed, replaySteps]);

  // Compute React Flow nodes and edges
  const reactFlowElements = useMemo(() => {
    if (!graphData.nodes.length) return { nodes: [], edges: [] };
    const nodes = graphData.nodes;
    const edges = graphData.edges;

    const rfNodes = nodes.map((node) => {
      let position = { x: 300, y: 300 };
      
      if (node.type === "Topic") {
        position = { x: 450, y: 40 };
      } else if (node.type === "Concept") {
        const cIdx = nodes.filter(n => n.type === "Concept").findIndex(n => n.id === node.id);
        position = { x: 120 + cIdx * 300, y: 160 };
      } else if (node.type === "Finding") {
        const fIdx = nodes.filter(n => n.type === "Finding").findIndex(n => n.id === node.id);
        position = { x: 180 + fIdx * 320, y: 320 };
      } else if (node.type === "Source") {
        const sIdx = nodes.filter(n => n.type === "Source").findIndex(n => n.id === node.id);
        position = { x: 40, y: 120 + sIdx * 120 };
      } else if (node.type === "Citation") {
        const citIdx = nodes.filter(n => n.type === "Citation").findIndex(n => n.id === node.id);
        position = { x: 140 + citIdx * 260, y: 500 };
      }

      const color = NODE_TYPE_COLORS[node.type] || "var(--accent-purple)";

      return {
        id: node.id,
        position,
        data: { label: node.label },
        type: "default",
        style: {
          background: "rgba(10, 12, 18, 0.95)",
          color: "var(--text-primary)",
          border: `2px solid ${color}`,
          borderRadius: "10px",
          padding: "10px 14px",
          fontSize: "11px",
          minWidth: "160px",
          maxWidth: "240px",
          boxShadow: `0 4px 15px rgba(0,0,0,0.4), 0 0 10px ${color}30`,
          cursor: "pointer",
          transition: "all 0.3s ease"
        }
      };
    });

    const rfEdges = edges.map((edge, idx) => {
      const isContradiction = edge.type === "CONTRADICTS";
      const isSupports = edge.type === "SUPPORTS";
      
      return {
        id: edge.id || `edge-${idx}`,
        source: edge.source,
        target: edge.target,
        animated: isSupports || isContradiction || playbackActive,
        type: "smoothstep",
        label: edge.type,
        style: {
          stroke: isContradiction ? "var(--error)" : isSupports ? "var(--success)" : "var(--border-color)",
          strokeWidth: isContradiction || isSupports ? 2.5 : 1.5,
          opacity: 0.85
        },
        labelStyle: { 
          fill: "var(--text-secondary)", 
          fontSize: 8, 
          fontWeight: "bold",
          background: "rgba(10, 12, 16, 0.9)", 
          borderRadius: "4px"
        }
      };
    });

    return { nodes: rfNodes, edges: rfEdges };
  }, [graphData, playbackActive]);

  const onNodeClick = useCallback((_event: any, node: any) => {
    const rawNode = graphData.nodes.find(n => n.id === node.id);
    if (rawNode) setSelectedNode(rawNode);
  }, [graphData]);

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

      await Promise.all([
        fetchSessionDetails(token),
        fetchGraph(token),
        fetchReplay(token)
      ]);
      setActiveTab("report");
    } catch (err) {
      console.error(err);
    } finally {
      setRunning(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadStatus("Uploading & parsing document...");
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
      setUploadStatus(`✓ Ingested: ${data.filename} (${(data.size_bytes / 1024).toFixed(1)} KB, ${data.extracted_chars} chars extracted)`);
      setTimeout(() => setUploadStatus(""), 6000);
    } catch (err: any) {
      setUploadStatus(`✗ ${err.message}`);
    }
  };

  const handleDownloadMarkdown = () => {
    if (!session?.report_markdown) return;
    const blob = new Blob([session.report_markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `intellex_dossier_${session_id.slice(0, 8)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadJSON = () => {
    if (!session) return;
    const payload = {
      session_id,
      query: session.original_query,
      status: session.status,
      findings: session.findings,
      graph: graphData,
      timeline: replaySteps,
      exported_at: new Date().toISOString()
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `intellex_dataset_${session_id.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleCopyReport = () => {
    if (!session?.report_markdown) return;
    navigator.clipboard.writeText(session.report_markdown);
    setCopyToast(true);
    setTimeout(() => setCopyToast(false), 3000);
  };

  const handleCompareSessions = async () => {
    if (!selectedCompareSessionId) return;
    const token = getToken();
    try {
      const res = await fetch(`${API_BASE}/api/sessions/${session_id}/compare/${selectedCompareSessionId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) setComparisonResult(await res.json());
    } catch (e) {
      console.error("Comparison request failed", e);
    }
  };

  const filteredFindings = useMemo(() => {
    if (!session?.findings) return [];
    if (findingFilter === "ALL") return session.findings;
    return session.findings.filter(f => f.verification_status === findingFilter);
  }, [session?.findings, findingFilter]);

  const tabStyle = (tab: TabType) => ({
    padding: "0.55rem 1.25rem", fontSize: "0.85rem", fontWeight: "600",
    background: activeTab === tab ? "#ffffff" : "#0d0d0d",
    color: activeTab === tab ? "#000000" : "#a3a3a3",
    border: `1px solid ${activeTab === tab ? "#ffffff" : "var(--border-color)"}`,
    borderRadius: "8px", cursor: "pointer", transition: "all 0.15s ease",
    display: "flex", alignItems: "center", gap: "0.5rem"
  });

  return (
    <>
      <nav className="navbar" suppressHydrationWarning>
        <div className="logo-container" onClick={() => router.push("/")} style={{ cursor: "pointer" }}>
          <div className="logo-icon">IX</div>
          <span className="brand-name">Intellex Workspace</span>
        </div>
        <div className="nav-links">
          <button
            onClick={() => router.push("/")}
            className="btn"
            style={{ width: "auto", background: "#111111", border: "1px solid var(--border-color)", color: "#ffffff", padding: "0.4rem 1.1rem", fontSize: "0.85rem" }}
          >
            ← Dashboard
          </button>
        </div>
      </nav>

      <div style={{ padding: "1.5rem 2rem", flex: 1, display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        {/* Header with Title & Action Controls */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1.5rem", flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: "280px" }}>
            <span style={{ fontSize: "0.75rem", color: "#a3a3a3", textTransform: "uppercase", fontWeight: "700", letterSpacing: "0.08em" }}>
              Active Research Inquiry
            </span>
            <h1 style={{ fontSize: "1.75rem", marginTop: "0.3rem", lineHeight: "1.35", fontWeight: "800", color: "#ffffff", letterSpacing: "-0.02em" }}>
              {session?.original_query || "Loading..."}
            </h1>
            <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginTop: "0.6rem" }}>
              {session?.status && (
                <span style={{
                  fontSize: "0.75rem", fontWeight: "700",
                  color: VERIFICATION_COLORS[session.status] || "#ffffff",
                  background: "#111111", padding: "0.25rem 0.85rem", borderRadius: "12px",
                  border: `1px solid ${VERIFICATION_COLORS[session.status] || "var(--border-color)"}`
                }}>
                  ● {session.status}
                </span>
              )}
              {session?.findings && (
                <span style={{ fontSize: "0.78rem", color: "#a3a3a3", fontWeight: "500" }}>
                  {session.findings.length} Empirical Assertions Synthesized
                </span>
              )}
            </div>
          </div>

          {/* Action Toolbar */}
          <div style={{ display: "flex", gap: "0.6rem", alignItems: "center", flexWrap: "wrap" }}>
            {session?.report_markdown && (
              <>
                <button
                  onClick={handleDownloadMarkdown}
                  className="btn"
                  title="Download Markdown Report"
                  style={{ width: "auto", padding: "0.5rem 0.85rem", fontSize: "0.8rem", background: "#111111", border: "1px solid #262626", color: "#ffffff" }}
                >
                  <Download size={14} /> Dossier (.md)
                </button>
                <button
                  onClick={handleDownloadJSON}
                  className="btn"
                  title="Download Raw JSON Data"
                  style={{ width: "auto", padding: "0.5rem 0.85rem", fontSize: "0.8rem", background: "#111111", border: "1px solid #262626", color: "#ffffff" }}
                >
                  <Download size={14} /> Data (.json)
                </button>
                <button
                  onClick={handleCopyReport}
                  className="btn"
                  title="Copy Report to Clipboard"
                  style={{ width: "auto", padding: "0.5rem 0.85rem", fontSize: "0.8rem", background: "#111111", border: "1px solid #262626", color: "#ffffff" }}
                >
                  {copyToast ? <Check size={14} color="#10b981" /> : <Copy size={14} />} {copyToast ? "Copied!" : "Copy"}
                </button>
                <button
                  onClick={() => window.print()}
                  className="btn"
                  title="Print / Save PDF"
                  style={{ width: "auto", padding: "0.5rem 0.85rem", fontSize: "0.8rem", background: "#111111", border: "1px solid #262626", color: "#ffffff" }}
                >
                  <Printer size={14} /> Print
                </button>
              </>
            )}

            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginLeft: "0.5rem" }}>
              <select
                value={citationFormat}
                onChange={(e) => setCitationFormat(e.target.value as "APA" | "IEEE")}
                className="form-input"
                style={{ width: "auto", padding: "0.45rem 0.75rem", fontSize: "0.82rem" }}
                disabled={running}
              >
                <option value="IEEE">IEEE Format</option>
                <option value="APA">APA Format</option>
              </select>
              <button
                id="execute-research-btn"
                onClick={handleStartResearch}
                className="btn btn-primary"
                style={{ width: "auto", padding: "0.55rem 1.4rem", fontWeight: "600", fontSize: "0.88rem" }}
                disabled={running || session?.status === "COMPLETED"}
              >
                {running ? (
                  <span style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span style={{
                      width: "12px", height: "12px", border: "2px solid rgba(255,255,255,0.3)",
                      borderTopColor: "white", borderRadius: "50%", animation: "spin 0.8s linear infinite"
                    }} />
                    Synthesizing...
                  </span>
                ) : session?.status === "COMPLETED" ? "✓ Investigation Complete" : "⚡ Run Autonomous Research"}
              </button>
            </div>
          </div>
        </div>

        {/* Live Multi-Agent Pipeline Stepper */}
        <div style={{
          background: "#0a0a0a",
          border: "1px solid var(--border-color)",
          borderRadius: "12px",
          padding: "0.85rem 1.25rem",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "0.75rem",
          overflowX: "auto"
        }}>
          {PIPELINE_STEPS.map((step, idx) => {
            const isCompleted = currentPipelineIndex > idx || session?.status === "COMPLETED";
            const isActive = currentPipelineIndex === idx && running;
            return (
              <div key={idx} style={{
                display: "flex", alignItems: "center", gap: "0.55rem", minWidth: "120px",
                opacity: isCompleted ? 1 : isActive ? 1 : 0.45,
                transition: "opacity 0.2s ease"
              }}>
                <div style={{
                  width: "28px", height: "28px", borderRadius: "50%",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: "0.8rem", fontWeight: "700",
                  background: isCompleted ? "#062e1e" : isActive ? "#ffffff" : "#141414",
                  color: isCompleted ? "#10b981" : isActive ? "#000000" : "#737373",
                  border: isCompleted ? "1.5px solid #10b981" : isActive ? "2px solid #ffffff" : "1px solid #262626",
                  boxShadow: isActive ? "0 0 12px rgba(255, 255, 255, 0.4)" : "none"
                }}>
                  {isCompleted ? "✓" : step.icon}
                </div>
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span style={{ fontSize: "0.75rem", fontWeight: "700", color: isCompleted ? "#ffffff" : isActive ? "#ffffff" : "#a3a3a3", whiteSpace: "nowrap" }}>
                    {step.label}
                  </span>
                  <span style={{ fontSize: "0.64rem", fontWeight: "500", color: isCompleted ? "#10b981" : isActive ? "#ffffff" : "#737373", whiteSpace: "nowrap" }}>
                    {isCompleted ? "Completed" : isActive ? "Executing..." : "Queued"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Workspace Body: Left Log & Ingestion / Right Intelligence Views */}
        <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", gap: "1.25rem", minHeight: "calc(100vh - 270px)" }}>
          {/* LEFT: File Ingestion + Activity Timeline */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {/* File Dropzone */}
            <div className="workspace-panel" style={{ padding: "1.1rem" }}>
              <div className="panel-title" style={{ fontSize: "0.82rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-secondary)" }}>
                Proprietary Evidence Ingestion
              </div>
              <div style={{ marginTop: "0.6rem" }}>
                <div
                  className="file-dropzone"
                  onClick={() => fileInputRef.current?.click()}
                  style={{ padding: "0.9rem", textAlign: "center", cursor: "pointer", borderRadius: "8px", border: "1px dashed var(--border-color)", background: "rgba(255,255,255,0.01)" }}
                >
                  <p style={{ fontSize: "0.82rem", fontWeight: "500", color: "var(--text-primary)" }}>Attach Papers or Datasets</p>
                  <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                    PDF, DOCX, TXT, CSV · Auto-chunked & matched
                  </span>
                  <input type="file" ref={fileInputRef} style={{ display: "none" }}
                    onChange={handleFileUpload} accept=".pdf,.docx,.txt,.csv,.png,.jpg,.jpeg" />
                </div>
                {uploadStatus && (
                  <div style={{
                    marginTop: "0.6rem", fontSize: "0.75rem", padding: "0.5rem 0.75rem", borderRadius: "6px",
                    background: "var(--bg-tertiary)",
                    color: uploadStatus.startsWith("✓") ? "var(--success)" : uploadStatus.startsWith("✗") ? "var(--error)" : "var(--accent-cyan)"
                  }}>
                    {uploadStatus}
                  </div>
                )}
              </div>
            </div>

            {/* Live Agent Activity Timeline */}
            <div className="workspace-panel" style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: "380px" }}>
              <div className="panel-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span>Agent Execution Stream</span>
                {running && (
                  <span style={{
                    width: "8px", height: "8px", borderRadius: "50%", background: "var(--success)",
                    boxShadow: "0 0 8px var(--success)", display: "inline-block"
                  }} />
                )}
              </div>
              <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.65rem", marginTop: "0.75rem" }}>
                {logs.length === 0 ? (
                  <p style={{ color: "var(--text-muted)", fontSize: "0.82rem", textAlign: "center", marginTop: "4rem", lineHeight: "1.6" }}>
                    No execution events.<br />Click <strong>Run Autonomous Research</strong> to trigger multi-agent pipeline.
                  </p>
                ) : (
                  <div className="timeline-list">
                    {logs.map((log, idx) => (
                      <div key={idx} className="timeline-item">
                        <div className="timeline-dot" style={{
                          background: log.log_type === "ERROR" ? "var(--error)" : log.log_type === "PROGRESS" ? "var(--accent-cyan)" : "var(--accent-purple)"
                        }} />
                        <div style={{
                          fontSize: "0.72rem", fontWeight: "700",
                          color: log.log_type === "ERROR" ? "var(--error)" : "var(--accent-purple)"
                        }}>
                          {log.agent_name}
                        </div>
                        <p style={{ fontSize: "0.8rem", color: "var(--text-primary)", marginTop: "0.15rem", lineHeight: "1.45" }}>
                          {log.message}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* RIGHT: Main Workspace Tabs */}
          <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
            {/* Tab Navigation */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                {(["report", "findings", "graph", "replay"] as TabType[]).map(tab => (
                  <button key={tab} style={tabStyle(tab)} onClick={() => setActiveTab(tab)}>
                    {tab === "report" && <FileText size={15} />}
                    {tab === "findings" && <Search size={15} />}
                    {tab === "graph" && <Sparkles size={15} />}
                    {tab === "replay" && <Activity size={15} />}
                    {tab === "report" ? "Research Dossier"
                      : tab === "findings" ? `Empirical Findings (${session?.findings?.length ?? 0})`
                      : tab === "graph" ? "Knowledge Graph"
                      : "Audit Replay"}
                  </button>
                ))}
              </div>

              {activeTab === "findings" && (
                <div style={{ display: "flex", gap: "0.3rem", alignItems: "center" }}>
                  <Filter size={13} color="var(--text-muted)" />
                  {["ALL", "VERIFIED", "CONFLICTING_EVIDENCE", "INSUFFICIENT_EVIDENCE"].map(status => (
                    <button
                      key={status}
                      onClick={() => setFindingFilter(status)}
                      style={{
                        background: findingFilter === status ? "var(--bg-tertiary)" : "transparent",
                        border: `1px solid ${findingFilter === status ? "var(--accent-purple)" : "var(--border-color)"}`,
                        color: findingFilter === status ? "var(--text-primary)" : "var(--text-muted)",
                        borderRadius: "6px", padding: "0.2rem 0.5rem", fontSize: "0.72rem", cursor: "pointer"
                      }}
                    >
                      {status === "ALL" ? "All Claims" : status.replace("_", " ")}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Tab Content Panes */}
            <div className="workspace-panel" style={{ flex: 1, maxHeight: "calc(100vh - 260px)", overflowY: "auto", padding: "1.5rem" }}>
              {/* 1. Report Tab */}
              {activeTab === "report" && (
                <div className="report-body">
                  {session?.report_markdown ? (
                    parseMarkdownReport(session.report_markdown)
                  ) : (
                    <div style={{ textAlign: "center", padding: "6rem 2rem", color: "var(--text-muted)" }}>
                      <FileText size={40} style={{ opacity: 0.3, marginBottom: "1rem" }} />
                      <h3 style={{ color: "var(--text-primary)", fontSize: "1.1rem" }}>No Research Dossier Generated</h3>
                      <p style={{ fontSize: "0.85rem", marginTop: "0.4rem" }}>
                        Click <strong>Run Autonomous Research</strong> to trigger evidence retrieval, contradiction arbitration, and report synthesis.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* 2. Findings Tab */}
              {activeTab === "findings" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  {/* Knowledge Evolution Comparison Selector */}
                  {sessionsList.length > 0 && (
                    <div style={{
                      background: "rgba(255,255,255,0.02)", border: "1px solid var(--border-color)",
                      borderRadius: "10px", padding: "0.75rem 1rem", display: "flex", justifyContent: "space-between",
                      alignItems: "center", gap: "1rem", flexWrap: "wrap"
                    }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <GitCompare size={15} color="var(--accent-purple)" />
                        <span style={{ fontSize: "0.82rem", fontWeight: "600" }}>Knowledge Evolution Comparison</span>
                      </div>
                      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                        <select
                          value={selectedCompareSessionId}
                          onChange={(e) => setSelectedCompareSessionId(e.target.value)}
                          className="form-input"
                          style={{ width: "200px", padding: "0.25rem 0.5rem", fontSize: "0.78rem" }}
                        >
                          <option value="">Compare with past session...</option>
                          {sessionsList.map(s => (
                            <option key={s.id} value={s.id}>{s.original_query.slice(0, 35)}...</option>
                          ))}
                        </select>
                        <button
                          onClick={handleCompareSessions}
                          className="btn btn-primary"
                          style={{ width: "auto", padding: "0.3rem 0.85rem", fontSize: "0.78rem" }}
                          disabled={!selectedCompareSessionId}
                        >
                          Compare
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Comparison Result Drawer */}
                  {comparisonResult && (
                    <div style={{
                      background: "rgba(138, 43, 226, 0.06)", border: "1px solid var(--accent-purple)",
                      borderRadius: "10px", padding: "1rem", position: "relative"
                    }}>
                      <button
                        onClick={() => setComparisonResult(null)}
                        style={{ position: "absolute", right: "12px", top: "12px", background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}
                      >
                        <X size={16} />
                      </button>
                      <h4 style={{ fontSize: "0.88rem", color: "var(--accent-purple)", marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                        <GitCompare size={14} /> Knowledge Shift Analysis
                      </h4>
                      <div style={{ display: "flex", gap: "1.25rem", fontSize: "0.78rem", color: "var(--text-muted)", marginBottom: "0.6rem" }}>
                        <span>New Assertions: <strong style={{ color: "var(--success)" }}>{comparisonResult.summary.total_new}</strong></span>
                        <span>Retracted: <strong style={{ color: "var(--error)" }}>{comparisonResult.summary.total_removed}</strong></span>
                        <span>Confidence Fluctuations: <strong style={{ color: "var(--warning)" }}>{comparisonResult.summary.total_changed}</strong></span>
                      </div>
                    </div>
                  )}

                  {/* Findings Cards */}
                  {!filteredFindings.length ? (
                    <p style={{ color: "var(--text-muted)", textAlign: "center", padding: "3rem" }}>
                      No findings match the selected filter.
                    </p>
                  ) : filteredFindings.map((f, idx) => (
                    <div key={f.id || idx} style={{
                      background: "#080808", border: "1px solid #262626",
                      borderRadius: "10px", padding: "1.25rem",
                      borderLeft: `3px solid ${VERIFICATION_COLORS[f.verification_status] || "#737373"}`
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                        <span style={{ fontSize: "0.74rem", color: "#ffffff", fontWeight: "800", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                          Finding #{idx + 1}
                        </span>
                        <span style={{
                          fontSize: "0.72rem", fontWeight: "700", padding: "0.2rem 0.75rem",
                          borderRadius: "12px", border: `1px solid ${VERIFICATION_COLORS[f.verification_status] || "#404040"}`,
                          color: VERIFICATION_COLORS[f.verification_status] || "#ffffff",
                          background: "#111111"
                        }}>
                          {f.verification_status}
                        </span>
                      </div>

                      <p style={{ fontSize: "0.95rem", fontWeight: "600", marginBottom: "0.75rem", lineHeight: "1.6", color: "#ffffff" }}>
                        {f.claim}
                      </p>
                      
                      <ConfidenceBar score={f.confidence_score} />
                      
                      <div style={{ display: "flex", gap: "1.25rem", flexWrap: "wrap", marginTop: "0.75rem", fontSize: "0.78rem", color: "#a3a3a3" }}>
                        <span>Confidence: <strong style={{ color: "#ffffff" }}>{f.confidence_score}%</strong></span>
                        <span>Source Authority: <strong style={{ color: "#ffffff" }}>{f.credibility_score ?? 80}%</strong></span>
                        <span>Corroborating Sources: <strong style={{ color: "#ffffff" }}>{f.supporting_sources?.length || f.source_count || 1}</strong></span>
                      </div>

                      {f.reasoning_trace && (
                        <div style={{
                          marginTop: "0.85rem", fontSize: "0.82rem", color: "#e5e5e5",
                          background: "#111111", border: "1px solid #262626", padding: "0.75rem 1rem", borderRadius: "6px", lineHeight: "1.6"
                        }}>
                          <strong style={{ color: "#ffffff", marginRight: "0.35rem" }}>Audit Rationale:</strong> {f.reasoning_trace}
                          {f.evidence_strength !== undefined && (
                            <div style={{ display: "flex", gap: "1.25rem", marginTop: "8px", fontSize: "0.75rem", borderTop: "1px solid #222222", paddingTop: "8px", color: "#a3a3a3", flexWrap: "wrap" }}>
                              <span>Evidence Depth: <strong style={{ color: "#ffffff" }}>{f.evidence_strength}%</strong></span>
                              <span>Agreement: <strong style={{ color: "#ffffff" }}>{f.cross_source_agreement ?? 100}%</strong></span>
                              <span>Recency: <strong style={{ color: "#ffffff" }}>{f.recency_score ?? 90}%</strong></span>
                              {f.contradiction_penalty ? <span style={{ color: "#ef4444", fontWeight: "600" }}>Contradiction Penalty: -{f.contradiction_penalty} pts</span> : null}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Supporting URLs & Citations */}
                      {f.supporting_sources && f.supporting_sources.length > 0 && (
                        <div style={{ marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                          <span style={{ fontSize: "0.72rem", color: "#a3a3a3", textTransform: "uppercase", fontWeight: "700" }}>Verified Source References:</span>
                          {f.supporting_sources.map((url, ui) => (
                            <a
                              key={ui}
                              href={url}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{ display: "inline-flex", alignItems: "center", gap: "6px", fontSize: "0.78rem", color: "#ffffff", textDecoration: "underline", fontWeight: "500" }}
                            >
                              <Link2 size={12} color="#a3a3a3" /> {url}
                            </a>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* 3. Knowledge Graph Tab */}
              {activeTab === "graph" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem", height: "100%" }}>
                  <div style={{ display: "flex", gap: "1rem", height: "480px" }}>
                    <div style={{
                      flex: 1, position: "relative", border: "1px solid var(--border-color)",
                      borderRadius: "12px", overflow: "hidden", background: "radial-gradient(circle, rgba(138, 43, 226, 0.03) 0%, transparent 80%)"
                    }}>
                      {reactFlowElements.nodes.length ? (
                        <ReactFlow
                          nodes={reactFlowElements.nodes}
                          edges={reactFlowElements.edges}
                          onNodeClick={onNodeClick}
                          fitView
                        >
                          <Background color="var(--border-color)" gap={16} size={1} />
                          <Controls />
                        </ReactFlow>
                      ) : (
                        <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", textAlign: "center", padding: "8rem 2rem" }}>
                          Knowledge graph will render after research execution completes.
                        </p>
                      )}
                    </div>

                    {/* Node Details Inspector Sidebar */}
                    <div style={{
                      width: "250px", background: "rgba(255, 255, 255, 0.02)",
                      border: "1px solid var(--border-color)", borderRadius: "12px",
                      padding: "1rem", display: "flex", flexDirection: "column", gap: "0.75rem", overflowY: "auto"
                    }}>
                      <div style={{ fontSize: "0.78rem", fontWeight: "700", textTransform: "uppercase", color: "var(--accent-purple)", borderBottom: "1px solid var(--border-color)", paddingBottom: "0.4rem" }}>
                        Node Inspector
                      </div>
                      
                      {!selectedNode ? (
                        <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", lineHeight: "1.5" }}>
                          Click any node in the graph workspace to inspect its source attribution, authority rating, or evidence verification trace.
                        </p>
                      ) : (
                        <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                          <div>
                            <span style={{ fontSize: "0.68rem", textTransform: "uppercase", color: "var(--text-muted)" }}>Type</span>
                            <div style={{ fontSize: "0.8rem", fontWeight: "600", color: NODE_TYPE_COLORS[selectedNode.type] }}>
                              {selectedNode.type}
                            </div>
                          </div>

                          <div>
                            <span style={{ fontSize: "0.68rem", textTransform: "uppercase", color: "var(--text-muted)" }}>Label</span>
                            <div style={{ fontSize: "0.78rem", color: "var(--text-primary)", fontWeight: "500", wordBreak: "break-word" }}>
                              {selectedNode.label}
                            </div>
                          </div>

                          {selectedNode.description && (
                            <div>
                              <span style={{ fontSize: "0.68rem", textTransform: "uppercase", color: "var(--text-muted)" }}>Content Summary</span>
                              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", lineHeight: "1.4", wordBreak: "break-word", maxHeight: "140px", overflowY: "auto" }}>
                                {selectedNode.description}
                              </div>
                            </div>
                          )}

                          {selectedNode.metadata?.url && (
                            <div style={{ borderTop: "1px solid var(--border-color)", paddingTop: "0.5rem" }}>
                              <a href={selectedNode.metadata.url} target="_blank" rel="noopener noreferrer" style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "0.75rem", color: "var(--accent-cyan)", textDecoration: "none" }}>
                                <Link2 size={12} /> Direct Citation Link
                              </a>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Graph Legend */}
                  <div style={{ display: "flex", gap: "1.25rem", flexWrap: "wrap", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    {Object.entries(NODE_TYPE_COLORS).map(([type, color]) => (
                      <span key={type} style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                        <span style={{ width: "9px", height: "9px", borderRadius: "50%", background: color, display: "inline-block" }} />
                        {type}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* 4. Replay Tab */}
              {activeTab === "replay" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  {!replaySteps.length ? (
                    <p style={{ color: "var(--text-muted)", textAlign: "center", marginTop: "3rem" }}>
                      No replay events available.
                    </p>
                  ) : (
                    <>
                      {/* Playback Toolbar */}
                      <div style={{
                        background: "var(--bg-tertiary)", border: "1px solid var(--border-color)",
                        borderRadius: "10px", padding: "0.75rem 1.25rem", display: "flex",
                        alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem"
                      }}>
                        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                          <button
                            onClick={() => setActiveReplayStep(prev => prev === null || prev === 0 ? 0 : prev - 1)}
                            className="btn"
                            style={{ width: "auto", padding: "0.4rem", background: "none", border: "1px solid var(--border-color)" }}
                            disabled={activeReplayStep === 0 || activeReplayStep === null}
                          >
                            <SkipBack size={14} />
                          </button>

                          <button
                            onClick={() => setPlaybackActive(!playbackActive)}
                            className="btn btn-primary"
                            style={{ width: "auto", padding: "0.4rem 0.9rem", fontSize: "0.78rem" }}
                          >
                            {playbackActive ? <Pause size={14} /> : <Play size={14} />} {playbackActive ? "Pause" : "Play Timeline"}
                          </button>

                          <button
                            onClick={() => setActiveReplayStep(prev => prev === null ? 0 : Math.min(replaySteps.length - 1, prev + 1))}
                            className="btn"
                            style={{ width: "auto", padding: "0.4rem", background: "none", border: "1px solid var(--border-color)" }}
                            disabled={activeReplayStep === replaySteps.length - 1}
                          >
                            <SkipForward size={14} />
                          </button>
                        </div>

                        <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                          Step {activeReplayStep !== null ? activeReplayStep + 1 : 1} of {replaySteps.length}
                        </span>
                      </div>

                      {/* Step Details */}
                      {activeReplayStep !== null && replaySteps[activeReplayStep] && (
                        <div style={{ background: "var(--bg-primary)", border: "1px solid var(--border-color)", borderRadius: "10px", padding: "1.25rem" }}>
                          <h4 style={{ color: "var(--accent-purple)", fontSize: "0.95rem", marginBottom: "0.5rem" }}>
                            {replaySteps[activeReplayStep].agent_name} · {replaySteps[activeReplayStep].agent_role}
                          </h4>
                          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                            {replaySteps[activeReplayStep].events.map((e, ei) => (
                              <div key={ei} style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: "1.5" }}>
                                • {e.message}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
