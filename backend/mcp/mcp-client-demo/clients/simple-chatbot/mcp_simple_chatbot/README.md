# MCP Simple Chatbot (Cliente MCP + AWS Diagram Server + Bedrock)

Cliente **MCP** (Model Context Protocol) con **enrutamiento por intención** y **pipelines de tools**.
Permite conversar y, cuando corresponde, **generar diagramas de arquitectura AWS** usando el servidor oficial [`aws-diagram-mcp-server`](https://awslabs.github.io/mcp/servers/aws-diagram-mcp-server) y la librería `diagrams`, con LLMs de **Amazon Bedrock** vía `langchain-aws`.

* 🔌 **Modular**: LLM, orquestación, servers y utilidades están separados.
* 🧠 **Clasificación de intención** (texto vs diagrama vs ambos).
* 🛡️ **Normalización/validación** del código antes de ejecutar tools MCP.
* 🧰 **Prewarm**, postprocesado y manejo de errores (incl. *Throttling*).
* 🧱 Lista para **agregar nuevos servers** y nuevas tools como pipelines.

---

## Tabla de contenido

* [Arquitectura](#arquitectura)
* [Requisitos](#requisitos)
* [Instalación](#instalación)
* [Configuración](#configuración)

  * [Variables de entorno](#variables-de-entorno)
  * [`servers_config.json`](#servers_configjson)
* [Estructura del proyecto](#estructura-del-proyecto)
* [Ejecutar](#ejecutar)
* [Cómo funciona](#cómo-funciona)

  * [Flujo de intención → prompt → pipeline](#flujo-de-intención--prompt--pipeline)
  * [Pipeline `generate_diagram`](#pipeline-generate_diagram)
  * [Normalización/validación del código](#normalizaciónvalidación-del-código)
* [Añadir nuevos servidores MCP](#añadir-nuevos-servidores-mcp)
* [Preguntas de prueba (prompts)](#preguntas-de-prueba-prompts)
* [Solución de problemas](#solución-de-problemas)
* [Desarrollo y pruebas](#desarrollo-y-pruebas)
* [Notas de seguridad](#notas-de-seguridad)
* [Licencia](#licencia)

---

## Arquitectura

**Capas principales:**

1. **LLM (`llm/`)**

   * `client.py`: invocación a Bedrock, clasificación de intención, generación de respuesta.
   * `prompts.py`: prompts de sistema (chat vs diagramas) + prompt de intención.
   * `schemas.py`: Pydantic para contratos (`DecisionEnvelope`, `IntentEnvelope`).

2. **Orquestación (`orchestration/`)**

   * `session.py`: bucle REPL, prewarm, resolución de pipelines por tool, manejo de errores.

3. **Servers MCP (`servers/`)**

   * `base.py`: conexión MCP (stdio), listado/ejecución de tools.
   * `hooks/aws_diagram.py`: prewarm y pipeline para `generate_diagram`.

4. **Utilidades (`utilities/`)**

   * Normalización, validación, inyección de `filename`, reemplazos comunes, postproceso.

5. **Config & Entry**

   * `config.py`: carga `.env`, constantes.
   * `main.py`: arranque del REPL.

---

## Requisitos

* **Python 3.10+** (recomendado 3.12).
* Cuenta y permisos en **AWS** para usar **Bedrock** (modelo configurado).
* Node/npm si el servidor MCP se levanta con `npx` (caso `aws-diagram-mcp-server`).

---

## Instalación

```bash
# 1) Clona el repo
git clone <URL_DEL_REPO>
cd mcp_client

# 2) Crea y activa un entorno virtual
python3 -m venv venv-mcp
source venv-mcp/bin/activate  # Windows: venv-mcp\Scripts\activate

# 3) Instala dependencias
pip install -U pip
pip install -r requirements.txt
```

> Si vas a usar el servidor `aws-diagram-mcp-server` vía `npx`, asegúrate de tener Node/npm y que `npx` esté en el PATH.

---

## Configuración

### Variables de entorno

Crea un `.env` en la raíz del proyecto:

```ini
# AWS / Bedrock
AWS_REGION=us-east-1
BEDROCK_MODEL=anthropic.claude-3-sonnet-20240229-v1:0
# También puedes usar perfiles o variables estándar:
# AWS_ACCESS_KEY_ID=...
# AWS_SECRET_ACCESS_KEY=...
# AWS_SESSION_TOKEN=...

# Depuración opcional
MCP_DEBUG_CODE=0
```

> **Recomendado**: usa **credenciales por perfil** (`aws configure`) y roles IAM con permisos a Bedrock en vez de poner llaves estáticas en `.env`.

### `servers_config.json`

Ejemplo mínimo para el servidor de diagramas AWS:

```json
{
  "mcpServers": {
    "awslabs.aws-diagram-mcp-server": {
      "command": "npx",
      "args": [
        "-y",
        "@awslabs/aws-diagram-mcp-server@latest"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

> Puedes agregar más servidores aquí (cada uno con `command`, `args`, `env`).

---

## Estructura del proyecto

```
mcp_client/
├─ main.py
├─ servers_config.json
├─ config.py
├─ orchestration/
│  └─ session.py
├─ servers/
│  ├─ base.py
│  └─ hooks/
│     └─ aws_diagram.py
├─ llm/
│  ├─ client.py
│  ├─ prompts.py
│  └─ schemas.py
└─ utilities/
   ├─ code_normalizer.py
   ├─ code_validator.py
   ├─ code_injection.py
   ├─ common_fixes.py
   └─ postprocess.py
```

---

## Ejecutar

```bash
source venv-mcp/bin/activate
python main.py
```

Aparecerá un REPL:

```
You: hola
Assistant (answer):  ¡Hola! ¿En qué puedo ayudarte?

You: genera un diagrama de aws con cognito, api gateway, lambda y dynamodb
Assistant (tool):  (explicación del diagrama + confirmación de archivo generado)
```

Comandos de salida: `exit`, `quit`, `salir`, `q`, `x`.

---

## Cómo funciona

### Flujo de **intención → prompt → pipeline**

1. **Último mensaje del usuario** → `LLMClient.classify_or_heuristic` decide si la intención es:

   * `diagram`, `text`, `both` o `neither`.
2. Según la intención:

   * Prompt de **diagramas** (`SYSTEM_PROMPT_BASE`) o
   * Prompt de **chat** (`CHAT_SYSTEM`).
3. El LLM devuelve un **`DecisionEnvelope`**:

   * `decision="tool"` → `tool = "generate_diagram"` + `arguments.code`.
   * `decision="answer"` → texto normal.
4. La **orquestación** envía el sobre a un **pipeline** por nombre de tool:

   * `generate_diagram` → pipeline en `servers/hooks/aws_diagram.py`.

### Pipeline `generate_diagram`

**Prewarm (opcional):**

* `get_diagram_examples` y `list_icons` para despertar caches.

**Preproceso:**

* Normaliza el bloque Python del LLM:

  * Elimina imports.
  * Convierte `vpc = Cluster("X")` → `with Cluster("X"):` (y asegura `:`).
  * Aplica **reemplazos comunes** (p. ej. `DynamoDB` → `Dynamodb`, `ALB` → `ELB`, `EventBridge` → `Eventbridge`, etc.).
  * Inyecta `filename="<ruta_absoluta_sin_.png>"` **dentro de** `with Diagram(...)`.
* Valida:

  * Debe existir `with Diagram(`.
  * Debe existir al menos **una conexión** `>>`.
  * No debe haber imports.
  * `ast.parse()` sin errores.

**Ejecución:**

* Llama la tool MCP `generate_diagram` con:

  * `code` (post-normalizado),
  * `filename`,
  * `workspace_dir`,
  * `timeout` (ej. 120 s).

**Postproceso:**

* Lee el payload: `status`, `message`, `path(s)`.
* Normaliza rutas (`file://`), verifica archivo real, limpia residuos.
* Devuelve un mensaje “humano” + explicación del LLM si vino en el sobre.

### Normalización/validación del código

Reglas duras (en el prompt y en validadores):

* **Sin imports** (el server importa `diagrams`).
* Código debe **empezar exactamente** con:
  `with Diagram("<título>", show=False):`
* `with Cluster("..."):` siempre con `with` (no asignaciones).
* **≥ 1** conexión `>>` para que el diagrama tenga flujo.
* Límite de nodos/conexiones razonable (evita timeouts).

---

## Añadir nuevos servidores MCP

1. **Agrega** el server a `servers_config.json`.
2. **Crea** un hook en `servers/hooks/<mi_server>.py` con funciones:

   * `prewarm(server)` (opcional)
   * `preprocess_<tool>(envelope, source_dir) -> (expected_png, tool_args, explanation)`
   * `postprocess_<tool>(result, expected_png, filename, source_dir) -> (ok: bool, msg: str)`
3. **Mapea** la tool al pipeline en `orchestration/session.py`:

   ```python
   pipelines = {
       "generate_diagram": self._run_generate_diagram_pipeline,
       "mi_tool": self._run_mi_tool_pipeline
   }
   ```
4. **Reutiliza utilidades** (`utilities/`) para normalizar/validar/inyectar.

---

## Preguntas de prueba (prompts)

Básicos:

1. *“Genera un diagrama simple de una API Gateway que invoca una Lambda.”*
2. *“Arquitectura serverless con Cognito, API Gateway, Lambda y DynamoDB para usuarios.”*
3. *“Sitio estático en S3 con CloudFront al frente.”*

Red/VPC:

4. *“VPC con subred pública y privada, NAT Gateway y tablas de ruteo; EC2 en privada.”*
5. *“ALB frente a ECS (mapea a ELB) y RDS.”*

Eventos/colas:

6. *“SQS como cola entre API Gateway y una Lambda worker.”*
7. *“Step Functions que coordina tres Lambdas y publica a Eventbridge.”*

Observabilidad/seguridad:

8. *“WAF delante de API Gateway y CloudWatch para logs/alarms.”*

**Negativos (de validación):**

* *“Dibuja con DynamoDB, EventBridge y SecurityGroup”* → Se corrige a `Dynamodb`, `Eventbridge` y `NetworkFirewall`/`WAF "SG"`.
* *“Haz un diagrama sin conexiones”* → Debe rechazar por falta de `>>`.

---

## Solución de problemas

### `ThrottlingException: Too many requests`

* El cliente implementa **backoff exponencial + jitter** y **rate limiting** (si habilitado).
* Consejos:

  * Evita dos invocaciones por turno (usa **heurística** para saltar el clasificador cuando es obvio).
  * Reduce `max_tokens` del clasificador de intención (p. ej. 200).
  * Baja `temperature` en intención (0.0).

### `NameError: name 'DynamoDB' is not defined`

* En `diagrams` se usa **`Dynamodb`** (clase).
* El cliente aplica **COMMON_FIXES** antes de validar/ejecutar.
* Asegúrate de que `utilities/common_fixes.py` esté cargando:

  * `DynamoDB` → `Dynamodb`
  * `EventBridge` → `Eventbridge`
  * `ALB` → `ELB`
  * `SecurityGroup` → `NetworkFirewall` (o `WAF` con label "SG").

### `Could not load 'sarif': No module named 'jschema_to_python'`

* Es opcional (formateadores SARIF). No bloquea PNG.
* Si quieres silenciar:
  `pip install jschema-to-python sarif-om`

### `TimeoutError: Diagram generation timed out after 120 seconds`

* Reduce nodos/conexiones (el prompt ya lo sugiere).
* Aumenta `timeout` a 180–240 s si hace falta.
* Implementa un **reintento “lite”** (máx. 10 nodos/10 conexiones).

### “Bedrock Invoke API… Using twice”

* El flujo puede hacer **dos invocaciones** (intención + respuesta).
* Usa la **heurística previa** para saltar la clasificación cuando la intención es evidente.

---

## Desarrollo y pruebas

### Requisitos de desarrollo

* `requirements.txt` incluye `langchain-aws`, `pydantic`, `dotenv`, etc.
* Servidor MCP levantado por `npx` (o binario) según `servers_config.json`.

### Estilo y logs

* Logs configurados en `main.py` con `logging.basicConfig`.
* Puedes activar `MCP_DEBUG_CODE=1` para imprimir el **código post-normalizado** antes de enviar al server (útil para depurar diagramas).

### Tests manuales (sugeridos)

* **Intención texto**: “¿Qué servicios de AWS recomiendas para una app web?” → `answer`.
* **Intención diagrama**: “Genera un diagrama de aws en el que se conecte una lambda con una instancia de ec2"
