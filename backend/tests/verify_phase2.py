import subprocess
import time
import httpx
import sys

def verify_all():
    print("=== Intellex Phase 2 Integration Verification ===")
    
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
        # 2. Test root endpoint
        print("\n[Test 1] Querying root endpoint...")
        res = httpx.get(f"{base_url}/")
        print(f"Status: {res.status_code}")
        print(f"Response: {res.json()}")
        assert res.status_code == 200
        assert res.json()["status"] == "online"
        
        # 3. Test user registration
        print("\n[Test 2] Querying registration endpoint...")
        reg_payload = {
            "email": "test_researcher@intellex.org",
            "password": "SecureTestPassword123",
            "role": "Researcher"
        }
        res = httpx.post(f"{base_url}/api/auth/register", json=reg_payload)
        print(f"Status: {res.status_code}")
        print(f"Response: {res.json()}")
        assert res.status_code == 201 or (res.status_code == 400 and "already registered" in res.text)
        
        # 4. Test user login
        print("\n[Test 3] Querying login endpoint...")
        login_payload = {
            "email": "test_researcher@intellex.org",
            "password": "SecureTestPassword123"
        }
        res = httpx.post(f"{base_url}/api/auth/login", json=login_payload)
        print(f"Status: {res.status_code}")
        print(f"Response: {res.json()}")
        assert res.status_code == 200
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 5. Test session creation
        print("\n[Test 4] Querying session creation endpoint...")
        sess_payload = {
            "original_query": "Verify compiler correctness in Clean Architecture."
        }
        res = httpx.post(f"{base_url}/api/sessions/create", json=sess_payload, headers=headers)
        print(f"Status: {res.status_code}")
        print(f"Response: {res.json()}")
        assert res.status_code == 201
        session_id = res.json()["id"]
        
        # 6. Test session retrieval
        print("\n[Test 5] Querying session details endpoint...")
        res = httpx.get(f"{base_url}/api/sessions/{session_id}", headers=headers)
        print(f"Status: {res.status_code}")
        print(f"Response: {res.json()}")
        assert res.status_code == 200
        
        # 7. Test SSE streaming run
        print("\n[Test 6] Querying Server-Sent Events stream endpoint...")
        with httpx.stream("GET", f"{base_url}/api/sessions/{session_id}/research", headers=headers) as stream:
            assert stream.status_code == 200
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    event_data = json_data = line[5:].strip()
                    print(f"Stream Event: {event_data}")
        
        print("\n=== All Phase 2 Verification Checks Passed! ===")
        
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
