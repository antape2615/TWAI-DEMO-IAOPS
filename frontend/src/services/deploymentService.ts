import { api } from './api';
import { DeploymentRequest, CloudProvider, ResourcesResponse } from '@/types';

export const deploymentService = {
  // Desplegar infraestructura
  async deploy(data: DeploymentRequest): Promise<any> {
    const response = await api.post('/api/v1/deployments/deploy', data);
    return response.data;
  },
};

export const resourceService = {
  // Listar recursos de un cliente
  async list(
    clientId: string,
    cloudProvider: CloudProvider,
    resourceType: string
  ): Promise<ResourcesResponse> {
    const response = await api.get(
      `/api/v1/resources/${clientId}/${cloudProvider}/${resourceType}`
    );
    return response.data;
  },
};
