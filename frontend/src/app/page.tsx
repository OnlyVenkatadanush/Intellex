"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

interface SessionItem {
  id: string;
  original_query: string;
  status: string;
  created_at: string;
}

interface MemoryItem {
  id: string;
  content: string;
  created_at: string | null;
}

interface UserProfile {
  id: string;
  email: string;
  role: string;
}

function getStatusColor(status: string): string {
  switch (status) {
    case "COMPLETED": return "var(--success)";
    case "FAILED": return "var(--error)";
    case "PLANNING": case "RESEARCHING": case "DEBATING": return "var(--warning)";
    default: return "var(--text-muted)";
  }
}

export default function DashboardPage() {
  const [query, setQuery] = useState("");
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const router = useRouter();

  const getToken = () => localStorage.getItem("intellex_token") ?? "";

  const fetchProfile = useCallback(async (token: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) setUser(await res.json());
    } catch { /* non-fatal */ }
  }, []);

  // ── REAL session history fetch (no more fake data) ──────────────────────────
  const fetchSessions = useCallback(async (token: string) => {
    const res = await fetch(`${API_BASE}/api/sessions/?limit=50`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (res.status === 401) {
      localStorage.removeItem("intellex_token");
      router.push("/login");
      return;
    }
    if (!res.ok) throw new Error("Failed to fetch sessions.");
    setSessions(await res.json());
  }, [router]);

  const fetchMemories = useCallback(async (token: string) => {
    try {
      // Fetch memories using a dummy session approach — or user-level
      const sessRes = await fetch(`${API_BASE}/api/sessions/?limit=1`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!sessRes.ok) return;
      const sessData: SessionItem[] = await sessRes.json();
      if (sessData.length === 0) return;

      // Get memories from first completed session
      const completedSess = sessData.find(s => s.status === "COMPLETED");
      if (!completedSess) return;

      const memRes = await fetch(`${API_BASE}/api/sessions/${completedSess.id}/memory`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (memRes.ok) {
        const memData = await memRes.json();
        setMemories(memData.memories || []);
      }
    } catch { /* non-fatal */ }
  }, []);

  useEffect(() => {
    const token = getToken();
    if (!token) { router.push("/login"); return; }

    Promise.all([
      fetchProfile(token),
      fetchSessions(token),
      fetchMemories(token),
    ])
      .catch(err => setError(err.message || "Failed to load workspace."))
      .finally(() => setLoading(false));
  }, [router, fetchProfile, fetchSessions, fetchMemories]);

  const handleCreateSession = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setCreating(true);
    setError("");

    try {
      const res = await fetch(`${API_BASE}/api/sessions/create`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${getToken()}`
        },
        body: JSON.stringify({ original_query: query.trim() })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to initialize session.");
      }
      const newSess: SessionItem = await res.json();
      setSessions(prev => [newSess, ...prev]);
      setQuery("");
      router.push(`/research/${newSess.id}`);
    } catch (err: any) {
      setError(err.message || "Failed to create session.");
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    setDeletingId(sessionId);
    try {
      await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${getToken()}` }
      });
      setSessions(prev => prev.filter(s => s.id !== sessionId));
    } catch {
      setError("Failed to delete session.");
    } finally {
      setDeletingId(null);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("intellex_token");
    router.push("/login");
  };

  return (
    <>
      {/* ── Navbar ── */}
      <nav className="navbar">
        <div className="logo-container">
          <div className="logo-icon">IX</div>
          <span className="brand-name">Intellex</span>
        </div>
        <div className="nav-links">
          {user && (
            <span className="user-badge">
              {user.email} · {user.role}
            </span>
          )}
          <button
            onClick={handleLogout}
            style={{
              background: "none", border: "none",
              color: "var(--text-muted)", cursor: "pointer", fontSize: "0.9rem"
            }}
          >
            Sign Out
          </button>
        </div>
      </nav>

      <div className="dashboard-grid">
        {/* ── Sidebar: Real Session History ── */}
        <aside className="sidebar">
          <h3 style={{
            fontSize: "0.85rem", color: "var(--text-muted)",
            textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: "600"
          }}>
            Research History
          </h3>

          {loading ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {[...Array(3)].map((_, i) => (
                <div key={i} style={{
                  height: "60px", background: "var(--bg-tertiary)",
                  borderRadius: "8px", opacity: 0.6,
                  animation: "pulse 1.5s ease-in-out infinite"
                }} />
              ))}
            </div>
          ) : sessions.length === 0 ? (
            <p style={{ color: "var(--text-muted)", fontSize: "0.88rem", lineHeight: "1.6" }}>
              No research sessions yet. Launch your first query above to begin.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {sessions.map((s) => (
                <div
                  key={s.id}
                  className="session-item"
                  style={{ position: "relative" }}
                  onClick={() => router.push(`/research/${s.id}`)}
                >
                  <span style={{
                    fontSize: "0.88rem", color: "var(--text-primary)",
                    fontWeight: "500", display: "-webkit-box",
                    WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
                    overflow: "hidden"
                  }}>
                    {s.original_query}
                  </span>
                  <div style={{
                    display: "flex", justifyContent: "space-between",
                    alignItems: "center", marginTop: "0.35rem"
                  }}>
                    <span style={{ fontSize: "0.72rem", color: getStatusColor(s.status), fontWeight: "500" }}>
                      ● {s.status}
                    </span>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                        {new Date(s.created_at).toLocaleDateString()}
                      </span>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDeleteSession(s.id); }}
                        disabled={deletingId === s.id}
                        style={{
                          background: "none", border: "none", cursor: "pointer",
                          color: "var(--text-muted)", fontSize: "0.75rem",
                          padding: "2px 4px", borderRadius: "4px",
                          opacity: deletingId === s.id ? 0.4 : 1,
                          transition: "color 0.2s"
                        }}
                        title="Delete session"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </aside>

        {/* ── Main Content ── */}
        <main className="main-content">
          {/* Hero Query Card */}
          <div style={{
            background: "linear-gradient(135deg, rgba(138, 43, 226, 0.1), rgba(0, 255, 255, 0.05))",
            border: "1px solid var(--border-color)", borderRadius: "16px",
            padding: "2.5rem", display: "flex", flexDirection: "column", gap: "1.25rem",
            boxShadow: "0 4px 30px rgba(0,0,0,0.2)"
          }}>
            <h1 style={{ fontSize: "2.25rem", fontWeight: "700" }}>
              Launch Autonomous Research
            </h1>
            <p style={{ color: "var(--text-secondary)", fontSize: "1rem", lineHeight: "1.7" }}>
              Formulate a research question — the multi-agent system will gather evidence from arXiv, PubMed, and web sources, debate contradictions, fact-check every claim, and synthesize a structured report.
            </p>

            {error && (
              <div style={{
                background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.3)",
                borderRadius: "8px", padding: "0.75rem 1rem",
                color: "var(--error)", fontSize: "0.9rem"
              }}>
                {error}
              </div>
            )}

            <form onSubmit={handleCreateSession} style={{ marginTop: "0.5rem" }}>
              <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                <input
                  id="research-query-input"
                  type="text"
                  className="form-input"
                  style={{ flex: 1, minWidth: "280px", padding: "1rem 1.25rem", fontSize: "1.05rem" }}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="e.g. Does aerobic exercise reduce the risk of Alzheimer's disease?"
                  required
                  maxLength={1000}
                  disabled={creating}
                />
                <button
                  id="launch-research-btn"
                  type="submit"
                  className="btn btn-primary"
                  style={{ width: "auto", padding: "0 2rem", minWidth: "160px" }}
                  disabled={creating || !query.trim()}
                >
                  {creating ? (
                    <span style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span style={{
                        width: "14px", height: "14px", border: "2px solid rgba(255,255,255,0.3)",
                        borderTopColor: "white", borderRadius: "50%",
                        animation: "spin 0.8s linear infinite"
                      }} />
                      Launching...
                    </span>
                  ) : "⚡ Launch Research"}
                </button>
              </div>
            </form>

            {/* Stats Row */}
            <div style={{ display: "flex", gap: "2rem", marginTop: "0.5rem" }}>
              {[
                { label: "Total Sessions", value: sessions.length },
                { label: "Completed", value: sessions.filter(s => s.status === "COMPLETED").length },
                { label: "Memory Records", value: memories.length },
              ].map(stat => (
                <div key={stat.label} style={{ textAlign: "center" }}>
                  <div style={{
                    fontSize: "1.75rem", fontWeight: "700",
                    background: "linear-gradient(135deg, var(--accent-purple), var(--accent-cyan))",
                    WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent"
                  }}>
                    {stat.value}
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.15rem" }}>
                    {stat.label}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Memory Bank — Real Data */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <h2 style={{ fontSize: "1.3rem", color: "var(--text-primary)" }}>
              Research Memory Bank
              <span style={{
                marginLeft: "0.75rem", fontSize: "0.8rem",
                color: "var(--text-muted)", fontWeight: "400"
              }}>
                Verified facts from past research sessions
              </span>
            </h2>

            <div style={{
              background: "var(--bg-secondary)", border: "1px solid var(--border-color)",
              borderRadius: "12px", padding: "1.5rem",
              display: "flex", flexDirection: "column", gap: "0.75rem"
            }}>
              {memories.length === 0 ? (
                <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
                  No verified memories yet. Complete a research session to build your knowledge base.
                </p>
              ) : (
                memories.slice(0, 5).map((mem, idx) => (
                  <div key={mem.id} style={{
                    padding: "1rem", background: "var(--bg-tertiary)",
                    borderRadius: "8px", border: "1px solid var(--border-color)",
                    borderLeft: "3px solid var(--accent-purple)"
                  }}>
                    <span style={{
                      fontSize: "0.72rem", color: "var(--accent-purple)",
                      fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.05em"
                    }}>
                      Memory #{idx + 1}
                    </span>
                    <p style={{ fontSize: "0.9rem", color: "var(--text-primary)", marginTop: "0.35rem", lineHeight: "1.5" }}>
                      {mem.content}
                    </p>
                    {mem.created_at && (
                      <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "0.35rem", display: "block" }}>
                        {new Date(mem.created_at).toLocaleString()}
                      </span>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </main>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse {
          0%, 100% { opacity: 0.4; }
          50% { opacity: 0.7; }
        }
      `}</style>
    </>
  );
}
