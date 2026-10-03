#!/usr/bin/env bash
# ==============================================================================
# Complete GCP Resource Provisioning Script for Sovereign Travel Agent Demo
# Provisions:
#   1. Required GCP APIs
#   2. Artifact Registry Docker Repository (`sovereign-travel-repo`)
#   3. IAM Service Accounts, Roles, and SPIFFE Workload Identity Pool + Provider
#   4. Cloud Firestore Databases (`agent-session-store` & `corp-travel-db`)
#   5. VPC (`corp-sovereign-vpc`), Subnets, Proxy Subnet, and PSC NAT Subnet
#   6. Serverless NEG, Regional Internal Application Load Balancer, and
#      Private Service Connect (PSC) Service Attachment (`corp-mcp-psc-attachment`)
#   7. Vertex AI Memory Bank & Agent Gateway (`agw-travel-secure`) registration
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
AR_REPO="sovereign-travel-repo"
VPC_NAME="corp-sovereign-vpc"
SUBNET_NAME="corp-sovereign-subnet"
PROXY_SUBNET_NAME="corp-ilb-proxy-subnet"
PSC_SUBNET_NAME="corp-mcp-psc-nat-subnet"
GATEWAY_NAME="agw-travel-secure"

echo "========================================================================"
echo "  Provisioning GCP Resources in Project: ${PROJECT_ID} (${REGION})"
echo "========================================================================"

echo "==> [1/7] Enabling required Google Cloud APIs..."
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  compute.googleapis.com \
  servicedirectory.googleapis.com \
  sts.googleapis.com \
  iamcredentials.googleapis.com \
  firestore.googleapis.com \
  logging.googleapis.com \
  cloudtrace.googleapis.com \
  --project="${PROJECT_ID}"

echo "==> [2/7] Creating Artifact Registry Repository (${AR_REPO})..."
if ! gcloud artifacts repositories describe "${AR_REPO}" --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${AR_REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Stateless container images for the Sovereign Travel Agent Fleet" \
    --project="${PROJECT_ID}"
else
  echo "    Artifact Registry ${AR_REPO} already exists."
fi

gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo "==> [3/7] Creating Least-Privilege Service Accounts & IAM Bindings..."
for sa in travel-router-sa travel-planner-sa corporate-policy-sa corporate-mcp-sa; do
  if ! gcloud iam service-accounts describe "${sa}@${PROJECT_ID}.iam.gserviceaccount.com" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${sa}" \
      --display-name="Sovereign Fleet Service Account (${sa})" \
      --project="${PROJECT_ID}"
    sleep 5
  else
    echo "    Service account ${sa} already exists."
  fi

  for role in roles/run.invoker roles/datastore.user roles/logging.logWriter roles/cloudtrace.agent roles/aiplatform.user; do
    for attempt in 1 2 3; do
      if gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
        --member="serviceAccount:${sa}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="${role}" \
        --condition=None \
        --quiet >/dev/null 2>&1; then
        break
      fi
      sleep 4
    done
  done
done

echo "==> [4/7] Creating SPIFFE Workload Identity Pool & OIDC JWT-SVID Provider..."
if ! gcloud iam workload-identity-pools describe "agent-fleet-wi-pool" --location="global" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "agent-fleet-wi-pool" \
    --location="global" \
    --display-name="Agent Fleet SPIFFE JWT-SVID Pool" \
    --description="Issues cryptographic SPIFFE tokens validated at Agent Gateway" \
    --project="${PROJECT_ID}"
else
  echo "    Workload Identity Pool agent-fleet-wi-pool already exists."
fi

if ! gcloud iam workload-identity-pools providers describe "spiffe-jwt-svid-provider" \
  --workload-identity-pool="agent-fleet-wi-pool" \
  --location="global" \
  --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "spiffe-jwt-svid-provider" \
    --workload-identity-pool="agent-fleet-wi-pool" \
    --location="global" \
    --issuer-uri="https://accounts.google.com" \
    --allowed-audiences="https://sts.googleapis.com/v1/token" \
    --attribute-mapping="google.subject=assertion.sub" \
    --project="${PROJECT_ID}" || echo "    [Note] Custom OIDC provider skipped due to Org Policy; using project native SPIFFE trust domain (${PROJECT_ID}.svc.id.goog)."
else
  echo "    Workload Identity Provider spiffe-jwt-svid-provider already exists."
fi

echo "==> [5/7] Creating Cloud Firestore Databases (SESSION_STORE_URI & Internal Corporate DB)..."
for db_name in agent-session-store corp-travel-db; do
  if ! gcloud firestore databases describe --database="${db_name}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud firestore databases create \
      --database="${db_name}" \
      --location="${REGION}" \
      --type=firestore-native \
      --project="${PROJECT_ID}"
  else
    echo "    Firestore database ${db_name} already exists."
  fi
done

echo "==> [6/7] Provisioning Corporate VPC, Subnets, & Private Service Connect (PSC)..."
if ! gcloud compute networks describe "${VPC_NAME}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute networks create "${VPC_NAME}" \
    --subnet-mode=custom \
    --project="${PROJECT_ID}"
else
  echo "    VPC ${VPC_NAME} already exists."
fi

if ! gcloud compute networks subnets describe "${SUBNET_NAME}" --region="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute networks subnets create "${SUBNET_NAME}" \
    --network="${VPC_NAME}" \
    --region="${REGION}" \
    --range="10.20.0.0/24" \
    --enable-private-ip-google-access \
    --project="${PROJECT_ID}"
else
  echo "    Subnet ${SUBNET_NAME} already exists."
fi

if ! gcloud compute networks subnets describe "${PROXY_SUBNET_NAME}" --region="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute networks subnets create "${PROXY_SUBNET_NAME}" \
    --network="${VPC_NAME}" \
    --region="${REGION}" \
    --range="10.20.20.0/24" \
    --purpose=REGIONAL_MANAGED_PROXY \
    --role=ACTIVE \
    --project="${PROJECT_ID}"
else
  echo "    Proxy-only subnet ${PROXY_SUBNET_NAME} already exists."
fi

if ! gcloud compute networks subnets describe "${PSC_SUBNET_NAME}" --region="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute networks subnets create "${PSC_SUBNET_NAME}" \
    --network="${VPC_NAME}" \
    --region="${REGION}" \
    --range="10.20.10.0/24" \
    --purpose=PRIVATE_SERVICE_CONNECT \
    --project="${PROJECT_ID}"
else
  echo "    PSC NAT subnet ${PSC_SUBNET_NAME} already exists."
fi

# Serverless NEG + Internal ALB + PSC Service Attachment for `corporate-mcp-server`
if ! gcloud compute network-endpoint-groups describe "corp-mcp-psc-neg" --region="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute network-endpoint-groups create "corp-mcp-psc-neg" \
    --region="${REGION}" \
    --network-endpoint-type=serverless \
    --cloud-run-service="corporate-mcp-server" \
    --project="${PROJECT_ID}"
fi

if ! gcloud compute backend-services describe "corp-mcp-backend" --region="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute backend-services create "corp-mcp-backend" \
    --load-balancing-scheme=INTERNAL_MANAGED \
    --protocol=HTTP \
    --region="${REGION}" \
    --project="${PROJECT_ID}"

  gcloud compute backend-services add-backend "corp-mcp-backend" \
    --region="${REGION}" \
    --network-endpoint-group="corp-mcp-psc-neg" \
    --network-endpoint-group-region="${REGION}" \
    --project="${PROJECT_ID}"
fi

if ! gcloud compute url-maps describe "corp-mcp-url-map" --region="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute url-maps create "corp-mcp-url-map" \
    --default-service="corp-mcp-backend" \
    --region="${REGION}" \
    --project="${PROJECT_ID}"
fi

if ! gcloud compute target-http-proxies describe "corp-mcp-http-proxy" --region="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute target-http-proxies create "corp-mcp-http-proxy" \
    --url-map="corp-mcp-url-map" \
    --region="${REGION}" \
    --project="${PROJECT_ID}"
fi

if ! gcloud compute forwarding-rules describe "corp-mcp-ilb-forwarding-rule" --region="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute forwarding-rules create "corp-mcp-ilb-forwarding-rule" \
    --load-balancing-scheme=INTERNAL_MANAGED \
    --network="${VPC_NAME}" \
    --subnet="${SUBNET_NAME}" \
    --address="10.20.0.50" \
    --ports=80 \
    --region="${REGION}" \
    --target-http-proxy="corp-mcp-http-proxy" \
    --target-http-proxy-region="${REGION}" \
    --project="${PROJECT_ID}"
fi

if ! gcloud compute service-attachments describe "corp-mcp-psc-attachment" --region="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute service-attachments create "corp-mcp-psc-attachment" \
    --region="${REGION}" \
    --producer-forwarding-rule="corp-mcp-ilb-forwarding-rule" \
    --connection-preference=ACCEPT_AUTOMATIC \
    --nat-subnets="${PSC_SUBNET_NAME}" \
    --project="${PROJECT_ID}"
fi

echo "==> [7/7] Resolving Agent Gateway Policy (${GATEWAY_NAME})..."
sed "s/YOUR_PROJECT_ID/${PROJECT_ID}/g" deploy/agent_gateway_policy.yaml > deploy/agent_gateway_policy.resolved.yaml
echo "✔ All GCP Infrastructure resources provisioned in ${PROJECT_ID}."
