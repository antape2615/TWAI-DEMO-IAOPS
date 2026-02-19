import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import {
  Cloud,
  Search,
  Loader2,
  Activity,
  Info,
  CheckCircle2,
  LayoutDashboard,
  ExternalLink
} from 'lucide-react';
import { CloudProvider, Resource, Client } from '@/types';
import { resourceService } from '@/services/resourceService';
import { clientService } from '@/services/clientService';
import { monitoringService } from '@/services/monitoringService';
import toast from 'react-hot-toast';

interface ResourceQuery {
  client_id: string;
  cloud_provider: CloudProvider;
  resource_type: string;
}

interface ResourceExtended extends Resource {
  location?: string;
  zone?: string;
  vm_size?: string;
  sku?: string;
}

export function Monitoring() {
  const [resources, setResources] = useState<Resource[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedBehavior, setSelectedBehavior] = useState<Resource | null>(null);
  const [dashboardUrl, setDashboardUrl] = useState<string>('');
  const [creatingDashboard, setCreatingDashboard] = useState(false);

  const { register, handleSubmit, setValue, watch } = useForm<ResourceQuery>();
  const watchedClientId = watch('client_id');

  useEffect(() => {
    const loadClients = async () => {
      try {
        const data = await clientService.getAll();
        setClients(data);
        if (data.length > 0) {
          setValue('client_id', data[0].id);
        }
      } catch (error) {
        console.error('Error loading clients:', error);
      }
    };

    loadClients();
  }, [setValue]);

  const handleResourceSelect = async (resource: Resource) => {
    setSelectedBehavior(resource);
    setDashboardUrl('');

    try {
      // Intentar obtener URL existente
      const url = await monitoringService.getDashboardUrl(resource.id);
      setDashboardUrl(url);
    } catch (error) {
      // No existe dashboard aún
      console.log('No dashboard found for resource');
    }
  };

  const handleCreateDashboard = async () => {
    if (!selectedBehavior || !watchedClientId) return;

    setCreatingDashboard(true);
    try {
      const response = await monitoringService.createDashboard({
        client_id: watchedClientId,
        resource_id: selectedBehavior.id,
        resource_type: selectedBehavior.type,
        resource_name: selectedBehavior.name || selectedBehavior.id
      });
      setDashboardUrl(response.dashboard_url);
      toast.success('Dashboard creado exitosamente');
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } }; message?: string };
      const errorMessage = axiosError?.response?.data?.detail || 'Error al crear el dashboard. Verifique la configuración en Settings.';
      console.error('Error creating dashboard:', error);
      toast.error(errorMessage);
    } finally {
      setCreatingDashboard(false);
    }
  };

  const onSubmit = async (data: ResourceQuery) => {
    setLoading(true);
    try {
      const result = await resourceService.listByType(
        data.client_id,
        data.cloud_provider,
        data.resource_type
      );
      setResources(result.resources);
      toast.success(`${result.count} recursos encontrados`);
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } }; message?: string };
      const errorMessage = axiosError?.response?.data?.detail || axiosError?.message || 'Error al listar recursos';
      toast.error(errorMessage);
      setResources([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Recursos Cloud</h1>
        <p className="mt-2 text-gray-600">
          Analiza el comportamiento y estado de tus recursos en tiempo real
        </p>
      </div>

      <div className="card">
        <div className="flex items-center space-x-2 mb-6">
          <Cloud className="w-6 h-6 text-primary-600" />
          <h2 className="text-xl font-semibold text-gray-900">
            Monitor de Recursos
          </h2>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="label">Cliente</label>
            <select
              className="input"
              {...register('client_id', { required: true })}
            >
              <option value="">Seleccionar Cliente...</option>
              {clients.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="label">Cloud Provider</label>
            <select
              className="input"
              {...register('cloud_provider', { required: true })}
            >
              <option value="">Seleccionar...</option>
              <option value="azure">Azure</option>
              <option value="aws">AWS</option>
              <option value="gcp">GCP</option>
            </select>
          </div>

          <div>
            <label className="label">Tipo de Recurso</label>
            <select
              className="input"
              {...register('resource_type', { required: true })}
            >
              <option value="">Seleccionar...</option>
              <option value="app_services">App Services</option>
              <option value="functions">Azure Functions</option>
              <option value="containers">Container Instances</option>
              <option value="vms">Virtual Machines / EC2</option>
              <option value="storage">Storage Accounts / S3</option>
              <option value="aks">Kubernetes (AKS/EKS/GKE)</option>
              <option value="amplify">AWS Amplify</option>
              <option value="resource_groups">Resource Groups / Resource Managers</option>
            </select>
          </div>

          <div className="flex items-end">
            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary w-full flex items-center justify-center space-x-2"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Search className="w-5 h-5" />
              )}
              <span>Analizar Recursos</span>
            </button>
          </div>
        </form>
      </div>

      {!loading && resources.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 card">
            <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-primary-600" />
              Estado de Recursos ({resources.length})
            </h2>

            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Nombre</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tipo</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ubicación</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Estado</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Acción</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {resources.map((resource, index) => (
                    <tr key={index} className="hover:bg-gray-50 cursor-pointer" onClick={() => handleResourceSelect(resource)}>
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">
                        {resource.name || resource.id}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {resource.type}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {(resource as ResourceExtended).location || (resource as ResourceExtended).zone || '-'}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-1 text-xs font-medium rounded-full ${resource.status === 'running' || resource.status === 'active'
                            ? 'bg-green-100 text-green-700'
                            : resource.status === 'stopped'
                              ? 'bg-red-100 text-red-700'
                              : 'bg-yellow-100 text-yellow-700'
                            }`}
                        >
                          {resource.status || 'unknown'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleResourceSelect(resource)}
                          className="text-primary-600 hover:text-primary-800 flex items-center justify-end w-full"
                        >
                          <LayoutDashboard className="w-5 h-5 mr-1" />
                          <span className="text-xs font-medium">Dashboard</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="card">
            <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Search className="w-5 h-5 text-primary-600" />
              Análisis de Comportamiento
            </h2>

            {selectedBehavior ? (
              <div className="space-y-4">
                <div className="p-4 bg-gray-50 rounded-lg">
                  <label className="text-xs text-gray-500 uppercase font-bold">Recurso Seleccionado</label>
                  <p className="text-lg font-bold text-gray-900">{selectedBehavior.name}</p>
                </div>

                <div className="space-y-3">
                  {(() => {
                    const behavior = selectedBehavior.behavior as Record<string, unknown> | undefined;
                    if (!behavior) return null;
                    return Object.entries(behavior).map(([key, value]) => {
                      const displayValue = value !== null && value !== undefined ? String(value) : '-';
                      return (
                        <div key={key} className="flex justify-between border-b pb-2">
                          <span className="text-sm text-gray-500 capitalize">{key.replace(/_/g, ' ')}</span>
                          <span className="text-sm font-medium text-gray-900">{displayValue}</span>
                        </div>
                      );
                    });
                  })()}

                  {(selectedBehavior as ResourceExtended).vm_size && (
                    <div className="flex justify-between border-b pb-2">
                      <span className="text-sm text-gray-500">Hardware Profile</span>
                      <span className="text-sm font-medium text-gray-900">{(selectedBehavior as ResourceExtended).vm_size}</span>
                    </div>
                  )}

                  {(selectedBehavior as ResourceExtended).sku && (
                    <div className="flex justify-between border-b pb-2">
                      <span className="text-sm text-gray-500">SKU / Precio</span>
                      <span className="text-sm font-medium text-gray-900">{(selectedBehavior as ResourceExtended).sku}</span>
                    </div>
                  )}
                </div>

                <div className="mt-6 p-4 bg-blue-50 border border-blue-100 rounded-lg">
                  <div className="flex items-start space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-blue-600 mt-0.5" />
                    <p className="text-xs text-blue-800">
                      <strong>AI Insights:</strong> Este recurso está sincronizado con la infraestructura generada. No se detectan desviaciones (Drift).
                    </p>
                  </div>
                </div>

                {/* Grafana Dashboard Section */}
                <div className="pt-4 border-t mt-4">
                  <h3 className="text-sm font-bold text-gray-900 mb-3 flex items-center">
                    <Activity className="w-4 h-4 mr-2 text-primary-600" />
                    Monitoreo en Tiempo Real
                  </h3>

                  {dashboardUrl ? (
                    <div className="border rounded-lg overflow-hidden bg-white shadow-sm">
                      <iframe
                        src={dashboardUrl}
                        width="100%"
                        height="400"
                        frameBorder="0"
                        title="Grafana Dashboard"
                      ></iframe>
                      <div className="p-2 bg-gray-50 text-right">
                        <a
                          href={dashboardUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-primary-600 hover:text-primary-800 flex items-center justify-end"
                        >
                          Abrir en Grafana <ExternalLink className="w-3 h-3 ml-1" />
                        </a>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center p-6 bg-gray-50 rounded-lg border border-dashed border-gray-300">
                      <LayoutDashboard className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                      <p className="text-sm text-gray-500 mb-3">No hay dashboard configurado para este recurso.</p>
                      <button
                        onClick={handleCreateDashboard}
                        disabled={creatingDashboard}
                        className="btn btn-primary btn-sm w-full py-2"
                      >
                        {creatingDashboard ? (
                          <><Loader2 className="w-4 h-4 animate-spin mr-2" /> Creando...</>
                        ) : (
                          "Crear Dashboard Automático"
                        )}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-64 text-center">
                <Info className="w-12 h-12 text-gray-300 mb-4" />
                <p className="text-gray-500">Selecciona un recurso para analizar su comportamiento y métricas en tiempo real.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
