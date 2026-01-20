import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Sparkles, Loader2 } from 'lucide-react';
import { ArchitectureRequest, Architecture } from '@/types';
import { architectureService } from '@/services/architectureService';
import { Alert } from '@/components/Alert';
import toast from 'react-hot-toast';

export function AIGenerator() {
  const [architecture, setArchitecture] = useState<Architecture | null>(null);
  const [loading, setLoading] = useState(false);

  const { register, handleSubmit, formState: { errors } } = useForm<ArchitectureRequest>();

  const onSubmit = async (data: ArchitectureRequest) => {
    setLoading(true);
    try {
      const result = await architectureService.generate(data);
      setArchitecture(result);
      toast.success('Arquitectura generada exitosamente');
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Error al generar arquitectura');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Generador de Arquitecturas con IA</h1>
        <p className="mt-2 text-gray-600">
          La IA genera arquitecturas respetando el perfil tecnológico del cliente
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form */}
        <div className="card">
          <div className="flex items-center space-x-2 mb-6">
            <Sparkles className="w-6 h-6 text-primary-600" />
            <h2 className="text-xl font-semibold text-gray-900">
              Nueva Arquitectura
            </h2>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="label">Cliente ID</label>
              <input
                type="text"
                className="input"
                placeholder="client-123"
                {...register('client_id', { required: 'Cliente ID es requerido' })}
              />
              {errors.client_id && (
                <p className="text-sm text-red-600 mt-1">{errors.client_id.message}</p>
              )}
            </div>

            <div>
              <label className="label">Descripción</label>
              <textarea
                rows={4}
                className="input"
                placeholder="Describe lo que necesitas construir..."
                {...register('description', { required: 'Descripción es requerida' })}
              />
              {errors.description && (
                <p className="text-sm text-red-600 mt-1">{errors.description.message}</p>
              )}
            </div>

            <div>
              <label className="label">Requerimientos (JSON)</label>
              <textarea
                rows={3}
                className="input font-mono text-sm"
                placeholder='{"scalability": "high", "availability": "99.9%"}'
                {...register('requirements')}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary w-full flex items-center justify-center space-x-2"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Generando...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5" />
                  <span>Generar Arquitectura</span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* Result */}
        <div className="card">
          <h2 className="text-xl font-semibold text-gray-900 mb-6">
            Resultado
          </h2>

          {!architecture && !loading && (
            <Alert
              type="info"
              message="Completa el formulario para generar una arquitectura"
            />
          )}

          {loading && (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="w-12 h-12 text-primary-600 animate-spin" />
            </div>
          )}

          {architecture && !loading && (
            <div className="space-y-4">
              <div>
                <h3 className="font-semibold text-gray-900 mb-2">
                  Descripción General
                </h3>
                <p className="text-sm text-gray-600">
                  {architecture.architecture.architecture_overview}
                </p>
              </div>

              <div>
                <h3 className="font-semibold text-gray-900 mb-2">
                  Componentes ({architecture.architecture.components.length})
                </h3>
                <div className="space-y-2">
                  {architecture.architecture.components.map((component, index) => (
                    <div
                      key={index}
                      className="p-3 bg-gray-50 rounded-lg border border-gray-200"
                    >
                      <p className="font-medium text-gray-900">{component.name}</p>
                      <p className="text-sm text-gray-600">{component.cloud_service}</p>
                      <p className="text-xs text-gray-500 mt-1">{component.description}</p>
                    </div>
                  ))}
                </div>
              </div>

              {architecture.estimated_cost && (
                <div>
                  <h3 className="font-semibold text-gray-900 mb-2">
                    Estimación de Costos
                  </h3>
                  <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                    <p className="text-lg font-bold text-green-700">
                      ${architecture.estimated_cost.monthly_estimate.min} - $
                      {architecture.estimated_cost.monthly_estimate.max} /mes
                    </p>
                    <p className="text-sm text-green-600">
                      {architecture.estimated_cost.monthly_estimate.currency}
                    </p>
                  </div>
                </div>
              )}

              {architecture.recommendations.length > 0 && (
                <div>
                  <h3 className="font-semibold text-gray-900 mb-2">
                    Recomendaciones
                  </h3>
                  <ul className="space-y-1">
                    {architecture.recommendations.map((rec, index) => (
                      <li key={index} className="text-sm text-gray-600 flex items-start">
                        <span className="text-primary-600 mr-2">•</span>
                        {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {architecture.infrastructure_code && (
                <div>
                  <h3 className="font-semibold text-gray-900 mb-2">
                    Código de Infraestructura
                  </h3>
                  <pre className="p-4 bg-gray-900 text-gray-100 rounded-lg overflow-x-auto text-xs">
                    {architecture.infrastructure_code}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
