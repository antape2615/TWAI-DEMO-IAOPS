import { api } from './api';

import { DeploymentRequest } from '@/types';

export interface CodeDeploymentRequest {
  client_id: string;
  repo_url: string;
  branch: string;
  resource_id: string;
  resource_type: string;
  environment: string;
  application_type?: string;  // nodejs, python, dotnet, java, go
  use_ai_pipeline?: boolean; // Usar IA para generar el pipeline
}

export interface DeploymentResponse {
  status: string;
  message: string;
  resources?: Array<{
    id: string;
    name: string;
    type: string;
    provider: string;
    region: string;
    status: string;
  }>;
  [key: string]: unknown;
}

export interface CodeDeploymentResponse {
  status: string;
  message: string;
  deployment_id: string;
  cicd_provider: string;
  details: string;
}

export interface DeploymentHistoryItem {
  id: string;
  client_id: string;
  cloud_provider: string;
  region: string;
  environment: string;
  status: string;
  deployment_data: Record<string, unknown>;
  error_message?: string;
  created_at: string;
  completed_at?: string;
}

export const deploymentService = {
  // Desplegar infraestructura
  async deploy(request: DeploymentRequest): Promise<DeploymentResponse> {
    const response = await api.post('/deployments/deploy', request);
    return response.data;
  },

  // Desplegar código desde repositorio a recurso cloud
  async deployCode(request: CodeDeploymentRequest): Promise<CodeDeploymentResponse> {
    const response = await api.post('/deployments/code', request);
    return response.data;
  },

  // Obtener historial de despliegues
  async getHistory(clientId: string): Promise<DeploymentHistoryItem[]> {
    const response = await api.get(`/deployments/history/${clientId}`);
    return response.data;
  }
};
