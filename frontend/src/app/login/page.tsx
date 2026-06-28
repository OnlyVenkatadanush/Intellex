"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isRegister, setIsRegister] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const baseUrl = "http://127.0.0.1:8000";
    const endpoint = isRegister ? "/api/auth/register" : "/api/auth/login";
    
    try {
      const payload = isRegister 
        ? { email, password, role: "Researcher" }
        : { email, password };

      const res = await fetch(`${baseUrl}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Authentication failed.");
      }

      if (isRegister) {
        // Toggle back to login on successful register
        setIsRegister(false);
        setError("Account created successfully. Please login.");
      } else {
        const data = await res.json();
        localStorage.setItem("intellex_token", data.access_token);
        router.push("/");
      }
    } catch (err: any) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleOAuth = async () => {
    setError("");
    setLoading(true);
    const baseUrl = "http://127.0.0.1:8000";
    
    try {
      // Simulate Google OAuth token exchange
      const mockGoogleToken = `google_oauth_token_${Math.random().toString(36).substring(2)}`;
      const res = await fetch(`${baseUrl}/api/auth/oauth/google`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: mockGoogleToken })
      });

      if (!res.ok) {
        throw new Error("Google OAuth authentication failed.");
      }

      const data = await res.json();
      localStorage.setItem("intellex_token", data.access_token);
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Google OAuth failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrapper">
      <div className="auth-card">
        <div className="auth-header">
          <div style={{ display: "flex", justifyContent: "center", marginBottom: "1rem" }}>
            <div className="logo-icon">IX</div>
          </div>
          <h1 className="auth-title">Intellex</h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            Autonomous Multi-Agent Research Platform
          </p>
        </div>

        {error && (
          <div style={{
            background: "rgba(239, 68, 68, 0.1)",
            border: "1px solid var(--error)",
            color: "var(--text-primary)",
            padding: "0.75rem",
            borderRadius: "8px",
            fontSize: "0.85rem",
            marginBottom: "1.25rem"
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleAuth}>
          <div className="form-group">
            <label className="form-label">Email Address</label>
            <input
              type="email"
              className="form-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="researcher@intellex.org"
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
              placeholder="••••••••"
              required
            />
          </div>

          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? "Processing..." : isRegister ? "Create Account" : "Access Workspace"}
          </button>
        </form>

        <button onClick={handleGoogleOAuth} className="btn btn-oauth" disabled={loading}>
          <svg style={{ width: "1.25rem", height: "1.25rem" }} viewBox="0 0 24 24">
            <path
              fill="currentColor"
              d="M12.24 10.285V14.4h6.887c-.648 2.41-2.519 4.114-5.136 4.114-3.518 0-6.386-2.868-6.386-6.386 0-3.518 2.868-6.386 6.386-6.386 1.705 0 3.255.674 4.417 1.768l3.222-3.222C19.245 2.24 15.932 1 12.24 1A11.24 11.24 0 0 0 1 12.24a11.24 11.24 0 0 0 11.24 11.24c6.19 0 11.24-5.05 11.24-11.24 0-.825-.098-1.616-.27-2.385H12.24Z"
            />
          </svg>
          Continue with Google
        </button>

        <div style={{ marginTop: "1.5rem", textAlign: "center", fontSize: "0.85rem" }}>
          <span style={{ color: "var(--text-muted)" }}>
            {isRegister ? "Already have an account?" : "New to Intellex?"}
          </span>{" "}
          <button
            onClick={() => setIsRegister(!isRegister)}
            style={{
              background: "none",
              border: "none",
              color: "var(--accent-purple)",
              fontWeight: "600",
              cursor: "pointer"
            }}
          >
            {isRegister ? "Access Workspace" : "Request Credentials"}
          </button>
        </div>
      </div>
    </div>
  );
}
