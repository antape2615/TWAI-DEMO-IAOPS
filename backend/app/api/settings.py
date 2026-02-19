from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.core.database import get_db
from app.models.database import CloudCredentialsModel, RepositoryCredentialsModel, CICDCredentialsModel
from app.models.schemas import CloudConfigUpdate, RepoConfigUpdate, CICDConfigUpdate
from app.core.logging import logger
from typing import Dict, Any

router = APIRouter()

@router.get("/defaults")
async def get_system_defaults():
    """
    Retorna los valores por defecto configurados en el sistema (variables de entorno)
    Enmascara los secretos por seguridad.
    """
    def mask(value: str) -> str:
        if not value: return ""
        return f"{value[:4]}****{value[-4:]}" if len(value) > 8 else "****"

    return {
        "cloud": {
            "aws": {
                "access_key": mask(settings.AWS_ACCESS_KEY_ID),
                "region": settings.AWS_DEFAULT_REGION
            },
            "azure": {
                "client_id": mask(settings.AZURE_CLIENT_ID),
                "tenant_id": mask(settings.AZURE_TENANT_ID),
                "subscription_id": mask(settings.AZURE_SUBSCRIPTION_ID)
            },
            "gcp": {
                "project_id": settings.GCP_PROJECT_ID
            }
        },
        "repositories": {
            "github": {
                "token": mask(settings.GITHUB_TOKEN)
            },
            "gitlab": {
                "url": settings.GITLAB_URL,
                "token": mask(settings.GITLAB_TOKEN)
            }
        }
    }

@router.post("/cloud", status_code=status.HTTP_200_OK)
async def update_cloud_config(data: CloudConfigUpdate, db: AsyncSession = Depends(get_db)):
    """Guarda o actualiza credenciales de nube para un cliente"""
    logger.info(f"Actualizando configuración cloud para cliente {data.client_id} ({data.provider})")
    
    result = await db.execute(
        select(CloudCredentialsModel)
        .where(CloudCredentialsModel.client_id == data.client_id, CloudCredentialsModel.provider == data.provider)
    )
    creds = result.scalar_one_or_none()
    
    if creds:
        creds.credentials = data.credentials
        creds.region = data.region
    else:
        creds = CloudCredentialsModel(
            client_id=data.client_id,
            provider=data.provider,
            credentials=data.credentials,
            region=data.region
        )
        db.add(creds)
    
    await db.commit()
    return {"status": "success", "message": "Configuración cloud actualizada"}

@router.post("/repositories")
async def update_repo_config(data: RepoConfigUpdate, db: AsyncSession = Depends(get_db)):
    """Guarda o actualiza credenciales de repositorio"""
    result = await db.execute(
        select(RepositoryCredentialsModel)
        .where(RepositoryCredentialsModel.client_id == data.client_id, RepositoryCredentialsModel.provider == data.provider)
    )
    creds = result.scalar_one_or_none()
    
    if creds:
        creds.credentials = data.credentials
        creds.organization = data.organization
    else:
        creds = RepositoryCredentialsModel(
            client_id=data.client_id,
            provider=data.provider,
            credentials=data.credentials,
            organization=data.organization
        )
        db.add(creds)
    
    await db.commit()
    return {"status": "success", "message": "Configuración de repositorio actualizada"}

@router.post("/cicd")
async def update_cicd_config(data: CICDConfigUpdate, db: AsyncSession = Depends(get_db)):
    """Guarda o actualiza credenciales de CI/CD"""
    result = await db.execute(
        select(CICDCredentialsModel)
        .where(CICDCredentialsModel.client_id == data.client_id, CICDCredentialsModel.provider == data.provider)
    )
    creds = result.scalar_one_or_none()
    
    if creds:
        creds.token = data.token
        creds.organization = data.organization
        creds.project = data.project
    else:
        creds = CICDCredentialsModel(
            client_id=data.client_id,
            provider=data.provider,
            token=data.token,
            organization=data.organization,
            project=data.project
        )
        db.add(creds)
    
    await db.commit()
    return {"status": "success", "message": "Configuración de CI/CD actualizada"}
