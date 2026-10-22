"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isRegister, setIsRegister] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);

    const endpoint = isRegister ? "/api/auth/register" : "/api/auth/login";

    try {
      const payload = isRegister
        ? { email: email.trim(), password, role: "Researcher" }
        : { email: email.trim(), password };

      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Authentication request failed.");
      }

      if (isRegister) {
        setIsRegister(false);
        setSuccess("Account successfully registered! Logging you into your workspace...");
        // Auto-login
        const loginRes = await fetch(`${API_BASE}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: email.trim(), password })
        });
        if (loginRes.ok) {
          const data = await loginRes.json();
          localStorage.setItem("intellex_token", data.access_token);
          router.push("/");
          return;
        }
      } else {
        const data = await res.json();
        localStorage.setItem("intellex_token", data.access_token);
        router.push("/");
      }
    } catch (err: any) {
      setError(err.message || "Failed to authenticate.");
    } finally {
      setLoading(false);
    }
  };

  const handleQuickDemo = async () => {
    setError("");
    setSuccess("Connecting with Intellex demo researcher profile...");
    setLoading(true);

    const demoEmail = "researcher@intellex.ai";
    const demoPassword = "EnterpriseResearch2026!";

    try {
      // 1. Try login
      let res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: demoEmail, password: demoPassword })
      });

      // 2. If not found, register first then login
      if (res.status === 401 || res.status === 404) {
        await fetch(`${API_BASE}/api/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: demoEmail, password: demoPassword, role: "Lead Investigator" })
        });
        res = await fetch(`${API_BASE}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: demoEmail, password: demoPassword })
        });
      }

      if (!res.ok) {
        throw new Error("Unable to initialize demo session.");
      }

      const data = await res.json();
      localStorage.setItem("intellex_token", data.access_token);
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Demo login failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrapper" suppressHydrationWarning>
      <div className="auth-card" suppressHydrationWarning>
        <div className="auth-header">
          <div style={{ display: "flex", justifyContent: "center", marginBottom: "1rem" }}>
            <div className="logo-icon" style={{ width: "48px", height: "48px", fontSize: "1.2rem" }}>IX</div>
          </div>
          <h1 className="auth-title">Intellex</h1>
          <p style={{ color: "#a3a3a3", fontSize: "0.9rem", marginTop: "0.25rem" }}>
            Multi-Agent Autonomous Research Platform
          </p>
        </div>

        {error && (
          <div style={{
            background: "rgba(239, 68, 68, 0.12)",
            border: "1px solid var(--error)",
            color: "#ef4444",
            padding: "0.75rem 1rem",
            borderRadius: "8px",
            fontSize: "0.85rem",
            marginBottom: "1.25rem"
          }}>
            {error}
          </div>
        )}

        {success && (
          <div style={{
            background: "rgba(16, 185, 129, 0.12)",
            border: "1px solid var(--success)",
            color: "#10b981",
            padding: "0.75rem 1rem",
            borderRadius: "8px",
            fontSize: "0.85rem",
            marginBottom: "1.25rem"
          }}>
            {success}
          </div>
        )}

        <form onSubmit={handleAuth} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div className="form-group">
            <label className="form-label">Work Email</label>
            <input
              type="email"
              className="form-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="researcher@intellex.ai"
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              type="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              required
              minLength={6}
            />
          </div>

          <button type="submit" className="btn btn-primary" disabled={loading} style={{ marginTop: "0.5rem" }}>
            {loading ? "Authenticating..." : isRegister ? "Create Researcher Account" : "Access Workspace"}
          </button>
        </form>

        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", margin: "1.25rem 0" }}>
          <div style={{ flex: 1, height: "1px", background: "var(--border-color)" }} />
          <span style={{ fontSize: "0.75rem", color: "#a3a3a3", textTransform: "uppercase" }}>Or</span>
          <div style={{ flex: 1, height: "1px", background: "var(--border-color)" }} />
        </div>

        <button
          onClick={handleQuickDemo}
          className="btn"
          disabled={loading}
          style={{
            background: "#ffffff",
            border: "1px solid #ffffff",
            color: "#000000",
            fontWeight: "700"
          }}
        >
          🚀 1-Click Instant Demo Login
        </button>

        <div style={{ marginTop: "1.5rem", textAlign: "center", fontSize: "0.85rem" }}>
          <span style={{ color: "#a3a3a3" }}>
            {isRegister ? "Already registered with Intellex?" : "Need a new research profile?"}
          </span>{" "}
          <button
            onClick={() => {
              setIsRegister(!isRegister);
              setError("");
              setSuccess("");
            }}
            style={{
              background: "none",
              border: "none",
              color: "#ffffff",
              textDecoration: "underline",
              fontWeight: "700",
              cursor: "pointer"
            }}
          >
            {isRegister ? "Sign In" : "Register Profile"}
          </button>
        </div>
      </div>
    </div>
  );
}
