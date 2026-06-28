# Intellex API Reference

**Base URL**: `http://localhost:8000` (development) | `https://api.intellex.your-domain.com` (production)  
**Authentication**: Bearer JWT token. Obtain via `POST /api/auth/login`.

---

## Authentication

### POST /api/auth/register
Register a new user account.

**Request Body**
```json
{ "email": "user@example.com", "password": "Password123!", "role": "Researcher" }
```

**Response 201**
```json
{ "id": "uuid", "email": "user@example.com", "role": "Researcher", "created_at": "..." }
```

---

### POST /api/auth/login
Authenticate and receive JWT token.

**Request Body**
```json
{ "email": "user@example.com", "password": "Password123!" }
```

**Response 200**
```json
{ "access_token": "eyJ...", "token_type": "bearer" }
```

---

### POST /api/auth/oauth/google
Exchange a Google OAuth token (development: simulated).

**Request Body**
```json
{ "token": "google_oauth_id_token" }
```

---

### GET /api/auth/me
Return the currently authenticated user's profile.

**Headers**: `Authorization: Bearer <token>`

---

### PUT /api/auth/admin/users/role
Update a user's role. **Requires Admin role.**

**Request Body**
```json
{ "user_id": "uuid", "new_role": "Researcher" }
```

---

## Research Sessions

### POST /api/sessions/create
Create a new research session.

**Headers**: `Authorization: Bearer <token>`  
**Request Body**
```json
{ "original_query": "What are the mechanisms of CRISPR-Cas9 off-target effects?" }
```

**Response 201**
```json
{ "id": "uuid", "original_query": "...", "status": "PENDING", "created_at": "..." }
```

---

### GET /api/sessions/
List all sessions for the authenticated user (paginated).

**Query Params**: `skip=0`, `limit=20`  
**Response 200**: Array of session objects

---

### GET /api/sessions/{session_id}
Retrieve a session with full findings, citations, and logs.

**Response 200**: Full session detail with nested findings array

---

### DELETE /api/sessions/{session_id}
Delete a session and all associated data.

**Response 204**: No content

---

### GET /api/sessions/{session_id}/research
Execute the multi-agent research pipeline via SSE streaming.

**Query Params**: `citation_format=APA` or `citation_format=IEEE`

**Response**: `text/event-stream`  
Each event:
```
data: {"agent_name": "CRO Agent", "agent_role": "Chief Research Officer", "message": "...", "log_type": "INFO"}
```

---

## Documents

### POST /api/documents/upload
Upload a research document for text extraction.

**Headers**: `Authorization: Bearer <token>`, `Content-Type: multipart/form-data`  
**Form Fields**: `file` (binary), `session_id` (string)  
**Allowed types**: PDF, DOCX, TXT, CSV, PNG, JPG, JPEG  
**Max size**: 10 MB (configurable)

**Response 202**
```json
{ "document_id": "uuid", "filename": "paper.pdf", "file_type": "PDF", "size_bytes": 245000, "extracted_chars": 8432, "status": "PARSED" }
```

---

### GET /api/documents/session/{session_id}
List all documents uploaded for a session.

---

## Analytics

### GET /api/sessions/{session_id}/graph
Retrieve the knowledge graph for a session.

**Response 200**
```json
{
  "session_id": "uuid",
  "status": "persisted",
  "nodes": [{ "id": "uuid", "label": "CRISPR-Cas9", "type": "CONCEPT", "confidence": 0.92 }],
  "edges": [{ "source": "uuid-a", "target": "uuid-b", "type": "SUPPORTS", "weight": 0.8 }]
}
```

**Node types**: `QUERY`, `CONCEPT`, `SOURCE`, `FINDING`  
**Edge types**: `DERIVED_FROM`, `SUPPORTS`, `CONTRADICTS`, `RELATED_TO`, `CITES`

---

### GET /api/sessions/{session_id}/replay
Retrieve the agent execution replay timeline.

**Response 200**
```json
{
  "session_id": "uuid",
  "total_steps": 8,
  "total_events": 24,
  "timeline": [{ "step_index": 1, "agent_name": "CRO Agent", "events": [...] }]
}
```

---

### GET /api/sessions/{session_id}/compare/{other_session_id}
Compare two research sessions (diff of claims and confidence).

**Response 200**
```json
{
  "new_claims": [...], "removed_claims": [...],
  "confidence_changes": [{ "claim": "...", "delta": -12.5, "session_a_status": "VERIFIED", "session_b_status": "CONTRADICTED" }],
  "summary": { "total_new": 2, "total_removed": 1, "total_changed": 3 }
}
```

---

### GET /api/sessions/{session_id}/memory
Retrieve the user's verified long-term memory records.

---

## Health

### GET /api/health
Liveness probe. Returns 200 if service is running.

### GET /api/health/detailed
Readiness probe with per-component status (database, etc.).

---

## Error Responses

| Code | Meaning |
|------|---------|
| 400 | Bad Request — validation error |
| 401 | Unauthorized — invalid or missing token |
| 403 | Forbidden — insufficient role |
| 404 | Not Found — resource doesn't exist or doesn't belong to user |
| 409 | Conflict — e.g., research already completed |
| 413 | Payload Too Large — file exceeds 10 MB |
| 415 | Unsupported Media Type |
| 422 | Unprocessable Entity — Pydantic validation error |
| 500 | Internal Server Error |
