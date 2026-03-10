# ─────────────────────────────────────────────────────────────────────────────
# IAOPS MCP API — Dockerfile
#
# Levanta el servidor FastAPI que expone los MCP Servers de AWS al frontend:
#   POST /api/ai/aws/chat
#   POST /api/ai/aws/reset
#   GET  /api/ai/aws/status
#   GET  /api/ai/aws/history
#
# Requisitos del host:
#   - Variables AWS en .env.mcp (ver .env.example)
#   - Puerto 8001 libre (configurable con MCP_API_PORT)
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

# ── Sistema ───────────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    graphviz \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── uv / uvx (necesario para lanzar los MCP Servers de AWS como subprocesos) ──
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:/root/.local/bin:$PATH"

# ── Dependencias Python ───────────────────────────────────────────────────────
WORKDIR /app
COPY mcp_simple_chatbot/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# ── Código fuente ─────────────────────────────────────────────────────────────
COPY mcp_simple_chatbot/ ./

# ── Configuración ─────────────────────────────────────────────────────────────
ENV MCP_API_PORT=8001
ENV PYTHONUNBUFFERED=1

EXPOSE 8001

# ── Arranque ──────────────────────────────────────────────────────────────────
CMD ["python", "main_api.py"]
