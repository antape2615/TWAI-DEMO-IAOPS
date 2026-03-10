import { api } from './api';
import { ArchitectureRequest, Architecture } from '@/types';

export const architectureService = {
  // Generar arquitectura con IA
  async generate(data: ArchitectureRequest): Promise<Architecture> {
    const response = await api.post('/architecture/generate', data);
    return response.data;
  },

  // Obtener historial de arquitecturas de un cliente
  async getHistory(clientId: string): Promise<Architecture[]> {
    const response = await api.get(`/architecture/history/${clientId}`);
    return response.data;
  },

  // Actualizar nombre de una arquitectura
  async updateName(id: string, name: string): Promise<Architecture> {
    const response = await api.put(`/architecture/${id}`, { name });
    return response.data;
  },

  // Estimar costo de arquitectura
  async estimateCost(data: ArchitectureRequest): Promise<unknown> {
    const response = await api.post('/architecture/estimate-cost', data);
    return response.data;
  },
  // Eliminar arquitectura por id
  async delete(id: string): Promise<void> {
    await api.delete(`/architecture/${id}`);
  },
};
