import { useState, useEffect, useMemo } from 'react';
import {
    Cloud,
    Github,
    ShieldCheck,
    Save,
    Loader2,
    Edit2,
    Lock,
    RefreshCw,
    Info,
    CheckCircle,
    AlertCircle,
    LayoutDashboard
} from 'lucide-react';
import { monitoringService } from '@/services/monitoringService';
import { clientService } from '@/services/clientService';
import { settingsService, SystemDefaults } from '@/services/settingsService';
import { Client } from '@/types';
import toast from 'react-hot-toast';

type SettingsTab = 'cloud' | 'repositories' | 'cicd' | 'general' | 'grafana';

export function Settings() {
    const [activeTab, setActiveTab] = useState<SettingsTab>('cloud');
    const [clients, setClients] = useState<Client[]>([]);
    const [selectedClientId, setSelectedClientId] = useState<string>('');
    const [systemDefaults, setSystemDefaults] = useState<SystemDefaults | null>(null);
    const [isEditing, setIsEditing] = useState(false);
    const [saving, setSaving] = useState(false);
    const [loading, setLoading] = useState(true);

    const selectedClient = useMemo(() =>
        clients.find(c => c.id === selectedClientId),
        [clients, selectedClientId]);

    useEffect(() => {
        initSettings();
    }, []);

    const initSettings = async () => {
        setLoading(true);
        try {
            const [clientsData, defaultsData] = await Promise.all([
                clientService.getAll(),
                settingsService.getDefaults()
            ]);
            setClients(clientsData);
            setSystemDefaults(defaultsData);
            if (clientsData.length > 0) {
                setSelectedClientId(clientsData[0].id);
            }
        } catch (error) {
            toast.error('Error al cargar la configuración');
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedClientId) return;

        setSaving(true);
        try {
            const form = e.target as HTMLFormElement;
            const formData = new FormData(form);
            const data: Record<string, any> = {};
            formData.forEach((value, key) => { data[key] = value; });

            if (activeTab === 'cloud') {
                const provider = selectedClient?.tech_profile.clouds[0] || 'azure';
                await settingsService.updateCloud(selectedClientId, provider, {
                    client_id: data.azure_client_id || data.aws_key,
                    client_secret: data.azure_secret || data.aws_secret,
                    tenant_id: data.azure_tenant,
                    subscription_id: data.azure_sub
                }, data.region);
            } else if (activeTab === 'repositories') {
                await settingsService.updateRepo(selectedClientId, 'github', {
                    token: data.github_token
                }, data.org);
            } else if (activeTab === 'cicd') {
                await settingsService.updateCICD(selectedClientId, data.cicd_provider, data.cicd_token, data.cicd_org, data.cicd_project);
            } else if (activeTab === 'grafana') {
                await monitoringService.configureGrafana({
                    client_id: selectedClientId,
                    azure_tenant_id: data.azure_tenant_id,
                    azure_subscription_id: data.azure_subscription_id,
                    azure_client_id: data.azure_client_id,
                    azure_client_secret: data.azure_client_secret
                });
            }

            toast.success('Configuración guardada correctamente. Los cambios se aplicarán sin reiniciar.');
        } catch (error) {
            toast.error('Error al guardar la configuración');
        } finally {
            setSaving(false);
            setIsEditing(false);
        }
    };

    // Filtrado de Tabs basado en perfil tecnológico del cliente
    const filteredTabs = useMemo(() => {
        const baseTabs = [
            { id: 'cloud', name: 'Nube (Cloud)', icon: Cloud, show: true },
            { id: 'repositories', name: 'Repositorios', icon: Github, show: true },
            { id: 'cicd', name: 'CI/CD Pipelines', icon: ShieldCheck, show: true },
            { id: 'grafana', name: 'Grafana & Monitor', icon: LayoutDashboard, show: true },
        ];

        if (!selectedClient) return baseTabs.map(t => ({ ...t, disabled: true }));

        const profile = selectedClient.tech_profile;

        return baseTabs.map(tab => {
            let isRelevant = true;
            if (tab.id === 'cloud' && profile.clouds.length === 0) isRelevant = false;
            if (tab.id === 'repositories' && profile.repositories.length === 0) isRelevant = false;

            // CI/CD y Grafana usualmente es relevante si hay cloud
            if ((tab.id === 'cicd' || tab.id === 'grafana') && profile.clouds.length === 0) isRelevant = false;

            return {
                ...tab,
                show: isRelevant
            };
        });
    }, [selectedClient]);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-start">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900">Configuración Centralizada</h1>
                    <p className="mt-2 text-gray-600">
                        Gestiona las conexiones para <strong>{selectedClient?.name || 'IAOPS'}</strong> heredando valores globales de <code>.env.docker</code>.
                    </p>
                </div>
                <div className="flex space-x-2">
                    <button
                        onClick={initSettings}
                        className="p-2 text-gray-400 hover:text-primary-600 transition-colors bg-white rounded-lg border"
                        title="Recargar desde el sistema"
                    >
                        <RefreshCw className="w-5 h-5" />
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                {/* Sidebar de Clientes */}
                <div className="lg:col-span-1 space-y-4">
                    <div className="card p-4">
                        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">Seleccionar Cliente</h3>
                        <div className="space-y-2">
                            {clients.map(c => (
                                <button
                                    key={c.id}
                                    onClick={() => {
                                        setSelectedClientId(c.id);
                                        setIsEditing(false);
                                    }}
                                    className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all ${selectedClientId === c.id
                                        ? 'bg-primary-50 text-primary-700 font-medium border border-primary-200 shadow-sm'
                                        : 'text-gray-600 hover:bg-gray-100'
                                        }`}
                                >
                                    <p className="truncate">{c.name}</p>
                                    <p className="text-[10px] opacity-70 truncate">{c.description || 'Sin descripción'}</p>
                                </button>
                            ))}
                        </div>
                    </div>

                    {selectedClient && (
                        <div className="card p-4 bg-gray-50 border-gray-200">
                            <h3 className="text-xs font-bold text-gray-400 uppercase mb-2">Perfil Detectado</h3>
                            <div className="flex flex-wrap gap-2">
                                {selectedClient.tech_profile.clouds.map(c => (
                                    <span key={c} className="px-2 py-0.5 bg-blue-100 text-blue-700 text-[10px] font-bold rounded uppercase">{c}</span>
                                ))}
                                <span className="px-2 py-0.5 bg-green-100 text-green-700 text-[10px] font-bold rounded uppercase">
                                    {selectedClient.tech_profile.standards.infrastructure}
                                </span>
                                <span className="px-2 py-0.5 bg-purple-100 text-purple-700 text-[10px] font-bold rounded uppercase">
                                    {selectedClient.tech_profile.standards.cicd}
                                </span>
                            </div>
                        </div>
                    )}
                </div>

                {/* Panel de Configuración */}
                <div className="lg:col-span-3 space-y-6">
                    <div className="card p-0 overflow-hidden">
                        <div className="flex bg-gray-100 border-b overflow-x-auto scrollbar-hide">
                            {filteredTabs.filter(t => t.show).map((tab) => {
                                const Icon = tab.icon;
                                return (
                                    <button
                                        key={tab.id}
                                        onClick={() => setActiveTab(tab.id as SettingsTab)}
                                        className={`flex items-center space-x-2 px-6 py-4 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${activeTab === tab.id
                                            ? 'border-primary-600 text-primary-600 bg-white'
                                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-200'
                                            }`}
                                    >
                                        <Icon className="w-5 h-5" />
                                        <span>{tab.name}</span>
                                    </button>
                                );
                            })}
                        </div>

                        <div className="p-6">
                            <div className="flex justify-between items-center mb-6">
                                <div className="flex items-center space-x-2">
                                    <div className={`p-1.5 rounded-full ${isEditing ? 'bg-orange-100 text-orange-600' : 'bg-green-100 text-green-600'}`}>
                                        {isEditing ? <Edit2 className="w-4 h-4" /> : <Lock className="w-4 h-4" />}
                                    </div>
                                    <h2 className="text-xl font-bold text-gray-900">
                                        {activeTab === 'cloud' && 'Conexión a Nube'}
                                        {activeTab === 'repositories' && 'Tokens de Repositorio'}
                                        {activeTab === 'cicd' && 'Configuración de Pipelines'}
                                        {activeTab === 'grafana' && 'Grafana & Azure Monitor'}
                                    </h2>
                                </div>

                                <button
                                    type="button"
                                    onClick={() => setIsEditing(!isEditing)}
                                    className={`btn flex items-center space-x-2 ${isEditing
                                        ? 'btn-outline border-orange-200 text-orange-600 hover:bg-orange-50'
                                        : 'btn-outline border-gray-200 text-gray-600 hover:bg-gray-50'
                                        }`}
                                >
                                    {isEditing ? <span>Cancelar Edición</span> : <><Edit2 className="w-4 h-4" /><span>Editar Parámetros</span></>}
                                </button>
                            </div>

                            <form onSubmit={handleSave} className="space-y-6">
                                {activeTab === 'cloud' && (
                                    <div className="space-y-6">
                                        {/* Azure Section */}
                                        {selectedClient?.tech_profile.clouds.includes('azure') && (
                                            <div className="space-y-4 p-4 border rounded-lg bg-gray-50/50">
                                                <div className="flex items-center space-x-2 text-blue-700 font-bold mb-2">
                                                    <CheckCircle className="w-4 h-4" />
                                                    <span>Parámetros de Azure (Heredados de .env.docker)</span>
                                                </div>
                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                    <div>
                                                        <label className="label">Client ID</label>
                                                        <input
                                                            type="text"
                                                            disabled={!isEditing}
                                                            className="input font-mono text-xs"
                                                            placeholder={isEditing ? 'Ingrese Client ID' : systemDefaults?.cloud.azure.client_id}
                                                        />
                                                        {!isEditing && <p className="mt-1 text-[10px] text-gray-400">Heredado del sistema</p>}
                                                    </div>
                                                    <div>
                                                        <label className="label">Subscription ID</label>
                                                        <input
                                                            type="text"
                                                            disabled={!isEditing}
                                                            className="input font-mono text-xs"
                                                            placeholder={isEditing ? 'Ingrese Subscription ID' : systemDefaults?.cloud.azure.subscription_id}
                                                        />
                                                    </div>
                                                </div>
                                                {isEditing && (
                                                    <div className="p-3 bg-blue-50 border border-blue-100 rounded text-xs text-blue-700 flex gap-2">
                                                        <Info className="w-4 h-4 flex-shrink-0" />
                                                        <p>Modificar estos valores sobrescribirá la configuración global de <code>.env.docker</code> solo para este cliente.</p>
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        {/* AWS Section */}
                                        {selectedClient?.tech_profile.clouds.includes('aws') && (
                                            <div className="space-y-4 p-4 border rounded-lg bg-gray-50/50">
                                                <div className="flex items-center space-x-2 text-orange-700 font-bold mb-2">
                                                    <AlertCircle className="w-4 h-4" />
                                                    <span>Parámetros de AWS (Pendientes)</span>
                                                </div>
                                                <div>
                                                    <label className="label">Access Key ID</label>
                                                    <input
                                                        name="aws_access_key_id"
                                                        type="text"
                                                        disabled={!isEditing}
                                                        className="input font-mono text-xs"
                                                        placeholder={systemDefaults?.cloud.aws.access_key || 'No configurado en .env'}
                                                    />
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}

                                {activeTab === 'repositories' && (
                                    <div className="space-y-6">
                                        <div className="p-4 bg-primary-50 rounded-lg border border-primary-100">
                                            <div className="flex space-x-3">
                                                <Github className="w-5 h-5 text-primary-600 flex-shrink-0" />
                                                <div>
                                                    <p className="text-sm font-bold text-primary-900">GitHub Personal Access Token</p>
                                                    <p className="text-xs text-primary-700">
                                                        Con solo el token, el sistema listará automáticamente todos tus repositorios accesibles.
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                        <div>
                                            <label className="label">GitHub Token (PAT)</label>
                                            <input
                                                name="github_token"
                                                type="password"
                                                disabled={!isEditing}
                                                className="input font-mono"
                                                placeholder={isEditing ? 'github_pat_...' : systemDefaults?.repositories.github.token}
                                            />
                                            <p className="mt-1 text-xs text-gray-500">
                                                Genera un Personal Access Token con permisos <code className="bg-gray-100 px-1 rounded">repo</code> en GitHub.
                                                El sistema automáticamente listará todos los repositorios accesibles.
                                            </p>
                                        </div>
                                    </div>
                                )}

                                {activeTab === 'cicd' && (
                                    <div className="space-y-6">
                                        <div className="grid grid-cols-1 md::grid-cols-2 gap-4">
                                            <div>
                                                <label className="label">Proveedor CI/CD</label>
                                                <select name="cicd_provider" className="input" disabled={!isEditing}>
                                                    <option value="github-actions" selected={selectedClient?.tech_profile.standards.cicd === 'github-actions'}>GitHub Actions</option>
                                                    <option value="azure-devops" selected={selectedClient?.tech_profile.standards.cicd === 'azure-devops'}>Azure DevOps</option>
                                                </select>
                                            </div>
                                            <div>
                                                <label className="label">Entorno Destino</label>
                                                <select name="cicd_env" className="input" disabled={!isEditing}>
                                                    <option value="production">Producción</option>
                                                    <option value="testing">Testing / Staging</option>
                                                </select>
                                            </div>
                                        </div>
                                        <div>
                                            <label className="label">Token CI/CD</label>
                                            <input name="cicd_token" type="password" className="input font-mono" placeholder="************************" disabled={!isEditing} />
                                        </div>
                                        <div className="flex items-center p-3 bg-green-50 text-green-700 rounded-lg text-xs space-x-2">
                                            <CheckCircle className="w-4 h-4" />
                                            <span>Pipelines automáticos habilitados para {selectedClient?.tech_profile.standards.infrastructure}</span>
                                        </div>
                                    </div>
                                )}

                                {activeTab === 'grafana' && (
                                    <div className="space-y-6">
                                        <div className="p-4 bg-purple-50 rounded-lg border border-purple-100">
                                            <div className="flex space-x-3">
                                                <LayoutDashboard className="w-5 h-5 text-purple-600 flex-shrink-0" />
                                                <div>
                                                    <p className="text-sm font-bold text-purple-900">Integración con Azure Monitor</p>
                                                    <p className="text-xs text-purple-700">
                                                        Configura las credenciales para que Grafana pueda acceder a las métricas de tus recursos en Azure.
                                                        Se requiere un Service Principal con rol de "Reader".
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            <div>
                                                <label className="label">Azure Tenant ID</label>
                                                <input
                                                    name="azure_tenant_id"
                                                    type="text"
                                                    disabled={!isEditing}
                                                    className="input font-mono text-xs"
                                                    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                                                />
                                            </div>
                                            <div>
                                                <label className="label">Azure Subscription ID</label>
                                                <input
                                                    name="azure_subscription_id"
                                                    type="text"
                                                    disabled={!isEditing}
                                                    className="input font-mono text-xs"
                                                    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                                                />
                                            </div>
                                            <div>
                                                <label className="label">Azure Client ID (App ID)</label>
                                                <input
                                                    name="azure_client_id"
                                                    type="text"
                                                    disabled={!isEditing}
                                                    className="input font-mono text-xs"
                                                    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                                                />
                                            </div>
                                            <div>
                                                <label className="label">Azure Client Secret</label>
                                                <input
                                                    name="azure_client_secret"
                                                    type="password"
                                                    disabled={!isEditing}
                                                    className="input font-mono text-xs"
                                                    placeholder="************************"
                                                />
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {isEditing && (
                                    <div className="pt-4 border-t flex justify-end space-x-3">
                                        <button
                                            type="button"
                                            onClick={() => setIsEditing(false)}
                                            className="btn border-gray-300 text-gray-700 hover:bg-gray-100"
                                        >
                                            Descartar
                                        </button>
                                        <button
                                            type="submit"
                                            disabled={saving}
                                            className="btn btn-primary flex items-center space-x-2"
                                        >
                                            {saving ? (
                                                <Loader2 className="w-5 h-5 animate-spin" />
                                            ) : (
                                                <Save className="w-5 h-5" />
                                            )}
                                            <span>Guardar Cambios</span>
                                        </button>
                                    </div>
                                )}
                            </form>
                        </div>
                    </div>

                    <div className="card p-4 bg-blue-50 border-blue-100 flex items-start space-x-3">
                        <Info className="w-5 h-5 text-blue-600 mt-0.5" />
                        <div className="text-xs text-blue-800 space-y-1">
                            <p className="font-bold uppercase tracking-wider text-[10px]">Nota de Seguridad:</p>
                            <p>
                                Los valores mostrados aquí provienen prioritariamente de la base de datos de este cliente.
                                Si no se han configurado valores específicos, el sistema utiliza las variables definidas en <code>.env.docker</code> de forma transparente.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
