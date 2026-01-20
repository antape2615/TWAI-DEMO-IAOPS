# IAOPS Platform - Quick Setup Guide

## 🚀 Setup Rápido

Sigue estos pasos para levantar la plataforma:

### 1. Archivos de Configuración Ya Creados ✅

Ya he creado los archivos `.env` necesarios con configuración por defecto:
- `backend/.env` - Configuración del backend
- `frontend/.env` - Configuración del frontend

### 2. Levantar Backend con Docker

```bash
# Desde la raíz del proyecto
docker-compose up -d
```

Esto levantará:
- ✅ PostgreSQL en puerto 5432
- ✅ Redis en puerto 6379
- ✅ Backend FastAPI en puerto 8000
- ✅ Documentación MkDocs en puerto 8001

### 3. Verificar que está funcionando

```bash
# Ver logs
docker-compose logs -f backend

# Verificar servicios
docker-compose ps

# Probar API
curl http://localhost:8000/health
```

Deberías ver: `{"status":"healthy","version":"1.0.0"}`

### 4. Acceder a la Documentación API

Abre en tu navegador:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **MkDocs**: http://localhost:8001

### 5. Levantar Frontend (en otra terminal)

```bash
cd frontend
npm install
npm run dev
```

El frontend estará en: http://localhost:3000

## 🔧 Configuración Opcional

### Si tienes credenciales de AWS/Azure/GCP

Edita `backend/.env` y agrega tus credenciales:

```env
# AWS
AWS_ACCESS_KEY_ID=tu-access-key
AWS_SECRET_ACCESS_KEY=tu-secret-key

# Azure
AZURE_CLIENT_ID=tu-client-id
AZURE_CLIENT_SECRET=tu-secret
AZURE_TENANT_ID=tu-tenant-id
AZURE_SUBSCRIPTION_ID=tu-subscription-id

# OpenAI (para generación de arquitecturas)
OPENAI_API_KEY=tu-openai-key
```

Luego reinicia el backend:
```bash
docker-compose restart backend
```

## 🐛 Solución de Problemas

### Error: Puerto 8000 en uso
```bash
# Encuentra el proceso
lsof -i :8000

# O cambia el puerto en docker-compose.yml
ports:
  - "8080:8000"  # Cambia 8000 a 8080
```

### Error: No se puede conectar a PostgreSQL
```bash
# Verifica que PostgreSQL está corriendo
docker-compose ps postgres

# Ver logs
docker-compose logs postgres

# Reiniciar
docker-compose restart postgres
```

### Reconstruir contenedores
```bash
# Si hiciste cambios en el código
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## 📊 URLs Importantes

| Servicio | URL |
|----------|-----|
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| API Docs (ReDoc) | http://localhost:8000/redoc |
| Frontend | http://localhost:3000 |
| MkDocs | http://localhost:8001 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

## 🎯 Primeros Pasos

1. **Crear un cliente** en el frontend (http://localhost:3000/clients)
2. **Generar arquitectura** con IA (http://localhost:3000/ai-generator)
3. **Ver recursos** cloud (http://localhost:3000/resources)

## 🛑 Detener Todo

```bash
docker-compose down

# Si quieres borrar los datos también
docker-compose down -v
```

## ✅ Todo Listo!

Si siguiste estos pasos, deberías tener:
- ✅ Backend corriendo en puerto 8000
- ✅ Base de datos PostgreSQL funcionando
- ✅ Redis funcionando
- ✅ Frontend listo para instalar y ejecutar
- ✅ Documentación accesible

¡Disfruta de IAOPS Platform! 🚀
