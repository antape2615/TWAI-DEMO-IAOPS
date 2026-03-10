/**
 * mcpService.ts
 *
 * Servicio para comunicarse con el servidor FastAPI MCP (main_api.py)
 * que orquesta los MCP Servers de AWS (diagrama + CloudFormation).
 *
 * Puerto por defecto: 8001 (configurable via VITE_MCP_API_URL)
 */

import axios from 'axios';

const MCP_BASE_URL =
  (import.meta.env.VITE_MCP_API_URL || 'http://localhost:8001') + '/api/ai/aws';

const mcpApi = axios.create({
  baseURL: MCP_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 300_000, // 5 min para operaciones multi-paso
});

// ─── Tipos ────────────────────────────────────────────────────────────────────

export type ChatMode = 'auto' | 'diagram' | 'infrastructure' | 'both';

export interface ChatRequest {
  message: string;
  session_id?: string;
  mode?: ChatMode;
}

export interface ChatResponse {
  mode: 'answer' | 'tool' | 'raw';
  text: string;
  diagram_path?: string | null;
  cfn_data?: Record<string, unknown> | null;
  session_id: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  mode?: ChatResponse['mode'];
  cfn_data?: Record<string, unknown> | null;
  timestamp: Date;
}

export interface McpStatus {
  status: string;
  servers: Array<{ name: string; alive: boolean }>;
  active_sessions: number;
}

// ─── API calls ────────────────────────────────────────────────────────────────

/**
 * Envía un mensaje al MCP y devuelve la respuesta del asistente.
 */
export async function sendChatMessage(req: ChatRequest): Promise<ChatResponse> {
  const response = await mcpApi.post<ChatResponse>('/chat', req);
  return response.data;
}

/**
 * Limpia el historial de conversación en el servidor.
 */
export async function resetSession(session_id = 'default'): Promise<void> {
  await mcpApi.post('/reset', null, { params: { session_id } });
}

/**
 * Obtiene el estado de los servidores MCP.
 */
export async function getMcpStatus(): Promise<McpStatus> {
  const response = await mcpApi.get<McpStatus>('/status');
  return response.data;
}

/**
 * Obtiene el historial guardado en el servidor para una sesión.
 */
export async function getHistory(
  session_id = 'default'
): Promise<{ session_id: string; messages: Array<{ role: string; content: string }> }> {
  const response = await mcpApi.get('/history', { params: { session_id } });
  return response.data;
}

// ─── SSE streaming ────────────────────────────────────────────────────────────

export type SseEventType = 'thinking' | 'step' | 'done' | 'error';

export interface SseThinkingEvent {
  type: 'thinking';
  iteration: number;
  message: string;
}

export interface SseStepEvent {
  type: 'step';
  iteration: number;
  mode: 'tool';
  text: string;
  cfn_data?: Record<string, unknown> | null;
}

export interface SseDoneEvent {
  type: 'done';
  mode: ChatResponse['mode'];
  text: string;
  cfn_data?: Record<string, unknown> | null;
}

export interface SseErrorEvent {
  type: 'error';
  message: string;
}

export type SseEvent = SseThinkingEvent | SseStepEvent | SseDoneEvent | SseErrorEvent;

/**
 * Envía un mensaje al backend usando SSE para recibir actualizaciones en tiempo real.
 * Llama a onEvent por cada evento recibido (thinking, step, done, error).
 */
export async function streamChatMessage(
  req: ChatRequest,
  onEvent: (event: SseEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const baseUrl = import.meta.env.VITE_MCP_API_URL || 'http://localhost:8001';
  const url = `${baseUrl}/api/ai/aws/chat/stream`;

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(req),
    signal,
  });

  if (!response.ok || !response.body) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(text || `HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Parsear bloques SSE delimitados por \n\n
    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() ?? '';

    for (const block of blocks) {
      let eventType = '';
      let dataStr = '';
      for (const line of block.split('\n')) {
        if (line.startsWith('event: ')) eventType = line.slice(7).trim();
        if (line.startsWith('data: '))  dataStr  = line.slice(6).trim();
      }
      if (!dataStr) continue;
      try {
        const payload = JSON.parse(dataStr);
        onEvent({ type: eventType as SseEventType, ...payload });
      } catch {
        // ignorar bloques malformados
      }
    }
  }
}
