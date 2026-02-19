import { api } from './api';

export interface DeployableResource {
    id: string;
    name: string;
    type: string;
    resource_type_display: string;
    cloud_provider: string;
    location?: string;
    region?: string;
    deployable: boolean;
}

export const resourceService = {
    // Listar todos los recursos donde se puede desplegar código
    async listDeployableResources(clientId: string, cloudProvider?: string): Promise<DeployableResource[]> {
        const params = cloudProvider ? { cloud_provider: cloudProvider } : {};
        const response = await api.get(`/resources/deployable/${clientId}`, { params });
        return response.data.resources;
    },

    // Listar recursos por tipo específico
    async listByType(clientId: string, cloudProvider: string, resourceType: string): Promise<{ count: number, resources: any[] }> {
        const response = await api.get(`/resources/${clientId}/${cloudProvider}/${resourceType}`);
        return response.data;
    }
};
