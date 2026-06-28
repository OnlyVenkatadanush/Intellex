# 🌌 Intellex — Multi-Agent Autonomous Research Platform

<div align="center">

### Autonomous Research. Evidence-Driven Intelligence. Explainable Insights.

*An AI-powered Research Operating System that plans, retrieves, verifies, debates, synthesizes, and manages complex research workflows using a multi-agent architecture.*

![Python](https://img.shields.io/badge/Python-3.12+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![Next.js](https://img.shields.io/badge/Next.js-Frontend-black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-Agent%20Orchestration-orange)
![Docker](https://img.shields.io/badge/Docker-Containerized-blue)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

---

# 🚀 What is Intellex?

Intellex is a **Research Operating System (ResearchOS)** designed to automate the entire research lifecycle.

Unlike traditional AI assistants that simply answer questions, Intellex:

✅ Plans research strategies

✅ Collects evidence from multiple sources

✅ Detects contradictions

✅ Verifies claims

✅ Generates citations

✅ Builds interactive knowledge graphs

✅ Tracks research evolution over time

✅ Produces explainable research reports

---

# 🧠 Research Workflow

```text
User Query
    │
    ▼
Chief Research Officer (CRO)
    │
    ▼
Research Manager
    │
 ┌───────────────────────────────┐
 │      Evidence Layer           │
 ├───────────────────────────────┤
 │ Search Agent                  │
 │ PubMed Agent                  │
 │ arXiv Agent                   │
 │ Crossref Agent                │
 │ Document Intelligence Agent   │
 └───────────────────────────────┘
                │
                ▼
 ┌───────────────────────────────┐
 │      Reasoning Layer          │
 ├───────────────────────────────┤
 │ Analysis Agent                │
 │ Debate Agent                  │
 │ Contradiction Agent           │
 │ Trend Agent                   │
 │ Hypothesis Agent              │
 └───────────────────────────────┘
                │
                ▼
 ┌───────────────────────────────┐
 │      Quality Layer            │
 ├───────────────────────────────┤
 │ Fact Checker                  │
 │ Citation Engine               │
 │ Confidence Scorer             │
 │ Credibility Engine            │
 └───────────────────────────────┘
                │
                ▼
       Research Report
```

---

# ✨ Core Features

## 🔍 Multi-Agent Research Engine

* Chief Research Officer (CRO) Planning Agent
* Evidence Gathering Agents
* Analysis & Synthesis Agents
* Debate & Contradiction Resolution
* Fact Verification Pipeline
* Automated Citation Generation

---

## 📚 Hybrid RAG Pipeline

Supports:

* Academic Papers (arXiv)
* Medical Literature (PubMed)
* Crossref Metadata
* Web Research (Tavily)
* PDF Documents
* DOCX Files
* TXT Files
* CSV Files

Combines semantic retrieval with live external research.

---

## 🕸 Interactive Knowledge Graph

Intellex automatically constructs dynamic knowledge graphs.

Features:

* Zoom In / Zoom Out
* Drag Nodes
* Search Concepts
* Expand Relationships
* Collapse Graph Sections
* Source-to-Finding Navigation
* Confidence-Based Visualization
* Interactive Research Exploration

Node Types:

* Topics
* Concepts
* Findings
* Sources
* Citations
* Research Sessions

Relationship Types:

* SUPPORTS
* CONTRADICTS
* REFERENCES
* DERIVED_FROM
* RELATED_TO

---

## 🎬 Research Replay System

Every research session is fully traceable.

Example:

```text
09:00 Query Submitted
09:01 CRO Planning
09:02 Source Retrieval
09:03 Evidence Collection
09:04 Contradiction Detection
09:05 Debate Phase
09:06 Verification
09:07 Report Generation
09:08 Knowledge Graph Creation
```

Researchers can replay and inspect every step.

---

## 🛡 Research Integrity Layer

Intellex is designed to minimize hallucinations.

Features:

* Evidence-Based Findings
* Source Verification
* Citation Validation
* Confidence Scoring
* Contradiction Detection
* Explainable Conclusions

Verification States:

* VERIFIED
* PARTIALLY_VERIFIED
* CONFLICTING_EVIDENCE
* INSUFFICIENT_EVIDENCE
* UNVERIFIED

---

## 📈 Knowledge Evolution Engine

Track how knowledge changes over time.

Detect:

* New Findings
* Updated Findings
* Deprecated Findings
* Emerging Trends
* Research Gaps

Compare current research with previous reports.

---

# 🏗 System Architecture

```text
Frontend (Next.js)
        │
        ▼
FastAPI API Gateway
        │
        ▼
Research Manager
        │
 ┌─────────────────┐
 │ Agent Layer     │
 └─────────────────┘
        │
        ▼
RAG Engine
        │
        ▼
Vector Search
(pgvector)
        │
        ▼
PostgreSQL
        │
        ▼
Knowledge Graph
```

---

# ⚙ Technology Stack

### Backend

* Python 3.12+
* FastAPI
* SQLAlchemy
* Pydantic v2
* LangGraph
* JWT Authentication

### Frontend

* Next.js
* TypeScript
* React
* Server Components
* Vanilla CSS Design System

### Database

* PostgreSQL
* pgvector

### AI & Research

* Gemini API
* Ollama
* RAG Pipeline
* Vector Embeddings
* NLP

### Infrastructure

* Docker
* Docker Compose
* Structured Logging
* Correlation IDs
* Health Monitoring

---

# 📂 Project Structure

```text
Intellex/
│
├── backend/
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   ├── presentation/
│   └── utils/
│
├── frontend/
│   ├── app/
│   ├── components/
│   └── styles/
│
├── docs/
│
└── docker-compose.yml
```

---

# 🚀 Getting Started

## Backend

```bash
cd backend

cp .env.example .env

pip install -r requirements.txt

uvicorn backend.app.main:app --reload
```

---

## Frontend

```bash
cd frontend

npm install

npm run dev
```

---

## Docker

```bash
docker-compose up --build
```

---

# 📡 API Endpoints

| Method | Endpoint                              | Description             |
| ------ | ------------------------------------- | ----------------------- |
| POST   | /api/auth/register                    | Register user           |
| POST   | /api/auth/login                       | Login                   |
| POST   | /api/sessions/create                  | Create research session |
| GET    | /api/sessions/{id}/research           | Execute research        |
| GET    | /api/sessions/{id}/graph              | Knowledge graph         |
| GET    | /api/sessions/{id}/replay             | Research replay         |
| GET    | /api/sessions/{id}/compare/{other_id} | Session comparison      |
| POST   | /api/documents/upload                 | Upload files            |
| GET    | /api/health/detailed                  | Health status           |

---

# 🧪 Testing

```bash
pytest backend/tests -v
```

Includes:

* Unit Tests
* Integration Tests
* Agent Workflow Tests
* Authentication Tests
* Document Processing Tests

---

# 🎯 Why Intellex?

Intellex demonstrates:

* Multi-Agent Systems
* Agentic AI
* Retrieval Augmented Generation (RAG)
* Knowledge Graphs
* Information Retrieval
* Research Automation
* FastAPI Backend Engineering
* System Design
* PostgreSQL & Vector Search
* Explainable AI

---

# 📜 License

MIT License

---

<div align="center">

### Built for the future of autonomous research.

**Intellex — Research Beyond Search.**

</div>
