import { api } from './api';

export interface DashboardStats {
    total_clients: number;
    total_architectures: number;
    total_deployments: number;
    recent_activity: Array<{
        action: string;
        client: string;
        time: string;
        type: 'deployment' | 'architecture';
    }>;
    cloud_usage: Record<string, number>;
}

export const dashboardService = {
    getStats: async (): Promise<DashboardStats> => {
        const response = await api.get<DashboardStats>('/dashboard/stats');
        return response.data;
    },
};
