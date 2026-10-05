# Webinar Presentation & Demo Script (`Script.md`)

**Session 2: Enterprise Multi-Agent Systems & Platform Governance (Govern Pillar)**  
**Presenter:** Len Henry, Global Founder Advocate  
**Target Duration:** 40 Minutes (Strict)  
**Key Architectural Theme:** Moving a multi-agent fleet from local containers and standalone custom code to Google Cloud Run and platform-managed Zero-Trust governance via **Agent Gateway (Egress Mode)**.

---

## Pre-Recording / Pre-Show Checklist (2 Minutes Before Start)

Run this once in your terminal so your environment variables and virtual environment are active:

```bash
cd /usr/local/google/home/gchenry/.gemini/jetski/scratch/sovereign-travel-agent
set -a && source .env && set +a
```

*(Optional — Start the Cloud Run authenticated proxy in a background terminal tab to use the Interactive Web Chat Console against Cloud Run)*:
```bash
gcloud run services proxy travel-router \
  --region=us-central1 \
  --project="${GOOGLE_CLOUD_PROJECT}" \
  --port=8090
```

Open these **browser tabs** ahead of time:
1. **Interactive Web Chat Console (Cloud Run)**: `http://localhost:8090/` *(or Local Docker at `http://localhost:8085/`)*
2. **Network Services — Agent Gateway (`agw-travel-secure`)**: `https://console.cloud.google.com/net-services/agent-gateway/list?project=${GOOGLE_CLOUD_PROJECT}`
3. **Cloud Run Services List**: `https://console.cloud.google.com/run?project=${GOOGLE_CLOUD_PROJECT}`
4. **Artifact Registry (`sovereign-travel-repo`)**: `https://console.cloud.google.com/artifacts/docker/${GOOGLE_CLOUD_PROJECT}/us-central1/sovereign-travel-repo?project=${GOOGLE_CLOUD_PROJECT}`
5. **Private Service Connect (`corp-mcp-psc-attachment`)**: `https://console.cloud.google.com/net-services/psc/list/publishedServices?project=${GOOGLE_CLOUD_PROJECT}`
6. **Cloud Firestore (`agent-session-store` & `corp-travel-db`)**: `https://console.cloud.google.com/firestore/databases?project=${GOOGLE_CLOUD_PROJECT}`
7. **Cloud Logging (Logs Explorer)**: `https://console.cloud.google.com/logs/query?project=${GOOGLE_CLOUD_PROJECT}`

---

## 🟩 00:00 – 00:05 | Segment 1: Intro, Session Hook, and "The Shift"

### 🖥️ What to Show on Screen
- **Slide**: *Session 2 Title Slide -> Single Agents vs. Cooperative A2A Fleets*

### 🎙️ Talk Track
> "Good call tuning in early today. Last week in Session 1, we built our first standalone agent and covered single-agent basics.
>
> Today, we are unlocking the true enterprise layout—moving from single prompt-and-response chatbots to a cooperative, distributed fleet of specialized **Agent-to-Agent (A2A)** and **Agent-to-Anywhere** microservices.
>
> Here is the core architectural challenge every enterprise hits when making this shift: When autonomous agents begin talking to other agents, querying internal corporate databases via MCP, and calling external third-party APIs, how do you police their communication boundaries without forcing your developers to write thousands of lines of custom mTLS and JWT security boilerplate in Python?
>
> Today, we'll see how the **Govern Pillar** of the **Gemini Enterprise Agent Platform** solves this at the platform layer using **Google Cloud's Agent Gateway**."

---

## 🟦 00:05 – 00:15 | Segment 2: Multi-Agent Orchestration & Platform Gateway Architecture

### 🖥️ What to Show on Screen
1. **Slide / Diagram**: *The Travel & Expense Sovereign Fleet Architecture Diagram* (or open `README.md` / `implementation_plan.md` Mermaid diagram).
2. **Google Cloud Console Tab — Network Services -> Agent Gateway**:
   - **Console Path**: *Network Services -> Agent Gateway* (`https://console.cloud.google.com/net-services/agent-gateway/list`)
   - Highlight `agw-travel-secure` in `us-central1` (`governedAccessPath: AGENT_TO_ANYWHERE`, protocol `MCP`, and its Google-managed `mtlsEndpoint` PSC service attachment).
3. **Google Cloud Console Tab — Cloud Run Services**:
   - **Console Path**: *Navigation Menu -> Cloud Run -> Services* (`https://console.cloud.google.com/run`)
   - Point out the distinct services running in `us-central1`:
     - `travel-router` (Orchestrator Agent + Zero-Trust Chat Console)
     - `travel-planner` (Travel Planner Sub-Agent)
     - `corporate-policy-agent` (Corporate Policy Sub-Agent)
     - `corporate-mcp-server` (Internal Corporate MCP Tool Server)
     - `agw-travel-secure` (Agent Gateway Data-Plane Enforcement Service bound to the Network Services `AgentGateway` control-plane resource)

### 🎙️ Talk Track
> "Let's map out the **Travel & Expense Sovereign Fleet** we're building today. Instead of one monolithic agent doing everything, we break the system into three specialized, autonomous agents running as stateless containers:
>
> 1. **The Travel Router Agent (`travel-router`)**: The orchestrator that receives the user's request and delegates across the fleet.
> 2. **The Travel Planner Agent (`travel-planner`)**: Pulls the user's travel preferences dynamically from a decoupled **Vertex AI Memory Bank (`MEMORYBANK_ID`)** and searches external airline APIs for flights.
> 3. **The Corporate Policy Agent (`corporate-policy-agent`)**: Queries our internal corporate compliance database via a **Model Context Protocol (MCP)** tool server to enforce Q4 department budgets, cabin class rules, and OFAC country embargoes.
>
> Notice the structural game-changer sitting directly in the outbound traffic lane of our agents: **Agent Gateway (`agw-travel-secure`)**. Rather than hardcoding proxies or custom security interceptors inside our Python containers, the platform dynamically intercepts, validates, and governs every user-to-agent, agent-to-agent, and agent-to-tool call."

---

## 🟨 00:15 – 00:25 | Segment 3: Zero-Trust Egress, SPIFFE Identities, and Securing MCP

### 🖥️ What to Show on Screen
1. **Google Cloud Console Tab — Private Service Connect**:
   - **Console Path**: *Network Services -> Private Service Connect -> Published services* (`https://console.cloud.google.com/net-services/psc/list/publishedServices`)
   - Highlight `corp-mcp-psc-attachment` backed by `corp-mcp-ilb-forwarding-rule` inside `corp-sovereign-vpc`.
2. **IDE File**: Open [`deploy/agent_gateway_policy.yaml`](./deploy/agent_gateway_policy.yaml)
   - Highlight lines `9–38`: `mode: AGENT_TO_ANYWHERE_EGRESS`, `protocol: SPIFFE_JWT_SVID`, `stsAudience`, `privateServiceConnectTargets`, and `egressPolicy: defaultAction: DENY`.

### 🎙️ Talk Track
> "Why is **Zero-Trust Egress** so critical for autonomous LLMs? Because giving an LLM arbitrary outbound internet access is an enterprise security nightmare. If a user slips a **prompt injection** into a request, a compromised agent could be tricked into exfiltrating sensitive corporate data or executive traveler profiles to an external attacker-controlled server.
>
> Look at how Agent Gateway locks down the perimeter in `deploy/agent_gateway_policy.yaml`:
>
> First, **Token Exchange & Cryptographic Workload Identity**: Every agent workload is issued a cryptographic **SPIFFE ID (`JWT-SVID` token)**. On every outbound hop, the Agent Gateway validates that SPIFFE token against **Google's Security Token Service (STS)**.
>
> Second, **Securing MCP via Private Service Connect (PSC)**: In the Google Cloud Console under *Private Service Connect*, our internal Corporate MCP Server sits inside an isolated corporate VPC (`corp-sovereign-vpc`) published via `corp-mcp-psc-attachment`. Only agents routed through the Agent Gateway carrying an explicitly authorized SPIFFE identity can invoke tools against our corporate database.
>
> That means our developers focus 100% on lightweight Python business logic while Google Cloud's perimeter handles network security and cryptographic token exchange."

---

## 🟥 00:25 – 00:35 | Segment 4: Technical Demonstration (4-Part Walkthrough)

---

### Demo Part 4A (`00:25 – 00:27`): The Repository & Local Stateless Containers (2 Mins)

#### 🖥️ What to Show on Screen
1. **IDE File 1**: [`app/main.py`](./app/main.py) (Highlight `/health` on line 83 and `/invoke` on line 98 — point out there are zero custom JWT or mTLS middleware imports).
2. **IDE File 2**: [`app/config.py`](./app/config.py) (Highlight `MEMORYBANK_ID` and `SESSION_STORE_URI` loaded from environment variables).
3. **IDE File 3**: [`docker-compose.yml`](./docker-compose.yml) (Show the 3 agent containers + local `mock-agent-gateway` container).
4. **Browser**: Briefly show the local Web Chat Console at `http://localhost:8085/`.

#### ⌨️ Commands to Execute
```bash
# 1. Show the clean /app directory structure
ls -la app/ app/agents/ app/tools/

# 2. Start the entire multi-agent fleet in local Docker containers
docker compose up -d --build

# 3. Show the running local containers
docker compose ps

# 4. Hit the local /health endpoint to show decoupled MEMORYBANK_ID and SESSION_STORE_URI
curl -s http://localhost:8085/health | python3 -m json.tool
```

#### 🎙️ Talk Track
> "Let's jump into the code. Notice how clean our `/app` directory is. Inside `app/main.py`, we have a lightweight FastAPI wrapper around our modular Python ADK agents exposing `/health` and `/invoke`, plus a built-in Zero-Trust Chat Console at `/`. There are no bulky third-party security libraries or 50-line JWT middleware classes here—the container is pure business logic.
>
> To make sure these containers can move seamlessly from a developer's laptop to Cloud Run, they are completely stateless. Looking at `app/config.py` and the `/health` output, user travel profiles are injected dynamically via `MEMORYBANK_ID`, and conversation turns are persisted externally via `SESSION_STORE_URI`.
>
> Right now, we have the entire fleet—the **Travel Router**, **Travel Planner**, **Corporate Policy Agent**, **Corporate MCP Server**, and a local **Mock Agent Gateway**—running in local Docker containers via `docker compose`."

---

### Demo Part 4B (`00:27 – 00:29`): Pre-Flight Evaluation (`agy test`) (2 Mins)

#### 🖥️ What to Show on Screen
- **IDE File**: [`tests/test_pre_flight.py`](./tests/test_pre_flight.py) (Briefly show the 6 test functions).
- **Terminal**: Run `./scripts/agy test`.

#### ⌨️ Commands to Execute
```bash
# Run local pre-deployment evaluation against the container fleet
./scripts/agy test
```

#### 🎙️ Talk Track
> "Before we promote our local containers to Cloud Run, we run `agy test` locally.
>
> Watch what this pre-flight evaluation verifies against our local mock gateway:
> 1. It confirms `/health` and our decoupled `MEMORYBANK_ID` and `SESSION_STORE_URI` bindings.
> 2. It tests end-to-end A2A routing from the Travel Router to the Travel Planner and Corporate Policy MCP Server.
> 3. It verifies that the Corporate MCP Server enforces OFAC country embargoes (blocking flights to Iran) and flags noncompliant First Class / over-budget fares for VP approval.
> 4. Most importantly, it simulates `403 Forbidden` rejections from the Agent Gateway—both for an unauthorized SPIFFE identity and a prompt injection exfiltration attempt—verifying that our agent code catches and handles Gateway rejections gracefully without crashing the container. All six pre-flight checks pass."

---

### Demo Part 4C (`00:29 – 00:32`): Promoting Local Containers to Cloud Run & Platform Config (3 Mins)

#### 🖥️ What to Show on Screen
1. **IDE File 1**: [`deploy/reasoning_engine_spec.json`](./deploy/reasoning_engine_spec.json)
   - Highlight lines `5–9`:
     ```json
     "deploymentSpec": {
       "agentGatewayConfig": {
         "agentGateway": "projects/YOUR_PROJECT_ID/locations/us-central1/agentGateways/agw-travel-secure"
       }
     }
     ```
2. **IDE File 2**: [`deploy/promote_local_to_cloudrun.sh`](./deploy/promote_local_to_cloudrun.sh)
3. **Google Cloud Console Tabs**:
   - Show **Artifact Registry** (`sovereign-travel-repo`) containing the pushed container images.
   - Show **Cloud Run** with all services green and deployed in `us-central1`.
   - Show **Cloud Firestore** (`agent-session-store` and `corp-travel-db`) backing the stateless containers.

#### ⌨️ Commands to Execute
```bash
# 1. Inspect the ReasoningEngine deployment specification binding Agent Gateway
cat deploy/reasoning_engine_spec.json

# 2. Verify our live Cloud Run services promoted from the local container image
gcloud run services list --region=us-central1
```
*(Optional if running the promotion live on camera instead of pre-deployed)*:
```bash
./deploy/promote_local_to_cloudrun.sh
```

#### 🎙️ Talk Track
> "Now let's move these exact same container images from local Docker to **Google Cloud Run** and attach platform governance.
>
> Look at `deploy/reasoning_engine_spec.json`. Instead of writing custom mTLS interceptors in Python, routing our agent's outbound traffic through the zero-trust gateway is a single declarative block on the `deploymentSpec`: `agentGatewayConfig` pointing to `agw-travel-secure` in `us-central1`.
>
> Running `promote_local_to_cloudrun.sh` pushes our local Docker image to **Artifact Registry** and deploys our three agents as distinct **Cloud Run** services—`travel-router`, `travel-planner`, and `corporate-policy-agent`—wired to our **Firestore** session store, **Vertex AI Memory Bank**, and **Agent Gateway**."

---

### Demo Part 4D (`00:32 – 00:35`): Live Test — Interactive Chat Console & Egress Block on Cloud Run (3 Mins)

#### 🖥️ What to Show on Screen
1. **Browser Tab 1 — Interactive Web Chat Console (`http://localhost:8090/` or `http://localhost:8085/`)**:
   - Click the 5 one-click scenario buttons (`1. Compliant Flight`, `2. Embargoed (Iran)`, `3. Over Cap / 1st Class`, `4. Rogue SPIFFE (403)`, `5. Prompt Injection (403)`) or type custom prompts in the chat box while showing the live **Multi-Agent A2A & Egress Trace** and **Agent Gateway Security Audit Logs** in the right-hand panel.
2. **Terminal (Alternative / Companion CLI Runner)**: Run `scripts/run_demo_scenarios.py` against the live **Cloud Run** endpoints.
3. **Google Cloud Console Tab — Cloud Logging (Logs Explorer)**:
   - **Console Path**: *Observability -> Logging -> Logs Explorer* (`https://console.cloud.google.com/logs/query`)
   - Query to paste in Logs Explorer:
     ```text
     resource.type="cloud_run_revision"
     resource.labels.service_name="agw-travel-secure"
     "AGENT-GATEWAY-AUDIT"
     ```

#### ⌨️ Commands to Execute
```bash
# Execute the 5 live scenarios directly against the deployed Cloud Run fleet
ROUTER_URL="$(gcloud run services describe travel-router --region=us-central1 --format='value(status.url)')"
GATEWAY_URL="$(gcloud run services describe agw-travel-secure --region=us-central1 --format='value(status.url)')"

TARGET_ROUTER_URL="${ROUTER_URL}" \
TARGET_GATEWAY_URL="${GATEWAY_URL}" \
.venv/bin/python scripts/run_demo_scenarios.py
```

#### 🎙️ Talk Track
> "Let's test our live Cloud Run deployment across five real-world scenarios in our Zero-Trust Chat Console and CLI runner.
>
> **In Scenario 1 (Compliant Booking)**, Alex Rivera asks to book a business-class flight to Tokyo and verify Q4 engineering budget compliance. The **Travel Router** pulls Alex's profile from `MEMORYBANK_ID`, fetches flight `PS-108` (`$4,250`) from the authorized Airline API, and calls the internal **Corporate MCP Server** over Private Service Connect. Both outbound hops pass **SPIFFE `JWT-SVID`** verification at the **Agent Gateway**, and the itinerary is `APPROVED`.
>
> **In Scenario 2 (OFAC Embargo Block)**, the user asks to book a flight to **Tehran, Iran (`IKA`)**. The Corporate Policy Agent queries our internal MCP server over PSC, which immediately blocks the itinerary (`POLICY_BLOCKED_EMBARGO`) under corporate export and sanctions rules.
>
> **In Scenario 3 (Noncompliant Cabin & Fare Cap)**, the user requests a **First Class** ticket to Tokyo (`$9,850`) or an over-cap Business route like Zurich (`$6,850`). The Corporate MCP Server flags the violation (`REQUIRES_VP_APPROVAL`) because First Class is prohibited and exceeds the `$5,500` cap.
>
> **In Scenario 4 (Rogue Workload SPIFFE Identity)**, we simulate an unauthorized agent presenting an unverified SPIFFE identity (`spiffe://rogue-workload.external/...`). The **Agent Gateway** rejects the token exchange via Google STS (`403`) before it ever reaches our Corporate MCP server.
>
> **Now look at Scenario 5 — the Prompt Injection Attack**: The user's prompt tries to trick the agent into forwarding executive traveler profiles and corporate card details to an external server (`https://exfil-vault.attacker-analytics.io/collect`).
>
> Watch what happens: Even when the agent attempts the outbound tool call, **Agent Gateway (`agw-travel-secure`)** intercepts the packet, sees that `attacker-analytics.io` is outside our authorized egress perimeter, **actively blocks the exfiltration attempt with a 403**, and immediately emits a structured security violation event to Cloud Logging—while our Travel Router handles the rejection gracefully!"

---

## 🟪 00:35 – 00:38 | Segment 5: Summary & Architectural Watch-outs

### 🖥️ What to Show on Screen
- **Slide**: *Deploying Safely: Key Design Rules & Architectural Watch-outs*

### 🎙️ Talk Track
> "Let's recap the three architectural rules from what we just built:
> 1. **Keep containers 100% stateless**: Decouple your state using `SESSION_STORE_URI` and `MEMORYBANK_ID` so the exact same container image moves cleanly from local Docker Compose to Cloud Run.
> 2. **Test local-to-cloud transitions early**: Use `agy test` with a local mock gateway during development to prove your agent code handles `403` gateway rejections gracefully before you deploy.
> 3. **Declare `agentGatewayConfig` on your deployment spec & verify Private Service Connect**: Always declare your `agentGatewayConfig` during deployment, verify your VPC and PSC service attachments for internal MCP databases beforehand, and coordinate with **Lisa Shen** on serverless GPU resources and backend scale parameters."

---

## 🟧 00:38 – 00:40 | Segment 6: Partner Transition & Handoff to Datadog

### 🖥️ What to Show on Screen
- **Terminal / Cloud Logging**: Highlight the JSON audit log output at the bottom of the terminal (`ZERO_TRUST_EGRESS_DESTINATION_VIOLATION`) or in Cloud Logging.
- **Slide**: *Observability: From Security Perimeter to Internal Reasoning Loops (Handoff to Kai Xin Tai, Datadog)*

### 🎙️ Talk Track
> "We have now successfully secured our agent network perimeter and egress lanes using **Google Cloud's Agent Gateway**.
>
> But once the perimeter is locked down, how do we see what is happening *inside* the cognitive reasoning loop of the model itself? How do we correlate these Agent Gateway security events with internal LLM traces, monitor hop-by-hop latency, and track token consumption across our multi-agent fleet?
>
> To show us how to monitor the internal telemetry of these secure hops, I'm handing the screen over to **Kai Xin Tai at Datadog**."
