import { api } from './api';
import { ArchitectureRequest, Architecture } from '@/types';

export const architectureService = {
  // Generar arquitectura con IA
  async generate(data: ArchitectureRequest): Promise<Architecture> {
    const response = await api.post('/api/v1/architecture/generate', data);
    return response.data;
  },

  // Estimar costo de arquitectura
  async estimateCost(data: ArchitectureRequest): Promise<any> {
    const response = await api.post('/api/v1/architecture/estimate-cost', data);
    return response.data;
  },
};
