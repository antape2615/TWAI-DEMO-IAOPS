import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { X } from 'lucide-react';
import { ClientCreate, CloudProvider, RepositoryProvider, InfrastructureStandard, CICDStandard } from '@/types';
import { clientService } from '@/services/clientService';
import toast from 'react-hot-toast';

interface CreateClientFormData {
  name: string;
  description?: string;
  infrastructure: InfrastructureStandard;
  cicd: CICDStandard;
  container_orchestration?: string;
  monitoring?: string;
  logging?: string;
}

export function CreateClientModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [loading, setLoading] = useState(false);
  const [selectedClouds, setSelectedClouds] = useState<CloudProvider[]>([]);
  const [selectedRepos, setSelectedRepos] = useState<RepositoryProvider[]>([]);

  const { register, handleSubmit, formState: { errors } } = useForm<CreateClientFormData>();

  const toggleCloud = (cloud: CloudProvider) => {
    setSelectedClouds(prev =>
      prev.includes(cloud)
        ? prev.filter(c => c !== cloud)
        : [...prev, cloud]
    );
  };

  const toggleRepo = (repo: RepositoryProvider) => {
    setSelectedRepos(prev =>
      prev.includes(repo)
        ? prev.filter(r => r !== repo)
        : [...prev, repo]
    );
  };

  const onSubmit = async (data: CreateClientFormData) => {
    if (selectedClouds.length === 0) {
      toast.error('Debes seleccionar al menos un cloud provider');
      return;
    }

    if (selectedRepos.length === 0) {
      toast.error('Debes seleccionar al menos un repositorio');
      return;
    }

    setLoading(true);
    try {
      const clientData: ClientCreate = {
        name: data.name,
        description: data.description,
        tech_profile: {
          clouds: selectedClouds,
          repositories: selectedRepos,
          standards: {
            infrastructure: data.infrastructure,
            cicd: data.cicd,
            container_orchestration: data.container_orchestration || 'kubernetes',
            monitoring: data.monitoring || 'prometheus',
            logging: data.logging || 'elk',
          },
        },
      };

      await clientService.create(clientData);
      toast.success('Cliente creado exitosamente');
      onSuccess();
      onClose();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Error al crear cliente';
      toast.error(errorMessage);
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-2xl font-bold text-gray-900">Nuevo Cliente</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-6">
          {/* Información Básica */}
          <div className="space-y-4">
            <h3 className="font-semibold text-gray-900">Información Básica</h3>

            <div>
              <label className="label">Nombre *</label>
              <input
                type="text"
                className="input"
                placeholder="Empresa ABC"
                {...register('name', { required: 'Nombre es requerido' })}
              />
              {errors.name && (
                <p className="text-sm text-red-600 mt-1">{errors.name.message}</p>
              )}
            </div>

            <div>
              <label className="label">Descripción</label>
              <textarea
                rows={3}
                className="input"
                placeholder="Descripción del cliente..."
                {...register('description')}
              />
            </div>
          </div>

          {/* Cloud Providers */}
          <div className="space-y-4">
            <h3 className="font-semibold text-gray-900">Cloud Providers *</h3>
            <div className="flex flex-wrap gap-3">
              {(['aws', 'azure', 'gcp'] as CloudProvider[]).map((cloud) => (
                <button
                  key={cloud}
                  type="button"
                  onClick={() => toggleCloud(cloud)}
                  className={`px-4 py-2 rounded-lg font-medium transition-colors ${selectedClouds.includes(cloud)
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                    }`}
                >
                  {cloud.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Repositorios */}
          <div className="space-y-4">
            <h3 className="font-semibold text-gray-900">Repositorios *</h3>
            <div className="flex flex-wrap gap-3">
              {(['github', 'gitlab', 'bitbucket'] as RepositoryProvider[]).map((repo) => (
                <button
                  key={repo}
                  type="button"
                  onClick={() => toggleRepo(repo)}
                  className={`px-4 py-2 rounded-lg font-medium transition-colors ${selectedRepos.includes(repo)
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                    }`}
                >
                  {repo.charAt(0).toUpperCase() + repo.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Estándares */}
          <div className="space-y-4">
            <h3 className="font-semibold text-gray-900">Estándares Tecnológicos</h3>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Infraestructura *</label>
                <select
                  className="input"
                  {...register('infrastructure', { required: true })}
                >
                  <option value="terraform">Terraform</option>
                  <option value="cloudformation">CloudFormation</option>
                  <option value="arm_templates">ARM Templates</option>
                  <option value="pulumi">Pulumi</option>
                </select>
              </div>

              <div>
                <label className="label">CI/CD *</label>
                <select
                  className="input"
                  {...register('cicd', { required: true })}
                >
                  <option value="github-actions">GitHub Actions</option>
                  <option value="gitlab-ci">GitLab CI</option>
                  <option value="azure-devops">Azure DevOps</option>
                  <option value="jenkins">Jenkins</option>
                  <option value="circleci">CircleCI</option>
                </select>
              </div>

              <div>
                <label className="label">Orquestación</label>
                <input
                  type="text"
                  className="input"
                  placeholder="kubernetes"
                  defaultValue="kubernetes"
                  {...register('container_orchestration')}
                />
              </div>

              <div>
                <label className="label">Monitoring</label>
                <input
                  type="text"
                  className="input"
                  placeholder="prometheus"
                  defaultValue="prometheus"
                  {...register('monitoring')}
                />
              </div>
            </div>
          </div>

          {/* Botones */}
          <div className="flex items-center justify-end space-x-3 pt-4 border-t border-gray-200">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary"
            >
              {loading ? 'Creando...' : 'Crear Cliente'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
