import { api } from './api';

export interface SystemDefaults {
    cloud: {
        aws: { access_key: string; region: string };
        azure: { client_id: string; tenant_id: string; subscription_id: string };
        gcp: { project_id: string };
    };
    repositories: {
        github: { token: string };
        gitlab: { url: string; token: string };
    };
}

export const settingsService = {
    async getDefaults(): Promise<SystemDefaults> {
        const response = await api.get('/settings/defaults');
        return response.data;
    },

    async updateCloud(clientId: string, provider: string, credentials: any, region?: string): Promise<any> {
        return await api.post('/settings/cloud', {
            client_id: clientId,
            provider,
            credentials,
            region
        });
    },

    async updateRepo(clientId: string, provider: string, credentials: any, organization?: string): Promise<any> {
        return await api.post('/settings/repositories', {
            client_id: clientId,
            provider,
            credentials,
            organization
        });
    },

    async updateCICD(clientId: string, provider: string, token: string, organization?: string, project?: string): Promise<any> {
        return await api.post('/settings/cicd', {
            client_id: clientId,
            provider,
            token,
            organization,
            project
        });
    }
};
