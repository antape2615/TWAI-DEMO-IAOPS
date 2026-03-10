import { api } from './api';

export interface Branch {
    name: string;
    protected: boolean;
}

export interface Commit {
    sha: string;
    message: string;
    author: string;
    date: string;
}

export const repositoryService = {
    // Listar ramas de un repositorio específico
    async listBranches(clientId: string, repoUrl: string): Promise<Branch[]> {
        const response = await api.get(`/repositories/${clientId}/branches`, {
            params: { repo_url: repoUrl }
        });
        return response.data;
    },

    // Listar todos los repositorios configurados
    async listRepositories(clientId: string): Promise<any[]> {
        const response = await api.get(`/repositories/${clientId}`);
        return response.data;
    },

    // Listar commits de una rama
    async listCommits(clientId: string, repoUrl: string, branch: string = 'main'): Promise<Commit[]> {
        const response = await api.get(`/repositories/${clientId}/commits`, {
            params: { repo_url: repoUrl, branch }
        });
        return response.data;
    },

    // Aceptar un merge (Simulación o API real si existe)
    async acceptMerge(clientId: string, branch: string): Promise<any> {
        return await api.post(`/repositories/${clientId}/merge`, { branch });
    }
};
