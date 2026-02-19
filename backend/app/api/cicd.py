from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from app.core.database import get_db
from app.models.database import CICDCredentialsModel
from app.core.logging import logger

router = APIRouter()

@router.post("/deploy-code")
async def trigger_deployment(client_id: str, resource_id: str, branch: str = "main", db: AsyncSession = Depends(get_db)):
    """Simula el disparo de un pipeline de CI/CD para un recurso específico"""
    logger.info(f"Disparando despliegue de código para cliente {client_id}, recurso {resource_id}, rama {branch}")
    
    # En una implementación real, aquí se llamaría a la API de GitHub o Azure DevOps
    # usando las credenciales almacenadas en CICDCredentialsModel
    
    return {
        "status": "success",
        "message": f"Pipeline disparado correctamente para la rama {branch}",
        "pipeline_id": "87654321",
        "url": "https://github.com/demo/repo/actions/runs/87654321"
    }

@router.get("/credentials/{client_id}")
async def get_cicd_credentials(client_id: str, db: AsyncSession = Depends(get_db)):
    """Obtiene las configuraciones de CI/CD para un cliente"""
    from sqlalchemy import select
    result = await db.execute(select(CICDCredentialsModel).where(CICDCredentialsModel.client_id == client_id))
    creds = result.scalars().all()
    
    return [
        {
            "id": c.id,
            "provider": c.provider,
            "organization": c.organization,
            "project": c.project,
            "is_active": c.is_active
        } for c in creds
    ]
