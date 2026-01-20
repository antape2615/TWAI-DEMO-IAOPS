import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Cloud, Search, Loader2 } from 'lucide-react';
import { CloudProvider, Resource } from '@/types';
import { resourceService } from '@/services/deploymentService';
import { Alert } from '@/components/Alert';
import toast from 'react-hot-toast';

interface ResourceQuery {
  client_id: string;
  cloud_provider: CloudProvider;
  resource_type: string;
}

export function Resources() {
  const [resources, setResources] = useState<Resource[]>([]);
  const [loading, setLoading] = useState(false);
  const [queried, setQueried] = useState(false);

  const { register, handleSubmit } = useForm<ResourceQuery>();

  const onSubmit = async (data: ResourceQuery) => {
    setLoading(true);
    setQueried(true);
    try {
      const result = await resourceService.list(
        data.client_id,
        data.cloud_provider,
        data.resource_type
      );
      setResources(result.resources);
      toast.success(`${result.count} recursos encontrados`);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Error al listar recursos');
      setResources([]);
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Recursos Cloud</h1>
        <p className="mt-2 text-gray-600">
          Consulta los recursos de tus clientes en diferentes proveedores de nube
        </p>
      </div>

      <div className="card">
        <div className="flex items-center space-x-2 mb-6">
          <Cloud className="w-6 h-6 text-primary-600" />
          <h2 className="text-xl font-semibold text-gray-900">
            Buscar Recursos
          </h2>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="label">Cliente ID</label>
            <input
              type="text"
              className="input"
              placeholder="client-123"
              {...register('client_id', { required: true })}
            />
          </div>

          <div>
            <label className="label">Cloud Provider</label>
            <select
              className="input"
              {...register('cloud_provider', { required: true })}
            >
              <option value="">Seleccionar...</option>
              <option value="aws">AWS</option>
              <option value="azure">Azure</option>
              <option value="gcp">GCP</option>
            </select>
          </div>

          <div>
            <label className="label">Tipo de Recurso</label>
            <input
              type="text"
              className="input"
              placeholder="ec2, vms, instances"
              {...register('resource_type', { required: true })}
            />
          </div>

          <div className="flex items-end">
            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary w-full flex items-center justify-center space-x-2"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Buscando...</span>
                </>
              ) : (
                <>
                  <Search className="w-5 h-5" />
                  <span>Buscar</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {loading && (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-12 h-12 text-primary-600 animate-spin" />
        </div>
      )}

      {!loading && queried && resources.length === 0 && (
        <Alert
          type="info"
          message="No se encontraron recursos con los criterios especificados"
        />
      )}

      {!loading && resources.length > 0 && (
        <div className="card">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Resultados ({resources.length})
          </h2>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    ID
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Nombre
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Tipo
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Estado
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {resources.map((resource, index) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-mono text-gray-900">
                      {resource.id}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {resource.name || '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {resource.type}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-1 text-xs font-medium rounded-full ${
                          resource.status === 'running'
                            ? 'bg-green-100 text-green-700'
                            : resource.status === 'stopped'
                            ? 'bg-red-100 text-red-700'
                            : 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {resource.status || 'unknown'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
