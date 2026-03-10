import { useState, useEffect, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { Sparkles, Loader2, Server, Cloud, Code, Send, RotateCcw } from 'lucide-react';
import { ArchitectureRequest, Architecture, Client, DeploymentRequest } from '@/types';
import { architectureService } from '@/services/architectureService';
import { clientService } from '@/services/clientService';
import { deploymentService } from '@/services/deploymentService';
import { streamChatMessage, resetSession, ChatMessage, ChatMode } from '@/services/mcpService';
import { Alert } from '@/components/Alert';
import toast from 'react-hot-toast';

// ─── Chat mode config ─────────────────────────────────────────────────────────

const CHAT_MODES: { value: ChatMode; label: string; description: string }[] = [
  { value: 'auto',           label: 'Auto',           description: 'El modelo detecta si quieres diagrama o infraestructura real' },
  { value: 'diagram',        label: 'Diagrama',        description: 'Genera un diagrama visual de arquitectura AWS' },
  { value: 'infrastructure', label: 'Infraestructura', description: 'Crea y gestiona recursos reales en AWS vía CloudFormation' },
];

// ─── MessageBubble ────────────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';
  const modeLabel: Record<string, string> = { tool: '🔧 operación', answer: '💬 respuesta', raw: '📄 raw' };
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div className="max-w-[85%]">
        <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm whitespace-pre-wrap ${
          isUser
            ? 'bg-primary-600 text-white rounded-tr-sm'
            : 'bg-white border border-gray-200 text-gray-800 rounded-tl-sm'
        }`}>
          {msg.content}
        </div>
        <div className={`flex items-center mt-1 gap-1.5 ${isUser ? 'justify-end' : 'justify-start'}`}>
          <span className="text-xs text-gray-400">
            {msg.timestamp.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })}
          </span>
          {!isUser && msg.mode && (
            <span className="text-xs text-gray-400">· {modeLabel[msg.mode] ?? msg.mode}</span>
          )}
        </div>
      </div>
    </div>
  );
}

export function AIGenerator() {
  const [architecture, setArchitecture] = useState<Architecture | null>(null);
  const [loading, setLoading] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [selectedCloud, setSelectedCloud] = useState<string | null>(null);

  // AWS MCP chat state
  const [awsMessages, setAwsMessages] = useState<ChatMessage[]>([]);
  const [mcpLoading, setMcpLoading] = useState(false);
  const [mcpStatusText, setMcpStatusText] = useState('');
  const [mcpMode, setMcpMode] = useState<ChatMode>('auto');
  const [mcpInput, setMcpInput] = useState('');
  const [mcpSessionId] = useState(`session-${Date.now()}`);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const { register, handleSubmit, watch, setValue, formState: { errors } } = useForm<ArchitectureRequest>();

  const selectedClientId = watch('client_id');
  // @ts-ignore - target_clouds is used dynamically
  const watchedCloud = watch('target_clouds');

  // @ts-ignore - watchedCloud is treated as string (single-select in form)
  const isAwsMode = (selectedCloud === 'aws' || String(watchedCloud ?? '') === 'aws') && !!selectedClient;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [awsMessages, mcpLoading]);

  useEffect(() => {
    loadClients();
  }, []);

  useEffect(() => {
    if (selectedClientId && clients.length > 0) {
      const client = clients.find(c => c.id === selectedClientId);
      setSelectedClient(client || null);
      if (client) {
        if (client.tech_profile.clouds.length > 0) {
          const firstCloud = client.tech_profile.clouds[0];
          setValue('target_clouds' as any, firstCloud);
          setSelectedCloud(firstCloud);
        }
        if (client.tech_profile.standards.infrastructure) {
          setValue('infrastructure_standard', client.tech_profile.standards.infrastructure);
        }
      }
    }
  }, [selectedClientId, clients, setValue]);

  const loadClients = async () => {
    try {
      const data = await clientService.getAll();
      setClients(data);
    } catch (error) {
      console.error('Error loading clients:', error);
      toast.error('Error al cargar clientes');
    }
  };

  const onSubmit = async (data: any) => {
    if (!selectedClient) return;

    setLoading(true);
    try {
      // Guardar cual nube se seleccionó para el despliegue posterior
      setSelectedCloud(data.target_clouds);

      // Parse requirements from string to JSON if it's a string
      const parsedData = {
        ...data,
        target_clouds: [data.target_clouds], // El backend espera una lista
        infrastructure_standard: selectedClient.tech_profile.standards.infrastructure // Usar el del cliente
      };

      if (typeof data.requirements === 'string') {
        try {
          // If it's an empty string, set to empty dict
          if (!data.requirements || (data.requirements as string).trim() === '') {
            parsedData.requirements = {};
          } else {
            parsedData.requirements = JSON.parse(data.requirements as unknown as string);
          }
        } catch (e) {
          toast.error('Error: El campo Requerimientos debe ser un JSON válido');
          setLoading(false);
          return;
        }
      }

      const result = await architectureService.generate(parsedData);
      setArchitecture(result);
      toast.success('Arquitectura generada exitosamente');
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } }; message?: string };
      const errorMessage = axiosError?.response?.data?.detail || axiosError?.message || 'Error al generar arquitectura';
      toast.error(errorMessage);
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  // ── AWS MCP chat ─────────────────────────────────────────────────────────

  const handleAwsChat = async () => {
    const text = mcpInput.trim();
    if (!text || mcpLoading) return;

    setAwsMessages(prev => [...prev, { role: 'user', content: text, timestamp: new Date() }]);
    setMcpInput('');
    setMcpLoading(true);
    setMcpStatusText('🤔 Analizando...');

    const abort = new AbortController();
    abortRef.current = abort;

    try {
      await streamChatMessage(
        { message: text, session_id: mcpSessionId, mode: mcpMode },
        (event) => {
          if (event.type === 'thinking') {
            setMcpStatusText(event.message);
          } else if (event.type === 'step') {
            // Resultado intermedio de una herramienta → aparece como burbuja
            setAwsMessages(prev => [...prev, {
              role: 'assistant',
              content: event.text,
              mode: 'tool',
              cfn_data: event.cfn_data ?? undefined,
              timestamp: new Date(),
            }]);
            setMcpStatusText(`⚙️ Paso ${event.iteration} completado, continuando...`);
          } else if (event.type === 'done') {
            setAwsMessages(prev => [...prev, {
              role: 'assistant',
              content: event.text,
              mode: event.mode,
              cfn_data: event.cfn_data ?? undefined,
              timestamp: new Date(),
            }]);
          } else if (event.type === 'error') {
            toast.error(event.message);
            setAwsMessages(prev => [...prev, {
              role: 'assistant',
              content: `❌ Error: ${event.message}`,
              mode: 'answer',
              timestamp: new Date(),
            }]);
          }
        },
        abort.signal,
      );
    } catch (error: unknown) {
      if ((error as { name?: string }).name === 'AbortError') return;
      const e = error as { response?: { data?: { detail?: string } }; message?: string };
      const errText = e?.response?.data?.detail || e?.message || 'Error al comunicarse con el asistente AWS';
      toast.error(errText);
      setAwsMessages(prev => [...prev, {
        role: 'assistant',
        content: `❌ Error: ${errText}`,
        mode: 'answer',
        timestamp: new Date(),
      }]);
    } finally {
      setMcpLoading(false);
      setMcpStatusText('');
      abortRef.current = null;
    }
  };

  const handleResetSession = async () => {
    abortRef.current?.abort();
    try { await resetSession(mcpSessionId); } catch { /* ignore */ }
    setAwsMessages([]);
    setMcpLoading(false);
    setMcpStatusText('');
    toast.success('Conversación reiniciada');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAwsChat(); }
  };

  // ─────────────────────────────────────────────────────────────────────────

  const handleDeploy = async () => {
    if (!architecture || !selectedClient || !architecture.infrastructure_code) return;

    setDeploying(true);
    try {
      const deployRequest: DeploymentRequest = {
        target: {
          client_id: selectedClient.id,
          cloud_provider: (selectedCloud || selectedClient.tech_profile.clouds[0]) as any,
          region: 'eastus', // Default region
          environment: 'dev',
        },
        infrastructure_code: architecture.infrastructure_code,
        architecture_metadata: architecture.architecture as Record<string, unknown>
      };

      await deploymentService.deploy(deployRequest);
      toast.success(`Despliegue completado exitosamente en ${selectedCloud || 'Azure'}`);
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } }; message?: string };
      let errorMessage = axiosError?.response?.data?.detail || axiosError?.message || 'Error en el despliegue';

      // Parse common Azure errors for better UX
      if (errorMessage.includes("Website with given name") && errorMessage.includes("already exists")) {
        errorMessage = "Error: El nombre del App Service ya está en uso globalmente en Azure. Por favor elige un nombre único y regenera.";
      } else if (errorMessage.includes("dnsPrefix") && (errorMessage.includes("already exists") || errorMessage.includes("invalid"))) {
        errorMessage = "Error: El prefijo DNS del cluster AKS es inválido o ya existe. Intenta con otro nombre.";
      } else if (errorMessage.includes("AuthorizationFailed")) {
        errorMessage = "Error de Permisos: La cuenta no tiene permisos suficientes en la suscripción.";
      } else if (errorMessage.includes("InvalidTemplateDeployment")) {
        // Try to extract inner error if possible, otherwise keep generic
        if (errorMessage.includes("The value of parameter dnsPrefix is invalid")) {
          errorMessage = "Error: El prefijo DNS para AKS es inválido.";
        }
      }

      toast.error(errorMessage, { duration: 5000 });
      console.error('Deployment error:', error);
    } finally {
      setDeploying(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Generador de Arquitecturas con IA</h1>
        <p className="mt-2 text-gray-600">
          {isAwsMode
            ? 'Genera diagramas y crea infraestructura real en AWS mediante lenguaje natural'
            : 'La IA genera arquitecturas respetando el perfil tecnológico del cliente'}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form */}
        <div className="space-y-6">
          <div className="card">
            <div className="flex items-center space-x-2 mb-6">
              <Sparkles className="w-6 h-6 text-primary-600" />
              <h2 className="text-xl font-semibold text-gray-900">
                {isAwsMode ? 'Asistente AWS con IA' : 'Nueva Arquitectura'}
              </h2>
            </div>

            <form
              onSubmit={isAwsMode ? (e) => { e.preventDefault(); handleAwsChat(); } : handleSubmit(onSubmit)}
              className="space-y-4"
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="label">Cliente</label>
                  <select
                    className="input"
                    {...register('client_id', { required: 'Cliente es requerido' })}
                  >
                    <option value="">Seleccionar cliente...</option>
                    {clients.map(client => (
                      <option key={client.id} value={client.id}>
                        {client.name}
                      </option>
                    ))}
                  </select>
                  {errors.client_id && (
                    <p className="text-sm text-red-600 mt-1">{errors.client_id.message}</p>
                  )}
                </div>

                {selectedClient && (
                  <div>
                    <label className="label">Nube de Destino</label>
                    <select
                      className="input capitalize"
                      {...register('target_clouds' as any, { required: 'Nube es requerida' })}
                      onChange={(e) => { setValue('target_clouds' as any, e.target.value); setSelectedCloud(e.target.value); }}
                    >
                      {selectedClient.tech_profile.clouds.map(cloud => (
                        <option key={cloud} value={cloud}>{cloud}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              {selectedClient && !isAwsMode && (
                <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 text-sm space-y-2">
                  <div className="flex items-center text-blue-800 font-medium mb-2">
                    <Server className="w-4 h-4 mr-2" />
                    Estándares del Cliente
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <span className="text-blue-600 block text-xs uppercase tracking-wider">IaC</span>
                      <div className="mt-1">
                        <span className="bg-blue-100 text-blue-800 px-2 py-0.5 rounded text-xs capitalize">
                          {selectedClient.tech_profile.standards.infrastructure.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                    <div>
                      <span className="text-blue-600 block text-xs uppercase tracking-wider">CI/CD</span>
                      <div className="mt-1">
                        <span className="bg-purple-100 text-purple-800 px-2 py-0.5 rounded text-xs capitalize">
                          {selectedClient.tech_profile.standards.cicd.replace('-', ' ')}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {isAwsMode ? (
                <>
                  <div>
                    <label className="label">Modo</label>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      {CHAT_MODES.map(m => (
                        <button key={m.value} type="button" title={m.description}
                          onClick={() => setMcpMode(m.value)}
                          className={`flex items-center justify-center gap-1 px-2 py-2 rounded-lg border text-xs font-medium transition-colors ${
                            mcpMode === m.value
                              ? 'bg-primary-600 text-white border-primary-600'
                              : 'bg-white text-gray-700 border-gray-300 hover:border-primary-400'
                          }`}
                        >
                          {m.label}
                        </button>
                      ))}
                    </div>
                    <p className="text-xs text-gray-500 mt-1.5">
                      {CHAT_MODES.find(m => m.value === mcpMode)?.description}
                    </p>
                  </div>

                  <div>
                    <label className="label">Mensaje</label>
                    <textarea rows={4} className="input resize-none"
                      placeholder={mcpMode === 'diagram'
                        ? '"Genera un diagrama serverless con API Gateway, Lambda y DynamoDB"'
                        : mcpMode === 'infrastructure'
                        ? '"Crea un bucket S3 con versionamiento habilitado"'
                        : 'Escribe tu solicitud en lenguaje natural...'}
                      value={mcpInput}
                      onChange={e => setMcpInput(e.target.value)}
                      onKeyDown={handleKeyDown}
                    />
                    <p className="text-xs text-gray-400 mt-1">Enter para enviar · Shift+Enter nueva línea</p>
                  </div>

                  <div className="flex gap-3">
                    <button type="submit" disabled={mcpLoading || !mcpInput.trim()}
                      className="btn btn-primary flex-1 flex items-center justify-center space-x-2">
                      {mcpLoading
                        ? <><Loader2 className="w-4 h-4 animate-spin" /><span>Procesando...</span></>
                        : <><Send className="w-4 h-4" /><span>Enviar</span></>}
                    </button>
                    <button type="button" onClick={handleResetSession}
                      className="btn btn-outline flex items-center space-x-1.5" title="Limpiar conversación">
                      <RotateCcw className="w-4 h-4" /><span>Reset</span>
                    </button>
                  </div>
                </>
              ) : (
                <>
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
                      <><Loader2 className="w-5 h-5 animate-spin" /><span>Generando...</span></>
                    ) : (
                      <><Sparkles className="w-5 h-5" /><span>Generar Arquitectura</span></>
                    )}
                  </button>
                </>
              )}
            </form>
          </div>
        </div>

        {/* Result / AWS Chat */}
        <div className={`card ${isAwsMode ? 'flex flex-col' : 'h-fit'}`}>
          {isAwsMode ? (
            /* ── AWS conversation panel ──────────────────────────── */
            <>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-900">Conversación</h2>
                <div className="flex items-center gap-2">
                  <span className="text-xs bg-orange-100 text-orange-700 px-2 py-1 rounded-full font-medium">☁ AWS</span>
                  <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-full">{awsMessages.length} msg</span>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto min-h-[400px] max-h-[560px] pr-1">
                {awsMessages.length === 0 && !mcpLoading && (
                  <div className="flex flex-col items-center justify-center h-full text-gray-400 space-y-3 pt-16">
                    <Sparkles className="w-10 h-10 text-primary-200" />
                    <div className="text-center">
                      <p className="font-medium text-gray-500">Asistente AWS listo</p>
                      <p className="text-sm mt-1 max-w-xs">Puedes pedir diagramas, crear recursos reales o hacer preguntas sobre AWS</p>
                    </div>
                    <div className="grid grid-cols-1 gap-2 mt-2 w-full max-w-sm px-4">
                      {[
                        { mode: 'diagram' as ChatMode,        text: 'Genera un diagrama serverless con Lambda y DynamoDB' },
                        { mode: 'infrastructure' as ChatMode,  text: 'Crea un bucket S3 con versionamiento habilitado' },
                        { mode: 'infrastructure' as ChatMode,  text: 'Lista todas mis funciones Lambda' },
                      ].map((s, i) => (
                        <button key={i} type="button"
                          className="text-left text-xs text-gray-500 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-lg px-3 py-2 transition-colors"
                          onClick={() => { setMcpMode(s.mode); setMcpInput(s.text); }}>
                          {s.mode === 'diagram' ? '📐' : '🏗️'} "{s.text}"
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {awsMessages.map((msg, i) => <MessageBubble key={i} msg={msg} />)}

                {mcpLoading && (
                  <div className="flex justify-start mb-3">
                    <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
                      <div className="flex items-center gap-2">
                        <div className="flex items-center gap-1">
                          {['-0.3s', '-0.15s', '0s'].map((d, i) => (
                            <div key={i} className="w-2 h-2 rounded-full bg-primary-400 animate-bounce"
                              style={{ animationDelay: d }} />
                          ))}
                        </div>
                        {mcpStatusText && (
                          <span className="text-xs text-gray-500 ml-1">{mcpStatusText}</span>
                        )}
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              <div className="mt-3 pt-3 border-t border-gray-100 text-center">
                <p className="text-xs text-gray-400">
                  Modo: <span className="font-medium text-primary-600 capitalize">{mcpMode}</span>
                  {' · '}Powered by AWS Bedrock + MCP Servers
                </p>
              </div>
            </>
          ) : (
            /* ── Classic result panel ────────────────────────────── */
            <>
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
            <div className="space-y-6">
              <div>
                <h3 className="font-semibold text-gray-900 mb-2">
                  Descripción General
                </h3>
                <p className="text-sm text-gray-600">
                  {typeof architecture.architecture === 'object'
                    ? (architecture.architecture as any).architecture_overview || 'Arquitectura generada'
                    : 'Arquitectura generada'}
                </p>
              </div>

              {(architecture.architecture as any)?.components && (architecture.architecture as any).components.length > 0 && (
                <div>
                  <h3 className="font-semibold text-gray-900 mb-2">
                    Componentes ({(architecture.architecture as any).components.length})
                  </h3>
                  <div className="space-y-2">
                    {(architecture.architecture as any).components.map((component: any, index: number) => (
                      <div
                        key={index}
                        className="p-3 bg-gray-50 rounded-lg border border-gray-200"
                      >
                        <p className="font-medium text-gray-900">{component.name || 'Componente'}</p>
                        {component.cloud_service && (
                          <p className="text-sm text-gray-600">{component.cloud_service}</p>
                        )}
                        {component.description && (
                          <p className="text-xs text-gray-500 mt-1">{component.description}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {architecture.estimated_cost && (
                <div>
                  <h3 className="font-semibold text-gray-900 mb-2">
                    Estimación de Costos
                  </h3>
                  <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                    {architecture.estimated_cost.monthly_estimate ? (
                      <>
                        <p className="text-lg font-bold text-green-700">
                          {typeof architecture.estimated_cost.monthly_estimate === 'object'
                            ? `$${(architecture.estimated_cost.monthly_estimate as any).min || 0} - $${(architecture.estimated_cost.monthly_estimate as any).max || 0} /mes`
                            : `$${architecture.estimated_cost.monthly_estimate} /mes`}
                        </p>
                        <p className="text-sm text-green-600">
                          {architecture.estimated_cost.currency || 'USD'}
                        </p>
                      </>
                    ) : (
                      <p className="text-sm text-gray-600">Estimación no disponible</p>
                    )}
                  </div>
                </div>
              )}

              {architecture.recommendations && architecture.recommendations.length > 0 && (
                <div>
                  <h3 className="font-semibold text-gray-900 mb-2">
                    Recomendaciones
                  </h3>
                  <ul className="space-y-1">
                    {architecture.recommendations.map((rec: string, index: number) => (
                      <li key={index} className="text-sm text-gray-600 flex items-start">
                        <span className="text-primary-600 mr-2">•</span>
                        {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {architecture.infrastructure_code && (
                <div className="border border-gray-200 rounded-lg overflow-hidden">
                  <div className="bg-gray-50 px-4 py-2 border-b border-gray-200 flex items-center justify-between">
                    <div className="flex items-center space-x-2 text-sm font-medium text-gray-700">
                      <Code className="w-4 h-4" />
                      <span>Código de Infraestructura</span>
                      {selectedClient && (
                        <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2.5 py-0.5 rounded uppercase">
                          {selectedClient.tech_profile.standards.infrastructure.replace('_', ' ')}
                        </span>
                      )}
                    </div>
                  </div>
                  <pre className="p-4 bg-gray-900 text-gray-100 overflow-x-auto text-sm font-mono leading-relaxed max-h-96">
                    {architecture.infrastructure_code}
                  </pre>

                  {/* Deploy Button */}
                  <div className="bg-gray-50 px-4 py-3 border-t border-gray-200 flex justify-end">
                    <button
                      onClick={handleDeploy}
                      disabled={deploying}
                      className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50"
                    >
                      {deploying ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Desplegando...
                        </>
                      ) : (
                        <>
                          <Cloud className="w-4 h-4 mr-2" />
                          Desplegar en {selectedCloud || 'Cloud'}
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}

              {/* Debug: Ver datos raw */}
              <div className="mt-4">
                <details className="text-xs">
                  <summary className="cursor-pointer text-gray-500 hover:text-gray-700">
                    Ver datos completos (debug)
                  </summary>
                  <pre className="mt-2 p-4 bg-gray-50 rounded-lg overflow-x-auto">
                    {JSON.stringify(architecture, null, 2)}
                  </pre>
                </details>
              </div>
            </div>
          )}
          </>
          )}
        </div>
      </div>
    </div>
  );
}
