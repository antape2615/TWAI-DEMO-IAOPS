import { useEffect, useState } from 'react';
import { Plus, Edit, Trash2, CheckCircle, XCircle } from 'lucide-react';
import { Client } from '@/types';
import { clientService } from '@/services/clientService';
import { Loading } from '@/components/Loading';
import { Alert } from '@/components/Alert';
import { CreateClientModal } from '@/components/CreateClientModal';
import toast from 'react-hot-toast';

export function Clients() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    loadClients();
  }, []);

  const loadClients = async () => {
    try {
      const data = await clientService.getAll();
      setClients(data);
    } catch (error) {
      toast.error('Error al cargar clientes');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('¿Estás seguro de eliminar este cliente?')) return;

    try {
      await clientService.delete(id);
      toast.success('Cliente eliminado correctamente');
      loadClients();
    } catch (error) {
      toast.error('Error al eliminar cliente');
      console.error(error);
    }
  };

  if (loading) {
    return <Loading text="Cargando clientes..." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Clientes</h1>
          <p className="mt-2 text-gray-600">
            Gestiona los perfiles tecnológicos de tus clientes
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn btn-primary flex items-center space-x-2"
        >
          <Plus className="w-5 h-5" />
          <span>Nuevo Cliente</span>
        </button>
      </div>

      {clients.length === 0 ? (
        <Alert
          type="info"
          title="No hay clientes"
          message="Crea tu primer cliente para comenzar a usar IAOPS"
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {clients.map((client) => (
            <div key={client.id} className="card hover:shadow-lg transition-shadow">
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <h3 className="text-xl font-semibold text-gray-900">
                    {client.name}
                  </h3>
                  {client.description && (
                    <p className="text-sm text-gray-500 mt-1">
                      {client.description}
                    </p>
                  )}
                </div>
                <div className="flex items-center space-x-2">
                  {client.is_active ? (
                    <CheckCircle className="w-5 h-5 text-green-500" />
                  ) : (
                    <XCircle className="w-5 h-5 text-red-500" />
                  )}
                </div>
              </div>

              <div className="space-y-3">
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase mb-2">
                    Clouds Permitidos
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {client.tech_profile.clouds.map((cloud) => (
                      <span
                        key={cloud}
                        className="px-3 py-1 bg-blue-100 text-blue-700 text-sm rounded-full"
                      >
                        {cloud.toUpperCase()}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase mb-2">
                    Repositorios
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {client.tech_profile.repositories.map((repo) => (
                      <span
                        key={repo}
                        className="px-3 py-1 bg-purple-100 text-purple-700 text-sm rounded-full"
                      >
                        {repo}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase mb-2">
                    Estándares
                  </p>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-gray-600">IaC:</span>{' '}
                      <span className="font-medium">
                        {client.tech_profile.standards.infrastructure}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-600">CI/CD:</span>{' '}
                      <span className="font-medium">
                        {client.tech_profile.standards.cicd}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end space-x-2 mt-4 pt-4 border-t border-gray-200">
                <button className="btn btn-secondary flex items-center space-x-1">
                  <Edit className="w-4 h-4" />
                  <span>Editar</span>
                </button>
                <button
                  onClick={() => handleDelete(client.id)}
                  className="btn btn-danger flex items-center space-x-1"
                >
                  <Trash2 className="w-4 h-4" />
                  <span>Eliminar</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal de Creación */}
      {showCreateModal && (
        <CreateClientModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={loadClients}
        />
      )}
    </div>
  );
}
