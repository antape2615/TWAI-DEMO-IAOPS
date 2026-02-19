import { api } from './api';

export interface GrafanaConfig {
    client_id: string;
    azure_tenant_id: string;
    azure_subscription_id: string;
    azure_client_id: string;
    azure_client_secret: string;
}

export interface DashboardRequest {
    client_id: string;
    resource_id: string;
    resource_type: string;
    resource_name: string;
}

export const monitoringService = {
    // Configurar Grafana con Azure Monitor
    async configureGrafana(config: GrafanaConfig): Promise<any> {
        const response = await api.post('/monitoring/configure-grafana', config);
        return response.data;
    },

    // Crear un dashboard para un recurso
    async createDashboard(request: DashboardRequest): Promise<any> {
        const response = await api.post('/monitoring/create-dashboard', request);
        return response.data;
    },

    // Obtener URL del dashboard existente
    async getDashboardUrl(resourceId: string): Promise<string> {
        const response = await api.get(`/monitoring/dashboard-url/${encodeURIComponent(resourceId)}`);
        return response.data.dashboard_url;
    }
};
