#!/usr/bin/env bash
# ==============================================================================
# Promote Local Containers to Cloud Run + Bind Agent Gateway (`agw-travel-secure`)
# Demonstrated in Segment 3 (00:29 - 00:32) of the Presentation
# ==============================================================================
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-YOUR_PROJECT_ID}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
AR_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/sovereign-travel-repo/sovereign-travel-agent:latest"
GATEWAY_RESOURCE="projects/${PROJECT_ID}/locations/${REGION}/agentGateways/agw-travel-secure"
MEMORYBANK_ID="projects/${PROJECT_ID}/locations/${REGION}/memoryBanks/mb-exec-travel-profiles"
SESSION_STORE_URI="firestore://projects/${PROJECT_ID}/databases/agent-session-store/collections/sessions"

echo "==> [Step 1] Tagging & pushing validated local container image to Artifact Registry"
docker tag sovereign-travel-agent:local "${AR_IMAGE}"
docker push "${AR_IMAGE}"

echo "==> [Step 2] Deploying the 3 specialized Agent Containers to Cloud Run"
gcloud run deploy travel-planner \
  --image="${AR_IMAGE}" \
  --region="${REGION}" \
  --ingress=internal \
  --service-account="travel-planner-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars="AGENT_ROLE=travel-planner,MEMORYBANK_ID=${MEMORYBANK_ID},SESSION_STORE_URI=${SESSION_STORE_URI}" \
  --project="${PROJECT_ID}"

gcloud run deploy corporate-policy-agent \
  --image="${AR_IMAGE}" \
  --region="${REGION}" \
  --ingress=internal \
  --service-account="corporate-policy-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars="AGENT_ROLE=corporate-policy-agent,MEMORYBANK_ID=${MEMORYBANK_ID},SESSION_STORE_URI=${SESSION_STORE_URI}" \
  --project="${PROJECT_ID}"

gcloud run deploy travel-router \
  --image="${AR_IMAGE}" \
  --region="${REGION}" \
  --allow-unauthenticated \
  --service-account="travel-router-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars="AGENT_ROLE=travel-router,MEMORYBANK_ID=${MEMORYBANK_ID},SESSION_STORE_URI=${SESSION_STORE_URI},AGENT_GATEWAY_RESOURCE=${GATEWAY_RESOURCE}" \
  --project="${PROJECT_ID}"

echo "==> [Step 3] Applying Platform-Level Agent Gateway Configuration (ReasoningEngine API)"
RESOLVED_SPEC="deploy/reasoning_engine_spec.resolved.json"
sed "s/YOUR_PROJECT_ID/${PROJECT_ID}/g" deploy/reasoning_engine_spec.json > "${RESOLVED_SPEC}"

curl -X PATCH \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d "@${RESOLVED_SPEC}" \
  "https://${REGION}-aiplatform.googleapis.com/v1beta1/projects/${PROJECT_ID}/locations/${REGION}/reasoningEngines/travel-router-engine?updateMask=spec.deploymentSpec.agentGatewayConfig"

echo "✔ Local containers promoted to Cloud Run and governed by ${GATEWAY_RESOURCE}"
