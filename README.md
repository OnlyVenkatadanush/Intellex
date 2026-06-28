# 🌌 Intellex — Multi-Agent Autonomous Research Platform

Intellex is a production-grade Research Operating System designed to autonomously plan, execute, verify, synthesize, and manage academic and scientific research workflows. Powered by a multi-agent orchestration architecture, it leverages hybrid RAG pipelines, dynamic knowledge graphs, and execution replay tracking to deliver explainable, high-fidelity research reports.

---

## 🚀 Key Features

*   **Multi-Agent Orchestration**: A sequential cognitive execution pipeline:
    $$\text{CRO Planner} \longrightarrow \text{Evidence Gatherer} \longrightarrow \text{Analysis Synthesis} \longrightarrow \text{Debate Engine} \longrightarrow \text{Fact Checker} \longrightarrow \text{Citation Formatter} \longrightarrow \text{Memory archiver} \longrightarrow \text{Report Compiler}$$
*   **Hybrid RAG Pipeline**: Combines semantic search with real-time academic API ingestion (arXiv, PubMed, and Tavily Web Search) and local file ingestion (PDF, DOCX, TXT, CSV).
*   **Knowledge Graph Engine**: Automatically builds node-link schemas (connecting CONCEPT, SOURCE, FINDING, and QUERY nodes) representing support and contradiction weights.
*   **Research Replay & Timeline**: Tracks agent step execution logs chronologically, allowing researchers to inspect details of decisions.
*   **Fact-Checking & Integrity Layer**: Validates claims against source indices. LLM-failed verifications fallback to `INSUFFICIENT_EVIDENCE` with a confidence score cap of `50.0%` to prevent hallucinations.
*   **Cross-Session Comparison**: Computes a detailed diff of finding sets across multiple research queries, exposing new, deleted, or altered confidence metrics.

---

## 🏛 Clean Architecture & Core Stack

```
backend/
├── app/
│   ├── domain/         # Pure entity definitions and provider contracts (interfaces)
│   ├── application/    # Repository interfaces
│   ├── infrastructure/ # ORM Models, DB Repositories, Gemini/Ollama Provider wrappers
│   ├── presentation/   # FastAPI API endpoints, SSE Stream handlers, and health checks
│   └── utils/          # Document parsers, Security, and Reliability utilities (retries, circuit breakers)
```

*   **Backend**: FastAPI, SQLAlchemy (PostgreSQL / SQLite), Pydantic v2
*   **Frontend**: Next.js 15 (App Router), Vanilla CSS Design System with HSL tokens
*   **AI Engine**: Gemini 1.5 Flash (primary model), Ollama compatibility
*   **Observability**: Structured JSON logging, Correlation ID tracing, Detailed Readiness probes
*   **Testing**: Pytest, Pytest-Asyncio, StaticPool test databases (100% passes)

---

## 🛠 Setup & Local Development

### Prerequisites
*   Python 3.12+ (or 3.13)
*   Node.js 18+
*   Docker & Docker Compose (optional)

### 1. Backend Configuration
Navigate to `backend/`, copy the environment template, and configure your keys:
```bash
cd backend
cp .env.example .env
```
Ensure you set your `GEMINI_API_KEY` inside `.env`.

Install requirements and launch the API server:
```bash
pip install -r requirements.txt
python -m uvicorn backend.app.main:app --reload --port 8000
```
API Documentation will be available locally at: `http://localhost:8000/api/docs`.

### 2. Frontend Configuration
Navigate to `frontend/`, configure your environment, install dependencies, and launch:
```bash
cd ../frontend
npm install
npm run dev
```
Open `http://localhost:3000` in your browser.

---

## 🐳 Running with Docker Compose

To boot the entire 3-tier containerized stack (PostgreSQL with pgvector, FastAPI Backend, and Next.js Frontend):
```bash
docker-compose up --build
```
The backend automatically waits until the PostgreSQL database container health check is healthy before initiating the table schema structures.

---

## 🧪 Testing Suite

We maintain a rigorous unit and integration test suite verifying authentication guards, document processing, health metrics, and agent logic. Run the tests locally:
```bash
python -m pytest backend/tests/ -v
```

---

## 📖 Key API Endpoints Quick-Start

| Method | Endpoint | Description |
|---|---|---|
| **POST** | `/api/auth/register` | User signup (email/password). |
| **POST** | `/api/auth/login` | User login, returns JWT token. |
| **POST** | `/api/sessions/create` | Open a new research session query. |
| **GET** | `/api/sessions/` | List all sessions of the authenticated user (paginated). |
| **GET** | `/api/sessions/{id}/research` | Execute agent pipeline and stream log timeline (SSE). |
| **POST** | `/api/documents/upload` | Upload PDF/DOCX/CSV/TXT source file (Max 10MB). |
| **GET** | `/api/sessions/{id}/graph` | Retrieve nodes/edges matching React Flow schema. |
| **GET** | `/api/sessions/{id}/replay` | Retrieve agent step timeline. |
| **GET** | `/api/sessions/{id}/compare/{other_id}` | Compare findings between two sessions. |
| **GET** | `/api/health/detailed` | Readiness check with DB connection state. |