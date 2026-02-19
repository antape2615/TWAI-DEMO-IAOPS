import { api } from './api';

export interface CICDConfig {
    id: string;
    provider: string;
    organization?: string;
    project?: string;
    is_active: boolean;
}

export const cicdService = {
    // Disparar despliegue de código
    async deployCode(clientId: string, resourceId: string, branch: string = 'main'): Promise<any> {
        const response = await api.post('/cicd/deploy-code', null, {
            params: { client_id: clientId, resource_id: resourceId, branch }
        });
        return response.data;
    },

    // Obtener credenciales de CI/CD del cliente
    async getCredentials(clientId: string): Promise<CICDConfig[]> {
        const response = await api.get(`/cicd/credentials/${clientId}`);
        return response.data;
    }
};
