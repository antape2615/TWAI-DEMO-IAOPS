"""
Aplicación principal FastAPI - IAOPS Platform
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import logger
from app.api import clients, deployments, architecture, resources, dashboard, repositories, cicd, settings as api_settings, monitoring
from app.core.database import engine
from app.models.database import Base

# Crear aplicación
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Intelligent AI Operations Platform - Orquestación Multi-Cloud y Multi-Repositorio",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(
    clients.router,
    prefix=f"{settings.API_V1_PREFIX}/clients",
    tags=["clients"]
)

app.include_router(
    deployments.router,
    prefix=f"{settings.API_V1_PREFIX}/deployments",
    tags=["deployments"]
)

app.include_router(
    architecture.router,
    prefix=f"{settings.API_V1_PREFIX}/architecture",
    tags=["architecture"]
)

app.include_router(
    resources.router,
    prefix=f"{settings.API_V1_PREFIX}/resources",
    tags=["resources"]
)

app.include_router(
    repositories.router,
    prefix=f"{settings.API_V1_PREFIX}/repositories",
    tags=["repositories"]
)

app.include_router(
    cicd.router,
    prefix=f"{settings.API_V1_PREFIX}/cicd",
    tags=["cicd"]
)

app.include_router(api_settings.router, prefix=f"{settings.API_V1_PREFIX}/settings", tags=["settings"])

app.include_router(
    dashboard.router,
    prefix=f"{settings.API_V1_PREFIX}/dashboard",
    tags=["dashboard"]
)

app.include_router(
    monitoring.router,
    prefix=f"{settings.API_V1_PREFIX}/monitoring",
    tags=["monitoring"]
)


@app.on_event("startup")
async def startup_event():
    """Evento de inicio de la aplicación"""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Inicializar tablas de base de datos
    try:
        from app.migrate_db import migrate
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Ejecutar migraciones manuales para columnas nuevas
        await migrate()
        
        logger.info("Base de datos persistente inicializada y migrada correctamente")
    except Exception as e:
        logger.error(f"Error inicializando base de datos: {e}")

    logger.info(f"Debug mode: {settings.DEBUG}")


@app.on_event("shutdown")
async def shutdown_event():
    """Evento de cierre de la aplicación"""
    logger.info("Shutting down IAOPS Platform")


@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "api": settings.API_V1_PREFIX
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
