terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.30.0"
    }
  }
}

variable "project_id" {
  description = "GCP Project ID for the Sovereign Travel Agent Demo"
  type        = string
}

variable "region" {
  description = "Primary GCP Region"
  type        = string
  default     = "us-central1"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. Artifact Registry for Local -> Cloud Run Container Promotion
resource "google_artifact_registry_repository" "sovereign_travel_repo" {
  location      = var.region
  repository_id = "sovereign-travel-repo"
  description   = "Docker images for Sovereign Travel Agent Fleet"
  format        = "DOCKER"
}

# 2. Corporate Internal VPC & Private Service Connect Subnets
resource "google_compute_network" "corp_sovereign_vpc" {
  name                    = "corp-sovereign-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "corp_sovereign_subnet" {
  name                     = "corp-sovereign-subnet"
  ip_cidr_range            = "10.20.0.0/24"
  region                   = var.region
  network                  = google_compute_network.corp_sovereign_vpc.id
  private_ip_google_access = true
}

resource "google_compute_subnetwork" "corp_mcp_psc_nat" {
  name          = "corp-mcp-psc-nat-subnet"
  ip_cidr_range = "10.20.10.0/24"
  region        = var.region
  network       = google_compute_network.corp_sovereign_vpc.id
  purpose       = "PRIVATE_SERVICE_CONNECT"
}

# 3. Dedicated Service Accounts for SPIFFE Workload Identities
resource "google_service_account" "travel_router_sa" {
  account_id   = "travel-router-sa"
  display_name = "Travel Router Agent SA"
}

resource "google_service_account" "travel_planner_sa" {
  account_id   = "travel-planner-sa"
  display_name = "Travel Planner Agent SA"
}

resource "google_service_account" "corporate_policy_sa" {
  account_id   = "corporate-policy-sa"
  display_name = "Corporate Policy Agent SA"
}

resource "google_service_account" "corporate_mcp_sa" {
  account_id   = "corporate-mcp-sa"
  display_name = "Secure Corporate MCP Server SA"
}

# 4. Workload Identity Pool for SPIFFE JWT-SVID Validation via Google STS
resource "google_iam_workload_identity_pool" "agent_fleet_wi_pool" {
  workload_identity_pool_id = "agent-fleet-wi-pool"
  display_name              = "Agent Fleet SPIFFE JWT-SVID Pool"
  description               = "Issues cryptographic SPIFFE tokens validated at Agent Gateway"
}

# 5. Decoupled Firestore Databases (SESSION_STORE_URI & Internal Corporate DB)
resource "google_firestore_database" "agent_session_store" {
  project     = var.project_id
  name        = "agent-session-store"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
}

resource "google_firestore_database" "corp_travel_db" {
  project     = var.project_id
  name        = "corp-travel-db"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
}
