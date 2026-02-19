import { api } from './api';
import { Client, ClientCreate } from '@/types';

export const clientService = {
  // Listar todos los clientes
  async getAll(): Promise<Client[]> {
    const response = await api.get('/clients/');
    return response.data;
  },

  // Obtener un cliente por ID
  async getById(id: string): Promise<Client> {
    const response = await api.get(`/clients/${id}`);
    return response.data;
  },

  // Crear un nuevo cliente
  async create(data: ClientCreate): Promise<Client> {
    const response = await api.post('/clients/', data);
    return response.data;
  },

  // Actualizar un cliente
  async update(id: string, data: Partial<ClientCreate>): Promise<Client> {
    const response = await api.put(`/clients/${id}`, data);
    return response.data;
  },

  // Eliminar un cliente
  async delete(id: string): Promise<void> {
    await api.delete(`/clients/${id}`);
  },

  // Validar perfil tecnológico del cliente
  async validateProfile(id: string): Promise<unknown> {
    const response = await api.post(`/clients/${id}/validate`);
    return response.data;
  },
};
