import { api } from './api';
import { Client, ClientCreate } from '@/types';

export const clientService = {
  // Listar todos los clientes
  async getAll(): Promise<Client[]> {
    const response = await api.get('/api/v1/clients/');
    return response.data;
  },

  // Obtener un cliente por ID
  async getById(id: string): Promise<Client> {
    const response = await api.get(`/api/v1/clients/${id}`);
    return response.data;
  },

  // Crear un nuevo cliente
  async create(data: ClientCreate): Promise<Client> {
    const response = await api.post('/api/v1/clients/', data);
    return response.data;
  },

  // Actualizar un cliente
  async update(id: string, data: Partial<ClientCreate>): Promise<Client> {
    const response = await api.put(`/api/v1/clients/${id}`, data);
    return response.data;
  },

  // Eliminar un cliente
  async delete(id: string): Promise<void> {
    await api.delete(`/api/v1/clients/${id}`);
  },

  // Validar perfil tecnológico del cliente
  async validateProfile(id: string): Promise<any> {
    const response = await api.post(`/api/v1/clients/${id}/validate`);
    return response.data;
  },
};
