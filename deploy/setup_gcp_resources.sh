#!/usr/bin/env bash
# ==============================================================================
# Provision GCP Infrastructure Resources for Sovereign Travel Agent Demo
# ==============================================================================
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-YOUR_PROJECT_ID}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
AR_REPO="sovereign-travel-repo"
VPC_NAME="corp-sovereign-vpc"
SUBNET_NAME="corp-sovereign-subnet"
PSC_SUBNET_NAME="corp-mcp-psc-nat-subnet"
GATEWAY_NAME="agw-travel-secure"

echo "==> [1/6] Enabling required Google Cloud APIs in project: ${PROJECT_ID}"
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

echo "==> [2/6] Creating Artifact Registry Repository (${AR_REPO}) for Local -> Cloud Run Container Promotion"
gcloud artifacts repositories create "${AR_REPO}" \
  --repository-format=docker \
  --location="${REGION}" \
  --description="Stateless container images for the Sovereign Travel Agent Fleet" \
  --project="${PROJECT_ID}" || true

echo "==> [3/6] Creating Least-Privilege Service Accounts & SPIFFE Workload Identity Pool"
for sa in travel-router-sa travel-planner-sa corporate-policy-sa corporate-mcp-sa; do
  gcloud iam service-accounts create "${sa}" \
    --display-name="Sovereign Fleet Service Account (${sa})" \
    --project="${PROJECT_ID}" || true
done

gcloud iam workload-identity-pools create "agent-fleet-wi-pool" \
  --location="global" \
  --display-name="Agent Fleet SPIFFE JWT-SVID Pool" \
  --project="${PROJECT_ID}" || true

echo "==> [4/6] Creating Decoupled State Stores (Firestore SESSION_STORE_URI & Corporate DB)"
gcloud firestore databases create \
  --database="agent-session-store" \
  --location="${REGION}" \
  --type=firestore-native \
  --project="${PROJECT_ID}" || true

gcloud firestore databases create \
  --database="corp-travel-db" \
  --location="${REGION}" \
  --type=firestore-native \
  --project="${PROJECT_ID}" || true

echo "==> [5/6] Provisioning Internal Corporate VPC & Private Service Connect (PSC) Subnet"
gcloud compute networks create "${VPC_NAME}" \
  --subnet-mode=custom \
  --project="${PROJECT_ID}" || true

gcloud compute networks subnets create "${SUBNET_NAME}" \
  --network="${VPC_NAME}" \
  --region="${REGION}" \
  --range="10.20.0.0/24" \
  --enable-private-ip-google-access \
  --project="${PROJECT_ID}" || true

gcloud compute networks subnets create "${PSC_SUBNET_NAME}" \
  --network="${VPC_NAME}" \
  --region="${REGION}" \
  --range="10.20.10.0/24" \
  --purpose=PRIVATE_SERVICE_CONNECT \
  --project="${PROJECT_ID}" || true

echo "==> [6/6] Registering Agent Gateway (${GATEWAY_NAME}) in Egress Mode"
echo "    Resource URI: projects/${PROJECT_ID}/locations/${REGION}/agentGateways/${GATEWAY_NAME}"
echo "    Policy Spec:  deploy/agent_gateway_policy.yaml"
echo "✔ GCP Infrastructure provisioning script complete."
