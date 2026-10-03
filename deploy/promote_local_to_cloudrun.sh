#!/usr/bin/env bash
# ==============================================================================
# Build, Push, and Promote Local Containers to Cloud Run + Agent Gateway
# Demonstrated in Segment 3 (00:29 - 00:32) of the Presentation
# ==============================================================================
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project)}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
AR_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/sovereign-travel-repo"

AGENT_IMAGE="${AR_BASE}/sovereign-travel-agent:latest"
MCP_IMAGE="${AR_BASE}/corporate-mcp-server:latest"
AIRLINE_IMAGE="${AR_BASE}/mock-airline-api:latest"
GATEWAY_IMAGE="${AR_BASE}/mock-agent-gateway:latest"

GATEWAY_RESOURCE="projects/${PROJECT_ID}/locations/${REGION}/agentGateways/agw-travel-secure"
MEMORYBANK_ID="projects/${PROJECT_ID}/locations/${REGION}/memoryBanks/mb-exec-travel-profiles"
SESSION_STORE_URI="firestore://projects/${PROJECT_ID}/databases/agent-session-store/collections/sessions"
ROUTER_SPIFFE="spiffe://${PROJECT_ID}.svc.id.goog/ns/agent-engine/sa/travel-router-sa"
PLANNER_SPIFFE="spiffe://${PROJECT_ID}.svc.id.goog/ns/agent-engine/sa/travel-planner-sa"
POLICY_SPIFFE="spiffe://${PROJECT_ID}.svc.id.goog/ns/agent-engine/sa/corporate-policy-sa"

echo "==> [Step 1] Building & Pushing Container Images to Artifact Registry (${AR_BASE})"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

docker build -t sovereign-travel-agent:local -t "${AGENT_IMAGE}" -f Dockerfile .
docker build -t "${MCP_IMAGE}" -f services/corporate_mcp/Dockerfile .
docker build -t "${AIRLINE_IMAGE}" -f services/mock_airline/Dockerfile .
docker build -t "${GATEWAY_IMAGE}" -f services/mock_gateway/Dockerfile .

docker push "${AGENT_IMAGE}"
docker push "${MCP_IMAGE}"
docker push "${AIRLINE_IMAGE}"
docker push "${GATEWAY_IMAGE}"

echo "==> [Step 2] Deploying Corporate MCP Server & Mock Airline API to Cloud Run"
gcloud run deploy corporate-mcp-server \
  --image="${MCP_IMAGE}" \
  --region="${REGION}" \
  --no-allow-unauthenticated \
  --service-account="corporate-mcp-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --project="${PROJECT_ID}" \
  --quiet

MCP_URL="$(gcloud run services describe corporate-mcp-server --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')"

gcloud run deploy mock-airline-api \
  --image="${AIRLINE_IMAGE}" \
  --region="${REGION}" \
  --no-allow-unauthenticated \
  --service-account="corporate-mcp-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --project="${PROJECT_ID}" \
  --quiet

AIRLINE_URL="$(gcloud run services describe mock-airline-api --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')"

MCP_HOST="$(echo "${MCP_URL}" | sed -E 's#https?://##')"
AIRLINE_HOST="$(echo "${AIRLINE_URL}" | sed -E 's#https?://##')"

echo "==> [Step 3] Deploying Agent Gateway Service (agw-travel-secure) to Cloud Run"
gcloud run deploy agw-travel-secure \
  --image="${GATEWAY_IMAGE}" \
  --region="${REGION}" \
  --no-allow-unauthenticated \
  --service-account="travel-router-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},AGENT_GATEWAY_RESOURCE=${GATEWAY_RESOURCE},WORKLOAD_SPIFFE_ID=${ROUTER_SPIFFE},PLANNER_SPIFFE_ID=${PLANNER_SPIFFE},POLICY_SPIFFE_ID=${POLICY_SPIFFE},EXTRA_ALLOWED_EGRESS_HOSTS=${MCP_HOST};${AIRLINE_HOST}" \
  --project="${PROJECT_ID}" \
  --quiet

GATEWAY_URL="$(gcloud run services describe agw-travel-secure --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')"

echo "==> [Step 4] Deploying the 3 Sovereign Agent Containers to Cloud Run"
gcloud run deploy travel-planner \
  --image="${AGENT_IMAGE}" \
  --region="${REGION}" \
  --no-allow-unauthenticated \
  --service-account="travel-planner-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars="AGENT_ROLE=travel-planner,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},MEMORYBANK_ID=${MEMORYBANK_ID},SESSION_STORE_URI=${SESSION_STORE_URI},AGENT_GATEWAY_URL=${GATEWAY_URL},AGENT_GATEWAY_RESOURCE=${GATEWAY_RESOURCE},WORKLOAD_SPIFFE_ID=${PLANNER_SPIFFE},AIRLINE_API_URL=${AIRLINE_URL}" \
  --project="${PROJECT_ID}" \
  --quiet

PLANNER_URL="$(gcloud run services describe travel-planner --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')"

gcloud run deploy corporate-policy-agent \
  --image="${AGENT_IMAGE}" \
  --region="${REGION}" \
  --no-allow-unauthenticated \
  --service-account="corporate-policy-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars="AGENT_ROLE=corporate-policy-agent,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},MEMORYBANK_ID=${MEMORYBANK_ID},SESSION_STORE_URI=${SESSION_STORE_URI},AGENT_GATEWAY_URL=${GATEWAY_URL},AGENT_GATEWAY_RESOURCE=${GATEWAY_RESOURCE},WORKLOAD_SPIFFE_ID=${POLICY_SPIFFE},MCP_SERVER_URL=${MCP_URL}" \
  --project="${PROJECT_ID}" \
  --quiet

POLICY_URL="$(gcloud run services describe corporate-policy-agent --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')"

gcloud run deploy travel-router \
  --image="${AGENT_IMAGE}" \
  --region="${REGION}" \
  --no-allow-unauthenticated \
  --service-account="travel-router-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars="AGENT_ROLE=travel-router,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},MEMORYBANK_ID=${MEMORYBANK_ID},SESSION_STORE_URI=${SESSION_STORE_URI},AGENT_GATEWAY_URL=${GATEWAY_URL},AGENT_GATEWAY_RESOURCE=${GATEWAY_RESOURCE},WORKLOAD_SPIFFE_ID=${ROUTER_SPIFFE},TRAVEL_PLANNER_URL=${PLANNER_URL},CORPORATE_POLICY_AGENT_URL=${POLICY_URL},MCP_SERVER_URL=${MCP_URL},AIRLINE_API_URL=${AIRLINE_URL}" \
  --project="${PROJECT_ID}" \
  --quiet

ROUTER_URL="$(gcloud run services describe travel-router --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')"

echo "==> [Step 5] Generating Resolved ReasoningEngine Spec with agentGatewayConfig"
RESOLVED_SPEC="deploy/reasoning_engine_spec.resolved.json"
sed "s/YOUR_PROJECT_ID/${PROJECT_ID}/g" deploy/reasoning_engine_spec.json > "${RESOLVED_SPEC}"

echo "========================================================================"
echo "✔ Cloud Run Fleet Deployed & Governed by Agent Gateway!"
echo "  • Travel Router URL:          ${ROUTER_URL}"
echo "  • Travel Planner URL:         ${PLANNER_URL}"
echo "  • Corporate Policy Agent URL: ${POLICY_URL}"
echo "  • Agent Gateway URL:          ${GATEWAY_URL}"
echo "  • Corporate MCP Server URL:   ${MCP_URL}"
echo "  • Mock Airline API URL:       ${AIRLINE_URL}"
echo "========================================================================"
