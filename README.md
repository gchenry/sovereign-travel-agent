# Sovereign Travel Agent Fleet — Agent Gateway (Egress Mode) Demo

Reference implementation for **Session 2: Enterprise Multi-Agent Systems & Platform Governance (Govern Pillar)**.

Demonstrates moving a multi-agent fleet (**Travel Router**, **Travel Planner**, and **Corporate Policy Agent**) from **local Docker containers** to **Google Cloud Run**, replacing custom Python security middleware with platform-enforced Zero-Trust governance via **Google Cloud Agent Gateway (`agw-travel-secure`)**.

---

## Architecture Highlights

1. **Modular Python ADK & FastAPI (`/app`)**:
   - Exposes `/health` and `/invoke` inside [`app/main.py`](./app/main.py).
   - Zero custom mTLS or JWT validation code in Python—the platform handles SPIFFE (`JWT-SVID`) verification via Google Security Token Service (STS) and egress enforcement.
2. **Decoupled State & Memory**:
   - `MEMORYBANK_ID`: Dynamically injects user travel profiles into the Travel Planner Agent without hardcoding.
   - `SESSION_STORE_URI`: Persists multi-turn state externally so containers remain 100% stateless across local Docker and Cloud Run.
3. **Zero-Trust Egress & Secure Corporate MCP**:
   - Outbound calls from the agent fleet traverse `agw-travel-secure`.
   - Internal Corporate MCP Server calls traverse Private Service Connect (PSC) after SPIFFE `JWT-SVID` verification.
   - Simulated **Prompt Injection Exfiltration** attempts are actively blocked at the Agent Gateway perimeter and logged to Cloud Logging (teeing up the Datadog observability handoff).

---

## 10-Minute Technical Walkthrough Guide (`00:25 - 00:35`)

### 1. The Repository & Local Containers (`00:25 - 00:27`)
Inspect the clean `/app` directory, `Dockerfile`, and `docker-compose.yml`:
```bash
# Start the 3 agent containers + Corporate MCP Server + Mock Airline API + Local Mock Gateway
docker compose up -d --build

# Verify running local containers
docker compose ps

# Check the stateless /health endpoint
curl -s http://localhost:8085/health | python3 -m json.tool
```

### 2. Pre-Flight Evaluation (`agy test`) (`00:27 - 00:29`)
Run `agy test` to verify routing, MCP tool usage, and graceful handling of Agent Gateway `403` rejections before cloud deployment:
```bash
./scripts/agy test
```

### 3. Promoting Local Containers to Cloud Run & Platform Config (`00:29 - 00:32`)
Inspect the `ReasoningEngine` deployment specification binding the agent to `agw-travel-secure`:
```bash
cat deploy/reasoning_engine_spec.json
```
Promote the validated local container image to Artifact Registry, Cloud Run, and bind `agentGatewayConfig`:
```bash
./deploy/setup_gcp_resources.sh
./deploy/promote_local_to_cloudrun.sh
```

### 4. Live Egress Block & Prompt Injection Demo (`00:32 - 00:35`)
Run the interactive scenario runner to demonstrate:
1. Authorized flight & Corporate MCP compliance check (`SPIFFE JWT-SVID` + `PSC`).
2. Blocking an unauthorized/rogue agent SPIFFE identity at the Gateway.
3. Blocking a simulated **Prompt Injection Attack** attempting to exfiltrate traveler profiles to `https://exfil-vault.attacker-analytics.io/collect`.
```bash
.venv/bin/python scripts/run_demo_scenarios.py
```
