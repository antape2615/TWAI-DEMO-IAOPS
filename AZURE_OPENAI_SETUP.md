# Configuración de Azure OpenAI para IAOPS

## 📋 Requisitos Previos

Para usar Azure OpenAI en IAOPS, necesitas:

1. **Cuenta de Azure** con acceso a Azure OpenAI Service
2. **Resource** de Azure OpenAI creado
3. **Deployment** de un modelo GPT-4 o GPT-3.5-turbo
4. **API Key** y **Endpoint** del recurso

---

## 🚀 Paso 1: Obtener Credenciales de Azure OpenAI

### En Azure Portal

1. Ve a [Azure Portal](https://portal.azure.com)
2. Busca tu recurso de **Azure OpenAI**
3. En el menú lateral, ve a **"Keys and Endpoint"**
4. Copia:
   - **KEY 1** o **KEY 2** (cualquiera funciona)
   - **Endpoint** (URL que termina en `.openai.azure.com/`)

### Obtener Deployment Name

1. En tu recurso de Azure OpenAI, ve a **"Model deployments"**
2. Verás algo como:
   - Deployment name: `gpt-4-deployment`
   - Model: `gpt-4`
3. Copia el **deployment name** (ej: `gpt-4-deployment`)

---

## ⚙️ Paso 2: Configurar el Backend

### Opción A: Con Docker (Recomendado)

Edita el archivo `backend/.env`:

```bash
cd /Users/angietatianapena/TWAI-DEMO-IAOPS
nano backend/.env
```

Agrega estas líneas:

```env
# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=tu-api-key-aqui
AZURE_OPENAI_ENDPOINT=https://tu-resource.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT_NAME=tu-deployment-name
AZURE_OPENAI_MODEL=gpt-4
```

**Ejemplo real:**

```env
AZURE_OPENAI_API_KEY=abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
AZURE_OPENAI_ENDPOINT=https://my-company-openai.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-deployment
AZURE_OPENAI_MODEL=gpt-4
```

Reinicia el backend:

```bash
docker-compose restart backend
```

### Opción B: Sin Docker

Si estás corriendo el backend directamente con `uvicorn`:

```bash
cd backend
nano .env
# (agregar las mismas variables de arriba)

# Reiniciar
# Ctrl+C para detener
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 🔍 Paso 3: Verificar la Configuración

### Verificar Variables de Entorno

```bash
# Ver logs del backend
docker-compose logs -f backend

# Deberías ver algo como:
# INFO Azure OpenAI client initialized: gpt-4-deployment
```

### Test de Conexión con cURL

```bash
# Crear un cliente de prueba
curl -X POST http://localhost:8000/api/v1/clients/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Cliente Test",
    "description": "Prueba Azure OpenAI",
    "tech_profile": {
      "clouds": ["aws"],
      "repositories": ["github"],
      "standards": {
        "infrastructure": "terraform",
        "cicd": "github-actions"
      }
    }
  }'

# Copiar el "id" del cliente creado

# Generar arquitectura
curl -X POST http://localhost:8000/api/v1/architecture/generate \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "el-id-que-copiaste",
    "description": "Una aplicación web escalable con base de datos",
    "requirements": {
      "scalability": "high",
      "availability": "99.9%"
    }
  }'
```

---

## 🎯 Paso 4: Probar desde el Frontend

1. **Abrir el frontend**: http://localhost:3000

2. **Crear un Cliente**:
   - Ir a "Clientes"
   - Click en "Nuevo Cliente"
   - Llenar el formulario:
     - Nombre: `Mi Empresa`
     - Clouds: AWS
     - Repos: GitHub
     - Infraestructura: Terraform
     - CI/CD: GitHub Actions
   - Guardar

3. **Generar Arquitectura con IA**:
   - Ir a "Generador IA"
   - Copiar el ID del cliente (está en la lista de clientes)
   - Llenar el formulario:
     - Cliente ID: `<el-id-copiado>`
     - Descripción: `Una API REST escalable con autenticación y base de datos PostgreSQL`
     - Requerimientos (opcional):
       ```json
       {
         "scalability": "high",
         "availability": "99.9%",
         "security": "enterprise"
       }
       ```
   - Click en "Generar Arquitectura"

4. **Ver el Resultado**:
   - La IA generará una arquitectura respetando el tech profile
   - Verás:
     - Descripción general
     - Componentes (servicios AWS reales)
     - Estimación de costos
     - Recomendaciones
     - Código de infraestructura (Terraform)

---

## 📊 Prioridad de Clientes IA

El sistema usa los clientes de IA en este orden:

1. **Azure OpenAI** (si está configurado) ← **PRIORIDAD**
2. **OpenAI** (si está configurado)
3. **Anthropic** (si está configurado)

Si tienes Azure OpenAI configurado, se usará automáticamente.

---

## 🔧 Troubleshooting

### Error: "No hay cliente de IA configurado"

**Solución:**
- Verifica que `backend/.env` tenga las variables de Azure OpenAI
- Reinicia el backend: `docker-compose restart backend`
- Verifica los logs: `docker-compose logs -f backend`

### Error: "Azure OpenAI API key not configured"

**Solución:**
- Verifica que `AZURE_OPENAI_API_KEY` esté en `backend/.env`
- Verifica que no tenga espacios extra
- Verifica que la key sea correcta (cópiala nuevamente de Azure Portal)

### Error: "Deployment not found"

**Solución:**
- Verifica que `AZURE_OPENAI_DEPLOYMENT_NAME` coincida exactamente con el nombre en Azure Portal
- Verifica que el deployment esté activo

### Error: "Endpoint not found"

**Solución:**
- Verifica que `AZURE_OPENAI_ENDPOINT` termine en `/`
- Formato correcto: `https://nombre.openai.azure.com/`

---

## 🎨 Ejemplo Completo de .env

```env
# Application
APP_NAME=IAOPS Platform
APP_VERSION=1.0.0
DEBUG=False
API_V1_PREFIX=/api/v1

# Database
DATABASE_URL=postgresql+asyncpg://iaops:iaops@postgres:5432/iaops

# Security
SECRET_KEY=tu-secret-key-super-seguro-aqui
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]

# AWS Configuration (opcional)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1

# Azure Cloud Configuration (opcional)
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
AZURE_TENANT_ID=
AZURE_SUBSCRIPTION_ID=

# ===================================
# AZURE OPENAI (IMPORTANTE) ← CONFIGURAR ESTO
# ===================================
AZURE_OPENAI_API_KEY=abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
AZURE_OPENAI_ENDPOINT=https://my-company-openai.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-deployment
AZURE_OPENAI_MODEL=gpt-4

# OpenAI Configuration (opcional, solo si no usas Azure)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4-turbo-preview

# Anthropic Configuration (opcional)
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-3-opus-20240229

# Redis
REDIS_URL=redis://redis:6379/0

# Celery
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
```

---

## ✅ Checklist de Verificación

- [ ] Tengo acceso a Azure OpenAI Service
- [ ] Copié la API Key de Azure Portal
- [ ] Copié el Endpoint de Azure Portal
- [ ] Copié el Deployment Name de Azure Portal
- [ ] Agregué las variables a `backend/.env`
- [ ] Reinicié el backend: `docker-compose restart backend`
- [ ] Verifiqué los logs: `docker-compose logs -f backend`
- [ ] Vi el mensaje: "Azure OpenAI client initialized"
- [ ] Creé un cliente de prueba en el frontend
- [ ] Generé una arquitectura con IA
- [ ] La IA generó una respuesta correcta

---

## 🎉 ¡Listo!

Una vez configurado, el sistema usará Azure OpenAI para:

- ✅ Generar arquitecturas cloud
- ✅ Respetar el tech profile del cliente
- ✅ Usar solo servicios reales (AWS, Azure, GCP)
- ✅ Generar código de infraestructura (Terraform, CloudFormation, etc.)
- ✅ Estimar costos
- ✅ Proporcionar recomendaciones

---

## 📚 Documentación Adicional

- [Azure OpenAI Service Docs](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [IAOPS Documentation](http://localhost:8001)

---

**¿Necesitas ayuda?** Revisa los logs del backend:

```bash
docker-compose logs -f backend | grep -i "openai\|error"
```
