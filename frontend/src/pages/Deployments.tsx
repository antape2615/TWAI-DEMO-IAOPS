import { useCallback, useEffect, useState } from 'react';
import { Cloud, Loader2, CheckCircle, XCircle, Clock, ExternalLink, Play, GitBranch, Github, GitMerge } from 'lucide-react';
import { api } from '@/services/api';
import { clientService } from '@/services/clientService';
import { repositoryService, Branch, Commit } from '@/services/repositoryService';
import { resourceService, DeployableResource } from '@/services/resourceService';
import { deploymentService, DeploymentHistoryItem } from '@/services/deploymentService';
import { Client } from '@/types';
import { format } from 'date-fns';
import { es } from 'date-fns/locale';
import { clsx } from 'clsx';
import toast from 'react-hot-toast';

interface Repository {
    id: string;
    name: string;
    url: string;
    clone_url: string;
    provider: string;
    private?: boolean;
}

interface DeploymentRecord extends DeploymentHistoryItem {}

export function Deployments() {
    const [deployments, setDeployments] = useState<DeploymentRecord[]>([]);
    const [clients, setClients] = useState<Client[]>([]);
    const [selectedClientId, setSelectedClientId] = useState<string>('');
    const [loading, setLoading] = useState(false);
    const [activeTab, setActiveTab] = useState<'new' | 'history' | 'verification' | 'repositories'>('history');

    // Repository states
    const [repositories, setRepositories] = useState<Repository[]>([]);
    const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
    const [branches, setBranches] = useState<Branch[]>([]);
    const [commits, setCommits] = useState<Commit[]>([]);
    const [selectedBranch, setSelectedBranch] = useState('main');

    // Deployable resources state
    const [deployableResources, setDeployableResources] = useState<DeployableResource[]>([]);
    const [selectedResource, setSelectedResource] = useState<string>('');
    const [selectedEnvironment, setSelectedEnvironment] = useState<string>('production');

    // Move loadHistory before loadClients since it's called by loadClients
    const loadHistory = useCallback(async (clientId: string) => {
        if (!clientId) return;
        setLoading(true);
        try {
            const response = await api.get(`/deployments/history/${clientId}`);
            setDeployments(response.data);
        } catch (error) {
            console.error('Error loading deployments:', error);
        } finally {
            setLoading(false);
        }
    }, []);

    const loadClients = useCallback(async () => {
        try {
            const data = await clientService.getAll();
            setClients(data);
            if (data.length > 0) {
                setSelectedClientId(data[0].id);
                loadHistory(data[0].id);
            }
        } catch (error) {
            console.error('Error loading clients:', error);
        }
    }, [loadHistory]);

    useEffect(() => {
        loadClients();
    }, [loadClients]);

    const loadDeployableResources = useCallback(async () => {
        if (!selectedClientId) return;
        setLoading(true);
        try {
            const resources = await resourceService.listDeployableResources(selectedClientId);
            setDeployableResources(resources);
        } catch (error) {
            console.error('Error loading deployable resources:', error);
        } finally {
            setLoading(false);
        }
    }, [selectedClientId]);

    const handleRepoSelect = useCallback(async (repo: Repository) => {
        setSelectedRepo(repo);
        try {
            const branchData = await repositoryService.listBranches(selectedClientId, repo.clone_url || repo.url);
            setBranches(branchData);
            if (branchData.length > 0) {
                setSelectedBranch(branchData[0].name);
                const commitData = await repositoryService.listCommits(selectedClientId, repo.clone_url || repo.url, branchData[0].name);
                setCommits(commitData);
            }
        } catch (error) {
            console.error('Error loading repo data:', error);
        }
    }, [selectedClientId]);

    const loadRepositories = useCallback(async () => {
        if (!selectedClientId) return;
        setLoading(true);
        try {
            const repos = await repositoryService.listRepositories(selectedClientId);
            setRepositories(repos);
            if (repos.length > 0) {
                handleRepoSelect(repos[0]);
            }
        } catch (error) {
            console.error('Error loading repositories:', error);
        } finally {
            setLoading(false);
        }
    }, [selectedClientId, handleRepoSelect]);

    useEffect(() => {
        if (selectedClientId && activeTab === 'repositories') {
            loadRepositories();
        }
        if (selectedClientId && activeTab === 'new') {
            loadDeployableResources();
            loadRepositories(); // También cargar repos para el formulario
        }
    }, [selectedClientId, activeTab, loadRepositories, loadDeployableResources]);

    const handleBranchChange = async (branch: string) => {
        setSelectedBranch(branch);
        if (!selectedRepo) return;
        try {
            const commitData = await repositoryService.listCommits(selectedClientId, selectedRepo.clone_url || selectedRepo.url, branch);
            setCommits(commitData);
        } catch (error) {
            console.error('Error loading commits:', error);
        }
    };

    const handleAcceptMerge = async () => {
        if (!selectedClientId || !selectedBranch) return;
        try {
            await repositoryService.acceptMerge(selectedClientId, selectedBranch);
            toast.success(`Merge de ${selectedBranch} aceptado correctamente`);
        } catch (error) {
            console.error('Error accepting merge:', error);
            toast.error('Error al aceptar el merge');
        }
    };

    const handleDeployCode = async () => {
        if (!selectedClientId || !selectedRepo || !selectedBranch || !selectedResource) {
            toast.error('Por favor completa todos los campos');
            return;
        }

        setLoading(true);
        try {
            const selectedResourceObj = deployableResources.find(r => r.id === selectedResource);

            await deploymentService.deployCode({
                client_id: selectedClientId,
                repo_url: selectedRepo.clone_url || selectedRepo.url,
                branch: selectedBranch,
                resource_id: selectedResource,
                resource_type: selectedResourceObj?.resource_type_display || 'sites',
                environment: selectedEnvironment,
                application_type: 'nodejs',  // Could be made configurable in UI
                use_ai_pipeline: true  // Enable AI-generated pipelines
            });

            toast.success('¡Despliegue iniciado exitosamente!');
            setActiveTab('history');
            loadHistory(selectedClientId);
        } catch (error: unknown) {
            const axiosError = error as { response?: { data?: { detail?: string } }; message?: string };
            const errorMessage = axiosError?.response?.data?.detail || 'Error al iniciar el despliegue';
            console.error('Error deploying code:', error);
            toast.error(errorMessage);
        } finally {
            setLoading(false);
        }
    };

    const onClientChange = (id: string) => {
        setSelectedClientId(id);
        loadHistory(id);
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'completed': return <CheckCircle className="w-5 h-5 text-green-500" />;
            case 'failed': return <XCircle className="w-5 h-5 text-red-500" />;
            case 'running': return <Clock className="w-5 h-5 text-blue-500 animate-pulse" />;
            default: return <Clock className="w-5 h-5 text-gray-500" />;
        }
    };

    type TabId = 'new' | 'history' | 'verification' | 'repositories';
    
    const tabs: Array<{ id: TabId; name: string; icon: typeof Play }> = [
        { id: 'new', name: 'Nuevo Despliegue', icon: Play },
        { id: 'history', name: 'Histórico', icon: Clock },
        { id: 'verification', name: 'Verificación', icon: CheckCircle },
        { id: 'repositories', name: 'Repositorios', icon: GitBranch },
    ];

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-end">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900">Operaciones de Despliegue</h1>
                    <p className="mt-2 text-gray-600">
                        Gestiona el ciclo de vida de tus aplicaciones e infraestructura
                    </p>
                </div>

                <div className="w-64">
                    <label className="label">Cliente</label>
                    <select
                        className="input"
                        value={selectedClientId}
                        onChange={(e) => onClientChange(e.target.value)}
                    >
                        <option value="">Seleccionar Cliente...</option>
                        {clients.map(c => (
                            <option key={c.id} value={c.id}>{c.name}</option>
                        ))}
                    </select>
                </div>
            </div>

            <div className="flex space-x-1 bg-gray-100 p-1 rounded-xl w-fit">
                {tabs.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={clsx(
                            'flex items-center space-x-2 px-4 py-2 text-sm font-medium rounded-lg transition-all',
                            activeTab === tab.id
                                ? 'bg-white text-primary-600 shadow-sm'
                                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                        )}
                    >
                        <tab.icon className="w-4 h-4" />
                        <span>{tab.name}</span>
                    </button>
                ))}
            </div>

            {loading ? (
                <div className="flex items-center justify-center h-64">
                    <Loader2 className="w-12 h-12 text-primary-600 animate-spin" />
                </div>
            ) : (
                <div className="space-y-6">
                    {activeTab === 'history' && (
                        <div className="grid grid-cols-1 gap-4">
                            {deployments.length === 0 ? (
                                <div className="card text-center py-12">
                                    <Cloud className="w-16 h-16 text-gray-200 mx-auto mb-4" />
                                    <h3 className="text-lg font-medium text-gray-900">No hay despliegues</h3>
                                    <p className="text-gray-500 mt-1">Este cliente aún no ha realizado ningún despliegue.</p>
                                </div>
                            ) : (
                                deployments.map((deployment) => (
                                    <div key={deployment.id} className="card hover:shadow-md transition-shadow">
                                        <div className="flex items-start justify-between">
                                            <div className="flex items-start space-x-4">
                                                <div className={`p-3 rounded-lg ${deployment.status === 'completed' ? 'bg-green-100' :
                                                    deployment.status === 'failed' ? 'bg-red-100' : 'bg-blue-100'
                                                    }`}>
                                                    <Cloud className={`w-6 h-6 ${deployment.status === 'completed' ? 'text-green-600' :
                                                        deployment.status === 'failed' ? 'text-red-600' : 'text-blue-600'
                                                        }`} />
                                                </div>
                                                <div>
                                                    <div className="flex items-center space-x-2">
                                                        <h3 className="text-lg font-bold text-gray-900 capitalize">
                                                            {deployment.cloud_provider} - {deployment.environment}
                                                        </h3>
                                                        {getStatusIcon(deployment.status)}
                                                    </div>
                                                    <p className="text-sm text-gray-500">
                                                        ID: {deployment.id.substring(0, 8)}... | Region: {deployment.region}
                                                    </p>
                                                    <div className="mt-2 flex items-center space-x-4">
                                                        <span className="text-xs font-medium text-gray-400">
                                                            Iniciado: {format(new Date(deployment.created_at), "dd MMM yyyy, HH:mm", { locale: es })}
                                                        </span>
                                                        {deployment.completed_at && (
                                                            <span className="text-xs font-medium text-gray-400">
                                                                Completado: {format(new Date(deployment.completed_at), "HH:mm", { locale: es })}
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="text-right">
                                                <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase ${deployment.status === 'completed' ? 'bg-green-100 text-green-700' :
                                                    deployment.status === 'failed' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'
                                                    }`}>
                                                    {deployment.status}
                                                </span>
                                                <div className="mt-4">
                                                    <button className="text-primary-600 hover:text-primary-800 flex items-center space-x-1 text-sm font-medium ml-auto">
                                                        <span>Ver Log</span>
                                                        <ExternalLink className="w-4 h-4" />
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    )}

                    {activeTab === 'new' && (
                        <div className="card">
                            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                                <Play className="w-5 h-5 text-primary-600" />
                                Nuevo Despliegue de Código
                            </h3>
                            <p className="text-sm text-gray-600 mb-6">
                                Despliega código desde un repositorio GitHub hacia tus recursos cloud usando GitHub Actions.
                            </p>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label className="label">Repositorio</label>
                                    <select
                                        className="input"
                                        value={selectedRepo?.id || ''}
                                        onChange={(e) => {
                                            const repo = repositories.find(r => r.id === e.target.value);
                                            if (repo) handleRepoSelect(repo);
                                        }}
                                    >
                                        <option value="">Seleccionar repositorio...</option>
                                        {repositories.map((repo: Repository) => (
                                            <option key={repo.id} value={repo.id}>
                                                {repo.name} {repo.private ? '🔒' : ''}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                                <div>
                                    <label className="label">Rama (Branch)</label>
                                    <select className="input" value={selectedBranch} onChange={(e) => setSelectedBranch(e.target.value)}>
                                        <option value="">Seleccionar rama...</option>
                                        {branches.map(b => (
                                            <option key={b.name} value={b.name}>{b.name}</option>
                                        ))}
                                    </select>
                                </div>
                                <div className="md:col-span-2">
                                    <label className="label">Recurso Destino</label>
                                    <select
                                        className="input"
                                        value={selectedResource}
                                        onChange={(e) => setSelectedResource(e.target.value)}
                                    >
                                        <option value="">
                                            {loading ? 'Cargando recursos...' : 'Seleccionar recurso...'}
                                        </option>
                                        {deployableResources.map((resource: DeployableResource) => (
                                            <option key={resource.id} value={resource.id}>
                                                {resource.name} ({resource.resource_type_display}) - {resource.location || resource.region}
                                            </option>
                                        ))}
                                    </select>
                                    <p className="mt-1 text-xs text-gray-500">
                                        Se listarán App Services, VMs, Functions, Containers y Kubernetes donde puedes desplegar código
                                    </p>
                                </div>
                                <div>
                                    <label className="label">Ambiente</label>
                                    <select
                                        className="input"
                                        value={selectedEnvironment}
                                        onChange={(e) => setSelectedEnvironment(e.target.value)}
                                    >
                                        <option value="dev">Desarrollo</option>
                                        <option value="staging">Staging</option>
                                        <option value="production">Producción</option>
                                    </select>
                                </div>
                            </div>
                            <div className="mt-6 flex justify-end">
                                <button
                                    className="btn btn-primary flex items-center space-x-2"
                                    onClick={handleDeployCode}
                                    disabled={loading || !selectedRepo || !selectedBranch || !selectedResource}
                                >
                                    {loading ? (
                                        <>
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                            <span>Desplegando...</span>
                                        </>
                                    ) : (
                                        <>
                                            <Play className="w-4 h-4" />
                                            <span>Iniciar Despliegue</span>
                                        </>
                                    )}
                                </button>
                            </div>
                        </div>
                    )}

                    {activeTab === 'verification' && (
                        <div className="card">
                            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                                <CheckCircle className="w-5 h-5 text-green-600" />
                                Verificación Post-Despliegue
                            </h3>
                            <p className="text-sm text-gray-600 mb-6">
                                Estado de salud de los últimos despliegues realizados.
                            </p>
                            {deployments.length === 0 ? (
                                <div className="text-center py-12">
                                    <CheckCircle className="w-16 h-16 text-gray-200 mx-auto mb-4" />
                                    <p className="text-gray-500">No hay despliegues para verificar</p>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {deployments.slice(0, 5).map((deployment) => (
                                        <div key={deployment.id} className="p-4 border border-gray-200 rounded-lg">
                                            <div className="flex items-center justify-between">
                                                <div>
                                                    <h4 className="font-medium text-gray-900">
                                                        {deployment.cloud_provider} - {deployment.environment}
                                                    </h4>
                                                    <p className="text-sm text-gray-500">
                                                        {format(new Date(deployment.created_at), "dd MMM yyyy, HH:mm", { locale: es })}
                                                    </p>
                                                </div>
                                                <div className="flex items-center space-x-2">
                                                    {getStatusIcon(deployment.status)}
                                                    <span className={`text-sm font-medium ${deployment.status === 'completed' ? 'text-green-600' :
                                                        deployment.status === 'failed' ? 'text-red-600' : 'text-blue-600'
                                                        }`}>
                                                        {deployment.status}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {activeTab === 'repositories' && (
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            <div className="lg:col-span-1 card">
                                <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                                    <Github className="w-5 h-5 text-gray-700" />
                                    Repositorios
                                </h3>
                                {repositories.length === 0 ? (
                                    <p className="text-sm text-gray-500">No hay repositorios configurados</p>
                                ) : (
                                    <div className="space-y-2">
                                        {repositories.map((repo: Repository) => (
                                            <button
                                                key={repo.id}
                                                onClick={() => handleRepoSelect(repo)}
                                                className={clsx(
                                                    'w-full text-left p-3 rounded-lg border transition-all',
                                                    selectedRepo?.id === repo.id
                                                        ? 'border-primary-500 bg-primary-50'
                                                        : 'border-gray-200 hover:border-gray-300'
                                                )}
                                            >
                                                <p className="font-medium text-sm text-gray-900">{repo.name}</p>
                                                <p className="text-xs text-gray-500">{repo.url}</p>
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>

                            <div className="lg:col-span-2 card">
                                {selectedRepo ? (
                                    <div className="space-y-4">
                                        <div>
                                            <h3 className="text-lg font-bold text-gray-900">{selectedRepo.name}</h3>
                                            <p className="text-sm text-gray-500">{selectedRepo.url}</p>
                                        </div>

                                        <div className="flex items-center space-x-4">
                                            <div className="flex-1">
                                                <label className="label">Rama (Branch)</label>
                                                <select
                                                    className="input"
                                                    value={selectedBranch}
                                                    onChange={(e) => handleBranchChange(e.target.value)}
                                                >
                                                    {branches.map(b => (
                                                        <option key={b.name} value={b.name}>{b.name}</option>
                                                    ))}
                                                </select>
                                            </div>
                                            <div className="pt-6">
                                                <button
                                                    onClick={handleAcceptMerge}
                                                    className="btn btn-primary flex items-center space-x-2"
                                                >
                                                    <GitMerge className="w-4 h-4" />
                                                    <span>Aceptar Merge</span>
                                                </button>
                                            </div>
                                        </div>

                                        <div>
                                            <label className="label">Últimos Commits</label>
                                            <div className="max-h-96 overflow-y-auto space-y-2">
                                                {commits.map(commit => (
                                                    <div key={commit.sha} className="p-3 bg-gray-50 border border-gray-200 rounded-lg hover:border-primary-300 transition-colors">
                                                        <div className="flex justify-between items-start">
                                                            <div className="flex-1">
                                                                <p className="font-mono text-xs text-gray-500">{commit.sha.substring(0, 7)}</p>
                                                                <p className="text-sm font-medium text-gray-900 mt-1">{commit.message}</p>
                                                                <p className="text-xs text-gray-500 mt-1">por {commit.author}</p>
                                                            </div>
                                                            <span className="text-xs text-gray-400">
                                                                {format(new Date(commit.date), "dd MMM, HH:mm", { locale: es })}
                                                            </span>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="flex flex-col items-center justify-center h-64 text-center">
                                        <Github className="w-12 h-12 text-gray-300 mb-4" />
                                        <p className="text-gray-500">Selecciona un repositorio para ver sus detalles</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
