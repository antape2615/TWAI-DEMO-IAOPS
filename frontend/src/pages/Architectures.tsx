import { useState, useEffect } from 'react';
import { Sparkles, Calendar, Search, Edit2, Check, X, Eye, FileJson } from 'lucide-react';
import { architectureService } from '@/services/architectureService';
import { clientService } from '@/services/clientService';
import { Client as ClientType, Architecture } from '@/types';
import { format } from 'date-fns';
import { es } from 'date-fns/locale';
import toast from 'react-hot-toast';

export function Architectures() {
    const [clients, setClients] = useState<ClientType[]>([]);
    const [selectedClientId, setSelectedClientId] = useState<string>('');
    const [architectures, setArchitectures] = useState<Architecture[]>([]);
    const [loading, setLoading] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editName, setEditName] = useState('');
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedArchitecture, setSelectedArchitecture] = useState<Architecture | null>(null);
    const [showViewer, setShowViewer] = useState(false);

    useEffect(() => {
        loadClients();
    }, []);

    useEffect(() => {
        if (selectedClientId) {
            loadHistory(selectedClientId);
        }
    }, [selectedClientId]);

    const loadClients = async () => {
        try {
            const data = await clientService.getAll();
            setClients(data);
            if (data.length > 0 && !selectedClientId) {
                setSelectedClientId(data[0].id);
            }
        } catch (error) {
            toast.error('Error al cargar clientes');
        }
    };

    const loadHistory = async (clientId: string) => {
        setLoading(true);
        try {
            const data = await architectureService.getHistory(clientId);
            setArchitectures(data);
        } catch (error) {
            toast.error('Error al cargar historial');
        } finally {
            setLoading(false);
        }
    };

    const handleEdit = (arch: Architecture) => {
        setEditingId(arch.id || null);
        setEditName(arch.name || '');
    };

    const handleSaveName = async (id: string) => {
        try {
            await architectureService.updateName(id, editName);
            toast.success('Nombre actualizado');
            setEditingId(null);
            loadHistory(selectedClientId);
        } catch (error) {
            toast.error('Error al actualizar nombre');
        }
    };

    const filteredArchitectures = architectures.filter(arch =>
        arch.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        arch.id?.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <div className="space-y-8">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900">Historial de Arquitecturas</h1>
                    <p className="mt-2 text-gray-600">
                        Gestiona y visualiza las arquitecturas generadas para tus clientes
                    </p>
                </div>

                <div className="flex flex-col sm:flex-row gap-3">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                        <input
                            type="text"
                            placeholder="Buscar arquitectura..."
                            className="input pl-10"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                        />
                    </div>

                    <select
                        className="input min-w-[200px]"
                        value={selectedClientId}
                        onChange={(e) => setSelectedClientId(e.target.value)}
                    >
                        <option value="">Seleccionar Cliente</option>
                        {clients.map(c => (
                            <option key={c.id} value={c.id}>{c.name}</option>
                        ))}
                    </select>
                </div>
            </div>

            {loading ? (
                <div className="flex items-center justify-center h-64">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
                </div>
            ) : filteredArchitectures.length === 0 ? (
                <div className="card text-center py-12">
                    <div className="bg-gray-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                        <Sparkles className="w-8 h-8 text-gray-400" />
                    </div>
                    <h3 className="text-lg font-medium text-gray-900">No se encontraron arquitecturas</h3>
                    <p className="text-gray-500 mt-2">
                        Comienza generando una nueva arquitectura en el Generador IA
                    </p>
                    <a href="/generator" className="btn btn-primary mt-6 inline-flex items-center space-x-2">
                        <Sparkles className="w-4 h-4" />
                        <span>Ir al Generador</span>
                    </a>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {filteredArchitectures.map((arch) => (
                        <div key={arch.id} className="card group hover:border-primary-200 transition-all duration-300">
                            <div className="flex justify-between items-start mb-4">
                                <div className="flex-1 mr-2">
                                    {editingId === arch.id ? (
                                        <div className="flex items-center gap-2">
                                            <input
                                                type="text"
                                                className="input text-lg font-bold py-1 px-2"
                                                value={editName}
                                                onChange={(e) => setEditName(e.target.value)}
                                                autoFocus
                                            />
                                            <button onClick={() => handleSaveName(arch.id!)} className="p-1 text-green-600 hover:bg-green-50 rounded">
                                                <Check className="w-4 h-4" />
                                            </button>
                                            <button onClick={() => setEditingId(null)} className="p-1 text-red-600 hover:bg-red-50 rounded">
                                                <X className="w-4 h-4" />
                                            </button>
                                        </div>
                                    ) : (
                                        <div className="flex items-center gap-2">
                                            <h3 className="text-lg font-bold text-gray-900 truncate">
                                                {arch.name || 'Arquitectura sin nombre'}
                                            </h3>
                                            <button
                                                onClick={() => handleEdit(arch)}
                                                className="p-1 text-gray-400 hover:text-primary-600 opacity-0 group-hover:opacity-100 transition-opacity"
                                            >
                                                <Edit2 className="w-4 h-4" />
                                            </button>
                                        </div>
                                    )}
                                    <p className="text-xs text-gray-400 flex items-center mt-1">
                                        <Calendar className="w-3 h-3 mr-1" />
                                        {arch.created_at ? format(new Date(arch.created_at), "PPP p", { locale: es }) : 'Fecha desconocida'}
                                    </p>
                                </div>
                                <div className="p-2 bg-primary-50 rounded-lg">
                                    <Sparkles className="w-5 h-5 text-primary-600" />
                                </div>
                            </div>

                            <div className="space-y-3 mb-6">
                                <div className="flex items-center justify-between text-sm">
                                    <span className="text-gray-500">Cloud</span>
                                    <span className="font-medium text-gray-900 uppercase">
                                        {(arch.architecture as any)?.cloud_provider || 'Multiple'}
                                    </span>
                                </div>
                                <div className="flex items-center justify-between text-sm">
                                    <span className="text-gray-500">Costo Est.</span>
                                    <span className="font-medium text-green-600">
                                        {arch.estimated_cost?.monthly_total || 'N/A'} {arch.estimated_cost?.currency || 'USD'}
                                    </span>
                                </div>
                            </div>

                            <div className="flex gap-2">
                                <button
                                    onClick={() => { setSelectedArchitecture(arch); setShowViewer(true); }}
                                    className="btn btn-secondary flex-1 py-2 text-sm flex items-center justify-center gap-2"
                                >
                                    <Eye className="w-4 h-4" />
                                    Visualizar
                                </button>

                                <button
                                    onClick={() => {
                                        // Descargar JSON
                                        const dataStr = JSON.stringify(arch, null, 2);
                                        const blob = new Blob([dataStr], { type: 'application/json' });
                                        const url = URL.createObjectURL(blob);
                                        const a = document.createElement('a');
                                        a.href = url;
                                        a.download = `${(arch.name || 'arquitectura').replace(/\s+/g, '_')}_${arch.id}.json`;
                                        document.body.appendChild(a);
                                        a.click();
                                        a.remove();
                                        URL.revokeObjectURL(url);
                                    }}
                                    className="btn btn-secondary p-2 group-hover:border-primary-200"
                                >
                                    <FileJson className="w-4 h-4 text-gray-500" />
                                </button>

                                <button
                                    onClick={async () => {
                                        const confirmed = window.confirm('¿Eliminar esta arquitectura? Esta acción no se puede deshacer.');
                                        if (!confirmed) return;
                                        try {
                                            await architectureService.delete(arch.id!);
                                            toast.success('Arquitectura eliminada');
                                            loadHistory(selectedClientId);
                                        } catch (error) {
                                            toast.error('Error al eliminar arquitectura');
                                        }
                                    }}
                                    className="btn btn-danger p-2 text-sm"
                                >
                                    Eliminar
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
            {/* Visor Modal */}
            {showViewer && selectedArchitecture && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-auto p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-xl font-bold">Visualizar Arquitectura</h2>
                            <div className="flex items-center gap-2">
                                <button onClick={() => setShowViewer(false)} className="btn btn-secondary">Cerrar</button>
                            </div>
                        </div>

                        <div className="space-y-4">
                            <h3 className="font-semibold">Metadatos</h3>
                            <pre className="bg-gray-100 p-4 rounded overflow-auto text-sm">{JSON.stringify({
                                id: selectedArchitecture.id,
                                name: selectedArchitecture.name,
                                client_id: selectedArchitecture.client_id,
                                created_at: selectedArchitecture.created_at,
                                estimated_cost: selectedArchitecture.estimated_cost
                            }, null, 2)}</pre>

                            <h3 className="font-semibold">Arquitectura (JSON)</h3>
                            <pre className="bg-gray-100 p-4 rounded overflow-auto text-sm">{JSON.stringify(selectedArchitecture.architecture, null, 2)}</pre>

                            {selectedArchitecture.infrastructure_code && (
                                <>
                                    <h3 className="font-semibold">Código de Infraestructura</h3>
                                    <pre className="bg-gray-900 text-white p-4 rounded overflow-auto text-sm whitespace-pre-wrap">{selectedArchitecture.infrastructure_code}</pre>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
