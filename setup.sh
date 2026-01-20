#!/bin/bash

# IAOPS Platform - Setup Script
# Este script configura automáticamente el entorno para desarrollo

set -e

echo "🚀 IAOPS Platform - Setup Automático"
echo "======================================"
echo ""

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Verificar si estamos en el directorio correcto
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Error: No se encontró docker-compose.yml${NC}"
    echo "Por favor ejecuta este script desde la raíz del proyecto"
    exit 1
fi

echo "📁 Creando archivos de configuración..."

# Crear backend/.env si no existe
if [ ! -f "backend/.env" ]; then
    echo -e "${YELLOW}📝 Creando backend/.env...${NC}"
    cp backend/.env.example backend/.env 2>/dev/null || cp backend/.env.docker backend/.env
    echo -e "${GREEN}✅ backend/.env creado${NC}"
else
    echo -e "${GREEN}✅ backend/.env ya existe${NC}"
fi

# Crear frontend/.env si no existe
if [ ! -f "frontend/.env" ]; then
    echo -e "${YELLOW}📝 Creando frontend/.env...${NC}"
    cp frontend/.env.example frontend/.env
    echo -e "${GREEN}✅ frontend/.env creado${NC}"
else
    echo -e "${GREEN}✅ frontend/.env ya existe${NC}"
fi

echo ""
echo "🐳 Levantando servicios Docker..."
echo ""

# Levantar Docker Compose
docker-compose up -d

echo ""
echo "⏳ Esperando a que los servicios estén listos..."
sleep 5

# Verificar que los servicios están corriendo
echo ""
echo "📊 Estado de los servicios:"
docker-compose ps

echo ""
echo -e "${GREEN}✅ ¡Setup completado!${NC}"
echo ""
echo "🌐 URLs disponibles:"
echo "  - Backend API: http://localhost:8000"
echo "  - API Docs (Swagger): http://localhost:8000/docs"
echo "  - API Docs (ReDoc): http://localhost:8000/redoc"
echo "  - MkDocs: http://localhost:8001"
echo ""
echo "📱 Para levantar el frontend:"
echo "  cd frontend"
echo "  npm install"
echo "  npm run dev"
echo "  Frontend estará en: http://localhost:3000"
echo ""
echo "📋 Comandos útiles:"
echo "  - Ver logs: docker-compose logs -f"
echo "  - Detener: docker-compose down"
echo "  - Reiniciar: docker-compose restart"
echo ""
echo -e "${GREEN}🎉 ¡Disfruta de IAOPS Platform!${NC}"
