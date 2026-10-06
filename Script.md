# Webinar Presentation & Demo Script (`Script.md`)

**Session 2: Enterprise Multi-Agent Systems & Platform Governance (Govern Pillar)**  
**Presenter:** Len Henry, Global Founder Advocate  
**Target Duration:** 40 Minutes (Strict)  
**Key Architectural Theme:** Moving a multi-agent fleet from local containers and standalone custom code to Google Cloud Run, Vertex AI Reasoning Engine (BYOC), and platform-managed Zero-Trust governance via **Google Cloud Agent Gateway (`agw-travel-secure` — Egress Mode)**.

---

## Pre-Recording / Pre-Show Checklist (2 Minutes Before Start)

Run this once in your terminal so your environment variables and virtual environment are active:

```bash
cd /usr/local/google/home/gchenry/.gemini/jetski/scratch/sovereign-travel-agent
set -a && source .env && set +a
```

*(Optional — Start the Cloud Run authenticated proxy in a background terminal tab to use the Interactive Web Chat Console against Cloud Run + Reasoning Engine)*:
```bash
gcloud run services proxy travel-router \
  --region=us-central1 \
  --project="${GOOGLE_CLOUD_PROJECT}" \
  --port=8090
```

Open these **browser tabs** ahead of time:
1. **Interactive Web Chat Console (Cloud Run -> ReasoningEngine)**: `http://localhost:8090/` *(or Local Docker at `http://localhost:8085/`)*
2. **Agent Platform — Gateways (`agw-travel-secure` Details & Observability)**: `https://console.cloud.google.com/net-services/agent-gateway/list?project=${GOOGLE_CLOUD_PROJECT}`
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
2. **Google Cloud Console Tab — Agent Platform -> Gateways (`agw-travel-secure`)**:
   - **Console Path**: *Agent Platform -> Gateways -> `agw-travel-secure`* (`https://console.cloud.google.com/net-services/agent-gateway/list`)
   - Highlight `agw-travel-secure` in `us-central1` (`governedAccessPath: AGENT_TO_ANYWHERE`, protocol `MCP`, bound to **Google Cloud Agent Registry**, **Network Security `AuthzPolicy` (`travel-agw-authz-policy`)**, and its Google-managed `mtlsEndpoint` PSC service attachment and TLS inspection Root CA certificate).
   - Click the **Observability** tab on `agw-travel-secure` to show native gateway traffic metrics and logs.
3. **Google Cloud Console Tab — Cloud Run Services**:
   - **Console Path**: *Navigation Menu -> Cloud Run -> Services* (`https://console.cloud.google.com/run`)
   - Point out the stateless application services running in `us-central1` (no mock gateway container in Cloud Run):
     - `travel-router` (Entrypoint + Zero-Trust Chat Console delegating governed egress execution to Vertex AI `ReasoningEngine`)
     - `travel-planner` (Travel Planner Sub-Agent)
     - `corporate-policy-agent` (Corporate Policy Sub-Agent)
     - `corporate-mcp-server` (Internal Corporate MCP Tool Server)
     - `mock-airline-api` (Authorized External Airline API)

### 🎙️ Talk Track
> "Let's map out the **Travel & Expense Sovereign Fleet** we're building today. Instead of one monolithic agent doing everything, we break the system into three specialized, autonomous agents packaged in a stateless container image:
>
> 1. **The Travel Router Agent (`travel-router`)**: The orchestrator that receives the user's request and coordinates the fleet.
> 2. **The Travel Planner Agent (`travel-planner`)**: Pulls the user's travel preferences dynamically from a decoupled **Vertex AI Memory Bank (`MEMORYBANK_ID`)** and searches external airline APIs for flights.
> 3. **The Corporate Policy Agent (`corporate-policy-agent`)**: Queries our internal corporate compliance database via a **Model Context Protocol (MCP)** tool server to enforce Q4 department budgets, cabin class rules, and OFAC country embargoes.
>
> Notice the structural game-changer sitting directly in the outbound traffic lane of our agents: **Agent Gateway (`agw-travel-secure`)**. When our container runs in Vertex AI Reasoning Engine with `agentGatewayConfig` attached to `agw-travel-secure`, the platform's managed Secure Web Gateway and mTLS PSC tunnel transparently intercept, inspect, and govern every outbound HTTP and JSON-RPC 2.0 MCP tool call—with zero simulated logs and zero custom security middleware in Python."

---

## 🟨 00:15 – 00:25 | Segment 3: Zero-Trust Egress, Agent Identity, and Securing MCP

### 🖥️ What to Show on Screen
1. **Google Cloud Console Tab — Private Service Connect**:
   - **Console Path**: *Network Services -> Private Service Connect -> Published services* (`https://console.cloud.google.com/net-services/psc/list/publishedServices`)
   - Highlight `corp-mcp-psc-attachment` backed by `corp-mcp-ilb-forwarding-rule` inside `corp-sovereign-vpc`.
2. **IDE Files**:
   - Open [`deploy/mcp_toolspec.json`](./deploy/mcp_toolspec.json) (Highlight the MCP `tools` schema registered in Google Cloud Agent Registry: `verify_travel_compliance` vs. `override_department_budget`).
   - Open [`deploy/agent_gateway_policy.yaml`](./deploy/agent_gateway_policy.yaml) (Highlight `AGENT_TO_ANYWHERE_EGRESS`, `SPIFFE_JWT_SVID`, `privateServiceConnectTargets`, and `egressPolicy: defaultAction: DENY`).

### 🎙️ Talk Track
> "Why is **Zero-Trust Egress** so critical for autonomous LLMs? Because giving an LLM arbitrary outbound internet access or unrestricted MCP tool access is an enterprise security nightmare. If a user slips a **prompt injection** into a request, a compromised agent could be tricked into invoking a privileged administrative tool or exfiltrating executive traveler profiles to an external attacker-controlled server.
>
> Look at how Agent Gateway locks down the perimeter using native Google Cloud primitives:
>
> First, **Cryptographic Agent Identity (`AGENT_IDENTITY`)**: Every agent workload is issued a cryptographic workload identity (`principal://agents.global.org-.../reasoningEngines/...`) backed by mTLS client certificates and SPIFFE `JWT-SVID` tokens.
>
> Second, **Deep MCP Protocol Inspection via Agent Registry & IAP CEL**: Look at `deploy/mcp_toolspec.json`. We register our Corporate MCP Server in **Google Cloud Agent Registry** with its JSON-RPC 2.0 tool specification. Through **Network Security `AuthzPolicy`** (`travel-agw-authz-policy`) and **IAP**, `agw-travel-secure` inspects the JSON-RPC `tools/call` body in flight—allowing `verify_travel_compliance` while natively blocking unauthorized tool calls like `override_department_budget` with an HTTP `403 Forbidden` at the gateway!
>
> Third, **Default-Deny Egress & Private Service Connect (PSC)**: Only endpoints registered in Agent Registry and granted `roles/iap.egressor` can be reached. Any unlisted external domain is terminated at `agw-travel-secure` with a `403`."

---

## 🟥 00:25 – 00:35 | Segment 4: Technical Demonstration (4-Part Walkthrough)

---

### Demo Part 4A (`00:25 – 00:27`): The Repository & Local Stateless Containers (2 Mins)

#### 🖥️ What to Show on Screen
1. **IDE File 1**: [`app/main.py`](./app/main.py) (Highlight `/health` and `/invoke` — point out there are zero custom JWT or mTLS middleware imports).
2. **IDE File 2**: [`app/config.py`](./app/config.py) (Highlight `MEMORYBANK_ID` and `SESSION_STORE_URI` loaded from environment variables).
3. **IDE File 3**: [`docker-compose.yml`](./docker-compose.yml) (Show the 3 agent containers + local `mock-agent-gateway` container used strictly for local testing).
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
> "Let's jump into the code. Notice how clean our `/app` directory is. Inside `app/main.py`, we have a lightweight FastAPI wrapper around our modular Python ADK agents exposing `/health` and `/invoke`, plus a built-in Zero-Trust Chat Console at `/`. There are no bulky third-party security libraries or custom JWT validation classes here—the container is pure business logic.
>
> To make sure these containers can move seamlessly from a developer's laptop to Cloud Run and Vertex AI Reasoning Engine, they are completely stateless. Looking at `app/config.py` and the `/health` output, user travel profiles are injected dynamically via `MEMORYBANK_ID`, and conversation turns are persisted externally via `SESSION_STORE_URI`.
>
> For local offline development, `docker compose` spins up our agents alongside a lightweight local simulator (`mock-agent-gateway`) on port `8095`."

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
> "Before we promote our local containers to Google Cloud, we run `agy test` locally.
>
> Watch what this pre-flight evaluation verifies in under a second:
> 1. It confirms `/health` and our decoupled `MEMORYBANK_ID` and `SESSION_STORE_URI` bindings.
> 2. It tests end-to-end A2A routing from the Travel Router to the Travel Planner and Corporate Policy MCP Server.
> 3. It verifies that the Corporate MCP Server enforces OFAC country embargoes (blocking flights to Iran) and flags noncompliant First Class / over-budget fares for VP approval.
> 4. Most importantly, it simulates `403 Forbidden` rejections from the Agent Gateway—both for an unauthorized workload action and a prompt injection exfiltration attempt—verifying that our agent code catches and handles Gateway rejections gracefully without crashing the container. All six pre-flight checks pass."

---

### Demo Part 4C (`00:29 – 00:32`): Promoting Local Containers to Cloud Run & Reasoning Engine (3 Mins)

#### 🖥️ What to Show on Screen
1. **IDE File 1**: [`deploy/reasoning_engine_spec.json`](./deploy/reasoning_engine_spec.json)
   - Highlight lines `5–16`:
     ```json
     "spec": {
       "identityType": "AGENT_IDENTITY",
       "agentFramework": "custom",
       "containerSpec": {
         "imageUri": "us-central1-docker.pkg.dev/YOUR_PROJECT_ID/sovereign-travel-repo/sovereign-travel-agent:latest"
       },
       "deploymentSpec": {
         "agentGatewayConfig": {
           "agentToAnywhereConfig": {
             "agentGateway": "projects/YOUR_PROJECT_ID/locations/us-central1/agentGateways/agw-travel-secure"
           }
         }
       }
     }
     ```
2. **IDE File 2**: [`Dockerfile`](./Dockerfile) & [`deploy/promote_local_to_cloudrun.sh`](./deploy/promote_local_to_cloudrun.sh) (Show `AGENT_GATEWAY_ROOT_CERTIFICATES` installed via `update-ca-certificates`).
3. **Google Cloud Console Tabs**:
   - Show **Artifact Registry** (`sovereign-travel-repo`) containing the pushed container images.
   - Show **Cloud Run** with all application services green and deployed in `us-central1`.
   - Show **Cloud Firestore** (`agent-session-store` and `corp-travel-db`) backing the stateless containers.

#### ⌨️ Commands to Execute
```bash
# 1. Inspect the BYOC ReasoningEngine deployment specification binding Agent Gateway
cat deploy/reasoning_engine_spec.json

# 2. Verify our live Cloud Run services promoted from the local container image
gcloud run services list --region=us-central1
```
*(Optional if running the promotion live on camera instead of pre-deployed)*:
```bash
./deploy/promote_local_to_cloudrun.sh
```

#### 🎙️ Talk Track
> "Now let's move these exact same container images from local Docker to **Google Cloud** and attach native platform governance.
>
> Look at `deploy/reasoning_engine_spec.json`. We deploy our container image with `identityType: AGENT_IDENTITY` and a single declarative `agentGatewayConfig.agentToAnywhereConfig` block pointing to `agw-travel-secure` in `us-central1`.
>
> In our `Dockerfile`, we install `agw-travel-secure`'s TLS inspection root CA certificate from its `agentGatewayCard` so the container trusts TLS interception by the gateway. Running `promote_local_to_cloudrun.sh` registers our MCP `tool-spec` in **Agent Registry**, binds our **IAP CEL policy**, and wires the fleet to **Firestore**, **Vertex AI Memory Bank**, and **Agent Gateway (`agw-travel-secure`)**."

---

### Demo Part 4D (`00:32 – 00:35`): Live Test — Interactive Chat Console & Native Egress Block (3 Mins)

#### 🖥️ What to Show on Screen
1. **Browser Tab 1 — Interactive Web Chat Console (`http://localhost:8090/` or `http://localhost:8085/`)**:
   - Click the 5 one-click scenario buttons (`1. Compliant Flight`, `2. Embargoed (Iran)`, `3. Over Cap / 1st Class`, `4. Rogue SPIFFE (403)`, `5. Prompt Injection (403)`) while showing the live **Multi-Agent A2A & Egress Trace** and **Native Agent Gateway Audit Telemetry (`networkservices.googleapis.com/Gateway`)** in the right-hand panel.
2. **Terminal (Companion CLI Runner)**: Run `scripts/run_demo_scenarios.py` against the live **Cloud Run + ReasoningEngine** endpoint.
3. **Google Cloud Console Tabs — Agent Gateway Observability & Cloud Logging**:
   - **Tab A**: *Agent Platform -> Gateways -> `agw-travel-secure` -> Observability*
   - **Tab B**: *Observability -> Logging -> Logs Explorer* (`https://console.cloud.google.com/logs/query`)
   - Query to paste in Logs Explorer:
     ```text
     resource.type="networkservices.googleapis.com/Gateway"
     resource.labels.gateway_name="agw-travel-secure"
     httpRequest.requestMethod!="CONNECT"
     NOT httpRequest.requestUrl:"googleapis.com"
     ```

#### ⌨️ Commands to Execute
```bash
# Execute the 5 live scenarios directly against the deployed Cloud Run + ReasoningEngine fleet
ROUTER_URL="$(gcloud run services describe travel-router --region=us-central1 --format='value(status.url)')"

TARGET_ROUTER_URL="${ROUTER_URL}" \
.venv/bin/python scripts/run_demo_scenarios.py
```

#### 🎙️ Talk Track
> "Let's test our live Cloud deployment across five real-world scenarios in our Zero-Trust Chat Console and CLI runner.
>
> **In Scenario 1 (Compliant Booking)**, Alex Rivera asks to book a business-class flight to Tokyo and verify Q4 engineering budget compliance. The agent pulls Alex's profile from `MEMORYBANK_ID`, fetches flight `PS-108` (`$4,250`) from the authorized Airline API, and invokes `verify_travel_compliance` on our **Corporate MCP Server**. Both requests are intercepted by `agw-travel-secure`, match our **Agent Registry** endpoints and **IAP CEL policy**, log `authzPolicyInfo.result: ALLOWED` (`200 OK`), and the itinerary is `APPROVED`.
>
> **In Scenario 2 (OFAC Embargo Block)**, the user asks to book a flight to **Tehran, Iran (`IKA`)**. The request passes gateway inspection (`ALLOWED`), and the Corporate MCP Server blocks the itinerary (`POLICY_BLOCKED_EMBARGO`) under corporate export and sanctions rules.
>
> **In Scenario 3 (Noncompliant Cabin & Fare Cap)**, the user requests a **First Class** ticket to Tokyo (`$9,850`). The Corporate MCP Server flags the violation (`REQUIRES_VP_APPROVAL`) because First Class is prohibited and exceeds the `$5,500` cap.
>
> **In Scenario 4 (Unauthorized MCP Tool / Identity Block)**, a compromised or rogue caller attempts to invoke `override_department_budget` on the Corporate MCP Server. Look at the native `networkservices.googleapis.com/Gateway` log entry: `agw-travel-secure` parses the JSON-RPC 2.0 body (`mcpInfo.method: tools/call`, `mcpInfo.parameter: override_department_budget`), evaluates our IAP CEL rule, and **natively blocks the call at the gateway with HTTP `403` (`authzPolicyInfo.result: DENIED`)** before it ever touches the MCP server!
>
> **Now look at Scenario 5 — the Prompt Injection Exfiltration Attack**: The user's prompt tries to trick the agent into forwarding executive traveler profiles and corporate card details to `https://exfil-vault.attacker-analytics.io/collect`.
>
> Watch what happens: **Agent Gateway (`agw-travel-secure`)** intercepts the TLS connection (`tlsSniHostname: exfil-vault.attacker-analytics.io`), sees that `attacker-analytics.io` is not an authorized Agent Registry target, **actively blocks the exfiltration attempt with HTTP `403` (`authzPolicyInfo.result: DENIED`)**, and emits a native `networkservices.googleapis.com/Gateway` log entry directly to Cloud Logging and the Gateway Observability dashboard!"

---

## 🟪 00:35 – 00:38 | Segment 5: Summary & Architectural Watch-outs

### 🖥️ What to Show on Screen
- **Slide**: *Deploying Safely: Key Design Rules & Architectural Watch-outs*

### 🎙️ Talk Track
> "Let's recap the three architectural rules from what we just built:
> 1. **Keep containers 100% stateless**: Decouple your state using `SESSION_STORE_URI` and `MEMORYBANK_ID` so the exact same container image moves cleanly from local Docker Compose to Cloud Run and Vertex AI Reasoning Engine.
> 2. **Test local-to-cloud transitions early**: Use `agy test` with a local mock gateway during development to prove your agent code handles `403` gateway rejections gracefully before you deploy.
> 3. **Declare `agentGatewayConfig` on your deployment spec, install the Gateway Root CA, & register MCP tool specs**: Bake the gateway's `rootCertificates` into your container image for TLS inspection, register your MCP `tool-spec` in Agent Registry with IAP CEL policies, and coordinate with **Lisa Shen** on serverless GPU resources and backend scale parameters."

---

## 🟧 00:38 – 00:40 | Segment 6: Partner Transition & Handoff to Datadog

### 🖥️ What to Show on Screen
- **Terminal / Cloud Logging / Gateway Observability**: Highlight the native `networkservices.googleapis.com/Gateway` (`LoadBalancerLogEntry`) JSON output at the bottom of the terminal (`authzPolicyInfo.result: "DENIED"`, `agentGatewayInfo.mcpInfo`, `tlsSniHostname: "exfil-vault.attacker-analytics.io"`).
- **Slide**: *Observability: From Security Perimeter to Internal Reasoning Loops (Handoff to Kai Xin Tai, Datadog)*

### 🎙️ Talk Track
> "We have now successfully secured our agent network perimeter and egress lanes using **Google Cloud's Agent Gateway**.
>
> But once the perimeter is locked down, how do we see what is happening *inside* the cognitive reasoning loop of the model itself? How do we correlate these native `networkservices.googleapis.com/Gateway` security events with internal LLM traces, monitor hop-by-hop latency, and track token consumption across our multi-agent fleet?
>
> To show us how to monitor the internal telemetry of these secure hops, I'm handing the screen over to **Kai Xin Tai at Datadog**."
