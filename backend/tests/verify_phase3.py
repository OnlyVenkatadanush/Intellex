import subprocess
import time
import httpx
import sys
import json

def verify_all():
    print("=== Intellex Phase 3 Integration Verification ===")
    
    # 1. Start the server as a background process
    print("Starting FastAPI backend server...")
    server_process = subprocess.Popen(
        [sys.executable, "-m", "backend.app.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for server to boot
    time.sleep(5.0)
    
    base_url = "http://127.0.0.1:8000"
    
    try:
        # 2. Authenticate
        print("\n[Step 1] Logging in test researcher...")
        login_payload = {
            "email": "test_researcher@intellex.org",
            "password": "SecureTestPassword123"
        }
        res = httpx.post(f"{base_url}/api/auth/login", json=login_payload)
        print(f"Status: {res.status_code}")
        assert res.status_code == 200
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 3. Create Session
        print("\n[Step 2] Creating research session...")
        sess_payload = {
            "original_query": "Does copper-doped lead apatite LK-99 exhibit zero resistance superconductivity?"
        }
        res = httpx.post(f"{base_url}/api/sessions/create", json=sess_payload, headers=headers)
        print(f"Status: {res.status_code}")
        assert res.status_code == 201
        session_id = res.json()["id"]
        
        # 4. Trigger Real Agent Pipeline Execution & Listen to SSE Logs
        print("\n[Step 3] Executing Multi-Agent pipeline (SSE stream)...")
        with httpx.stream("GET", f"{base_url}/api/sessions/{session_id}/research", headers=headers, timeout=60.0) as stream:
            assert stream.status_code == 200
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    event_data = line[5:].strip()
                    parsed = json.loads(event_data)
                    print(f"[{parsed.get('agent_name')}]: {parsed.get('message')}")
        
        # 5. Fetch Session Details at completion to verify database insertions
        print("\n[Step 4] Querying completed session database records...")
        res = httpx.get(f"{base_url}/api/sessions/{session_id}", headers=headers)
        print(f"Status: {res.status_code}")
        assert res.status_code == 200
        data = res.json()
        
        print("\n=== Session Database Record Audit ===")
        print(f"Status: {data.get('status')}")
        print(f"Findings Count: {len(data.get('findings', []))}")
        print(f"Report Length: {len(data.get('report_markdown', ''))} characters")
        
        assert data.get("status") == "COMPLETED"
        assert len(data.get("findings", [])) > 0
        assert len(data.get("report_markdown", "")) > 100
        
        # Audit a finding metrics
        finding = data.get("findings")[0]
        print(f"\nClaim: {finding.get('claim')}")
        print(f"Confidence Score: {finding.get('confidence_score')}%")
        print(f"Source Count: {finding.get('source_count')}")
        print(f"Source Quality: {finding.get('source_quality_score')}/10")
        print(f"Verification Status: {finding.get('verification_status')}")
        print(f"Citations Count: {len(finding.get('citations', []))}")
        
        # Assertions
        assert finding.get("confidence_score") is not None
        assert finding.get("source_count") is not None
        assert finding.get("source_quality_score") is not None
        assert finding.get("verification_status") in ["VERIFIED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]
        
        print("\n=== All Phase 3 Multi-Agent Orchestration & RAG Verification Passed! ===")
        
    except Exception as e:
        print(f"\nVerification FAILED: {e}")
        # Print server logs if failed
        out, err = server_process.communicate(timeout=1.0)
        print(f"Server Out:\n{out}\nServer Err:\n{err}")
        sys.exit(1)
        
    finally:
        # Kill the server process
        server_process.terminate()
        server_process.wait()
        print("\nFastAPI backend server stopped.")

if __name__ == "__main__":
    verify_all()
