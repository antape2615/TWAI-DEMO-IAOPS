export type CloudProvider = 'aws' | 'azure' | 'gcp';
export type RepositoryProvider = 'github' | 'gitlab' | 'bitbucket';
export type InfrastructureStandard = 'terraform' | 'cloudformation' | 'arm_templates' | 'bicep' | 'pulumi';
export type CICDStandard = 'github-actions' | 'gitlab-ci' | 'azure-devops' | 'jenkins' | 'circleci';

export interface TechStandards {
  infrastructure: InfrastructureStandard;
  cicd: CICDStandard;
  container_orchestration?: string;
  monitoring?: string;
  logging?: string;
}

export interface TechProfile {
  clouds: CloudProvider[];
  repositories: RepositoryProvider[];
  standards: TechStandards;
  allowed_services?: Record<string, string[]>;
  restrictions?: Record<string, unknown>;
}

export interface Client {
  id: string;
  name: string;
  description?: string;
  tech_profile: TechProfile;
  created_at?: string;
  updated_at?: string;
  is_active: boolean;
}

export interface ClientCreate {
  name: string;
  description?: string;
  tech_profile: TechProfile;
}

export interface ArchitectureRequest {
  client_id: string;
  description: string;
  requirements?: Record<string, unknown>;
  target_clouds?: CloudProvider[];
  infrastructure_standard?: InfrastructureStandard;
}

export interface Architecture {
  id?: string;
  client_id: string;
  name?: string;
  architecture: {
    architecture_overview: string;
    components: Array<{
      name: string;
      type: string;
      cloud_service: string;
      description: string;
      configuration?: Record<string, unknown>;
    }>;
    data_flow?: string;
    security?: Record<string, unknown>;
    scalability?: Record<string, unknown>;
    disaster_recovery?: Record<string, unknown>;
  };
  infrastructure_code?: string;
  diagram?: string;
  estimated_cost?: {
    currency: string;
    monthly_total?: string;
    monthly_estimate: {
      min: number;
      max: number;
      currency: string;
    };
    breakdown?: Record<string, string>;
  };
  recommendations: string[];
  created_at?: string;
}

export interface DeploymentTarget {
  client_id: string;
  cloud_provider: CloudProvider;
  region: string;
  environment: string;
  resource_tags?: Record<string, string>;
}

export interface DeploymentRequest {
  target: DeploymentTarget;
  infrastructure_code: string;
  architecture_metadata?: Record<string, unknown>;
  repository_config?: {
    provider: RepositoryProvider;
    repository: string;
    file_path?: string;
    branch?: string;
    organization?: string;
  };
}

export interface Resource {
  id: string;
  name?: string;
  type: string;
  status?: string;
  [key: string]: unknown;
}

export interface ResourcesResponse {
  client_id: string;
  cloud_provider: CloudProvider;
  resource_type: string;
  count: number;
  resources: Resource[];
}
