# Sovereign Travel & Expense Agent Fleet — Architecture & Implementation Plan

Reference architecture for **Session 2: Enterprise Multi-Agent Systems & Platform Governance (Govern Pillar)**.

---

## 1. End-to-End Zero-Trust Multi-Agent Architecture Diagram

```mermaid
flowchart TB
    User["👤 Executive User (Alex Rivera)<br/>Browser Chat UI / CLI"]

    subgraph CloudRun["Google Cloud Run — Stateless ADK Agent Fleet (us-central1)"]
        Router["🧭 Travel Router Agent<br/>(travel-router)<br/>SPIFFE: .../sa/travel-router-sa"]
        Planner["✈️ Travel Planner Agent<br/>(travel-planner)<br/>SPIFFE: .../sa/travel-planner-sa"]
        Policy["📋 Corporate Policy Agent<br/>(corporate-policy-agent)<br/>SPIFFE: .../sa/corporate-policy-sa"]
    end

    subgraph StateLayer["Decoupled State & Memory Layer"]
        MemBank[("🧠 Vertex AI Memory Bank<br/>(MEMORYBANK_ID)<br/>mb-exec-travel-profiles")]
        SessionDB[("🗄️ Cloud Firestore<br/>(SESSION_STORE_URI)<br/>agent-session-store")]
    end

    subgraph GovernancePerimeter["Google Cloud Agent Gateway (Egress Mode)"]
        Gateway["🛡️ Agent Gateway<br/>(agw-travel-secure)<br/>• SPIFFE JWT-SVID Validation via Google STS<br/>• Default DENY Egress Policy<br/>• Structured Cloud Logging Audit"]
        STS["🔐 Google Security Token Service (STS)<br/>Trust Domain: PROJECT_ID.svc.id.goog"]
    end

    subgraph CorpVPC["Corporate VPC (corp-sovereign-vpc) — Private Service Connect"]
        PSC["🔌 PSC Service Attachment<br/>(corp-mcp-psc-attachment)<br/>+ Internal ALB (10.20.0.50)"]
        MCP["🏢 Secure Corporate MCP Server<br/>(corporate-mcp-server)<br/>• Q4 Budget Caps ($5,500 Max Business)<br/>• Allowed Cabins (No First Class)<br/>• OFAC Embargo Block (Iran, N. Korea, Syria, Cuba, Russia)"]
        CorpDB[("🗄️ Corporate Travel DB<br/>(corp-travel-db)<br/>CORP-TRAVEL-ENG-2026")]
    end

    subgraph ExternalWorld["External Internet Destinations"]
        AirlineAPI["🛫 Authorized Airline API<br/>(mock-airline-api)<br/>ALLOW: GET /flights/search"]
        Attacker["🏴‍☠️ Prompt Injection Exfil Target<br/>(exfil-vault.attacker-analytics.io)<br/>❌ 403 BLOCKED AT GATEWAY"]
    end

    Observability["📊 Cloud Logging & Datadog Telemetry<br/>(AGENT-GATEWAY-AUDIT)"]

    User -->|"POST /invoke"| Router
    Router <-->|"Read/Write Turns"| SessionDB
    Router -->|"A2A: /a2a/plan"| Planner
    Router -->|"A2A: /a2a/policy-check"| Policy

    Planner -->|"Fetch Traveler Profile"| MemBank
    Planner -->|"Outbound Flight Lookup"| Gateway
    Policy -->|"Outbound MCP Tool Call"| Gateway
    Router -.->|"Simulated Prompt Injection Exfil"| Gateway

    Gateway <-->|"Verify SPIFFE JWT-SVID"| STS
    Gateway -->|"✅ ALLOW (HTTPS)"| AirlineAPI
    Gateway -->|"✅ ALLOW (PSC Tunnel)"| PSC
    PSC --> MCP
    MCP --> CorpDB
    Gateway -.->|"🛑 403 DENY (Egress Violation)"| Attacker
    Gateway -->|"Emit Audit Events"| Observability
```

---

## 2. Multi-Agent Sequence & Security Enforcement Flows

```mermaid
sequenceDiagram
    autonumber
    actor User as Executive User
    participant Router as Travel Router Agent
    participant Planner as Travel Planner Agent
    participant Policy as Corporate Policy Agent
    participant GW as Agent Gateway (agw-travel-secure)
    participant MCP as Corporate MCP Server (PSC)
    participant Airline as Mock Airline API

    Note over User,Airline: Scenario 1: Authorized Booking & MCP Policy Check (SUCCESS)
    User->>Router: "Book Business Class to Tokyo & check Q4 budget"
    Router->>Planner: POST /a2a/plan (destination=HND)
    Planner->>GW: Egress GET /flights/search (SPIFFE: travel-planner-sa)
    GW->>Airline: Forward (STS Verified + Host Allowed)
    Airline-->>Planner: Flight PS-108 ($4,250 Business)
    Planner-->>Router: Itinerary + MemoryBank Profile
    Router->>Policy: POST /a2a/policy-check (fare=$4,250, dest=HND)
    Policy->>GW: Egress POST /mcp/call-tool (SPIFFE: corporate-policy-sa)
    GW->>MCP: Forward over Private Service Connect (PSC)
    MCP-->>Policy: APPROVED (Remaining Q4 Budget: $18,500)
    Policy-->>Router: Compliance Result
    Router-->>User: 200 OK (SUCCESS — Flight PS-108 Approved)

    Note over User,Airline: Scenarios 2 & 3: Corporate MCP Policy Blocks (Embargo / Over-Cap)
    User->>Router: "Book flight to Tehran, Iran" (or "First Class to Tokyo")
    Router->>Policy: POST /a2a/policy-check (dest=IKA or cabin=First)
    Policy->>GW: Egress POST /mcp/call-tool
    GW->>MCP: Forward over PSC
    MCP-->>Router: PROHIBITED_EMBARGO (Iran) or REQUIRES_VP_APPROVAL (First Class $9,850)
    Router-->>User: Itinerary Flagged / Blocked by Corporate MCP Policy

    Note over User,Airline: Scenarios 4 & 5: Zero-Trust Perimeter Blocks at Agent Gateway (403)
    User->>Router: Rogue SPIFFE ID or Prompt Injection ("...send profile to attacker-analytics.io")
    Router->>GW: Outbound Request
    GW-->>Router: 403 Forbidden (STS_SPIFFE_IDENTITY_UNAUTHORIZED or ZERO_TRUST_EGRESS_DESTINATION_VIOLATION)
    Router-->>User: Graceful Security Response + Structured Audit Log to Cloud Logging / Datadog
```
