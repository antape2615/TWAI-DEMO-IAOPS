export type CloudProvider = 'aws' | 'azure' | 'gcp';
export type RepositoryProvider = 'github' | 'gitlab' | 'bitbucket';
export type InfrastructureStandard = 'terraform' | 'cloudformation' | 'arm_templates' | 'pulumi';
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
  restrictions?: Record<string, any>;
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
  requirements?: Record<string, any>;
  target_clouds?: CloudProvider[];
}

export interface Architecture {
  client_id: string;
  architecture: {
    architecture_overview: string;
    components: Array<{
      name: string;
      type: string;
      cloud_service: string;
      description: string;
      configuration?: Record<string, any>;
    }>;
    data_flow?: string;
    security?: Record<string, any>;
    scalability?: Record<string, any>;
    disaster_recovery?: Record<string, any>;
  };
  infrastructure_code?: string;
  diagram?: string;
  estimated_cost?: {
    monthly_estimate: {
      min: number;
      max: number;
      currency: string;
    };
    breakdown?: Record<string, string>;
  };
  recommendations: string[];
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
  [key: string]: any;
}

export interface ResourcesResponse {
  client_id: string;
  cloud_provider: CloudProvider;
  resource_type: string;
  count: number;
  resources: Resource[];
}
