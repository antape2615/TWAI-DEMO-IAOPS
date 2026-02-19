from fastapi import APIRouter, HTTPException, status, Depends
from typing import Dict, Any, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import httpx
import re
import base64
import asyncio
import os
from app.models.schemas import DeploymentTarget, Client
from app.models.database import ClientModel, DeploymentHistoryModel, CICDCredentialsModel
from app.orchestrators.iaops_orchestrator import orchestrator
from app.core.database import get_db
from app.core.logging import logger
from app.core.config_resolver import ConfigResolver
from app.connectors.cicd.dispatcher import CICDDispatcher

router = APIRouter()

class DeploymentRequest(BaseModel):
    """Request de despliegue"""
    target: DeploymentTarget
    infrastructure_code: str
    architecture_metadata: Optional[Dict[str, Any]] = None
    repository_config: Optional[Dict[str, Any]] = None

class CodeDeploymentRequest(BaseModel):
    """Request para despliegue de código desde repositorio"""
    client_id: str
    repo_url: str
    branch: str
    resource_id: str
    resource_type: str
    environment: str = "production"
    application_type: str = "nodejs"  # nodejs, python, dotnet, java, go
    use_ai_pipeline: bool = True  # Usar IA para generar el pipeline

@router.post("/deploy")
async def deploy_infrastructure(request: DeploymentRequest, db: AsyncSession = Depends(get_db)):
    """
    Despliega infraestructura en el cloud especificado y guarda histórico en DB
    """
    # Verificar cliente en DB
    result = await db.execute(select(ClientModel).where(ClientModel.id == request.target.client_id))
    client_model = result.scalar_one_or_none()
    
    if not client_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {request.target.client_id} no encontrado"
        )
    
    # Crear record de histórico (pendente)
    history = DeploymentHistoryModel(
        client_id=client_model.id,
        cloud_provider=request.target.cloud_provider,
        region=request.target.region,
        environment=request.target.environment,
        status="running",
        deployment_data={
            "target": request.target.model_dump(),
            "metadata": request.architecture_metadata
        }
    )
    db.add(history)
    await db.commit()
    
    # Convertir a esquema Pydantic para el orquestador
    client = Client(
        id=client_model.id,
        name=client_model.name,
        description=client_model.description,
        tech_profile=client_model.tech_profile,
        is_active=client_model.is_active,
        created_at=client_model.created_at,
        updated_at=client_model.updated_at
    )
    
    try:
        logger.info(f"Iniciando despliegue para {client.name} (Ref: {history.id})")
        
        # Orquestar despliegue
        result = await orchestrator.orchestrate_deployment(
            client=client,
            target=request.target,
            infrastructure_code=request.infrastructure_code,
            architecture_metadata=request.architecture_metadata,
            repository_config=request.repository_config
        )
        
        # Actualizar histórico a completado
        history.status = "completed"
        history.completed_at = datetime.utcnow()
        await db.commit()
        
        return result
        
    except Exception as e:
        logger.error(f"Error en despliegue: {e}")
        # Actualizar histórico a fallido
        history.status = "failed"
        history.error_message = str(e)
        history.completed_at = datetime.utcnow()
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/code")
async def deploy_code(request: CodeDeploymentRequest, db: AsyncSession = Depends(get_db)):
    """
    Despliega código automáticamente según el tipo de CI/CD configurado en el cliente.
    Soporta: GitHub Actions, Azure DevOps, GitLab CI, Jenkins, CircleCI
    """
    # Verificar cliente
    result = await db.execute(select(ClientModel).where(ClientModel.id == request.client_id))
    client_model = result.scalar_one_or_none()
    
    if not client_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {request.client_id} no encontrado"
        )
    
    # Obtener tipo de CI/CD configurado
    tech_profile = client_model.tech_profile
    if not tech_profile or "standards" not in tech_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cliente sin configuración de tecnología (standards)"
        )
    
    cicd_type = tech_profile.get("standards", {}).get("cicd")
    if not cicd_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cliente sin tipo de CI/CD configurado"
        )
    
    logger.info(f"Cliente {client_model.name} usa CI/CD type: {cicd_type}")
    
    # Obtener credenciales de CI/CD
    cicd_creds_result = await db.execute(
        select(CICDCredentialsModel).where(
            (CICDCredentialsModel.client_id == request.client_id) &
            (CICDCredentialsModel.provider == cicd_type) &
            (CICDCredentialsModel.is_active == True)
        )
    )
    cicd_creds = cicd_creds_result.scalar_one_or_none()
    
    if not cicd_creds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se encontraron credenciales de CI/CD ({cicd_type}) para este cliente"
        )
    
    logger.info(f"CICD credentials found for {cicd_type}")
    logger.info(f"Credentials detail: provider={cicd_creds.provider}, token={cicd_creds.token[:20] if cicd_creds.token else 'NONE'}..., org={cicd_creds.organization}, project={cicd_creds.project}")
    
    # Crear registro de despliegue
    history = DeploymentHistoryModel(
        client_id=client_model.id,
        cloud_provider="multi-cloud",
        region="",
        environment=request.environment,
        status="running",
        deployment_data={
            "type": "code_deployment",
            "cicd_provider": cicd_type,
            "repo_url": request.repo_url,
            "branch": request.branch,
            "resource_id": request.resource_id,
            "resource_type": request.resource_type
        }
    )
    db.add(history)
    await db.commit()
    
    try:
        logger.info(f"Starting code deployment for resource {request.resource_id}" 
                   f" via {cicd_type} in {request.environment}")
        
        # Get Azure credentials from environment (for GitHub Actions)
        azure_credentials = None
        if cicd_type.lower() == "github-actions":
            azure_credentials = {
                "AZURE_CLIENT_ID": os.getenv("AZURE_CLIENT_ID", ""),
                "AZURE_CLIENT_SECRET": os.getenv("AZURE_CLIENT_SECRET", ""),
                "AZURE_TENANT_ID": os.getenv("AZURE_TENANT_ID", ""),
                "AZURE_SUBSCRIPTION_ID": os.getenv("AZURE_SUBSCRIPTION_ID", "")
            }
            logger.info(f"[Deploy] Azure credentials loaded: client_id={azure_credentials['AZURE_CLIENT_ID'][:8] if azure_credentials['AZURE_CLIENT_ID'] else 'NONE'}...")
        
        # Extraer información del cliente para la generación de pipeline con IA
        client_info = {
            "id": client_model.id,
            "name": client_model.name,
            "use_ai": request.use_ai_pipeline,
            "resource_type": request.resource_type,
            "resource_name": _extract_resource_name(request.resource_id),
            "resource_group": _extract_resource_group(request.resource_id),
            "application_type": request.application_type,
            "cicd_provider": cicd_type
        }
        
        # Usar el dispatcher para manejar el despliegue según el tipo de CI/CD
        logger.info(f"Calling CICDDispatcher with:")
        logger.info(f"  - cicd_type: {cicd_type}")
        logger.info(f"  - repo_url: {request.repo_url}")
        logger.info(f"  - branch: {request.branch}")
        logger.info(f"  - resource_id: {request.resource_id}")
        logger.info(f"  - environment: {request.environment}")
        logger.info(f"  - use_ai_pipeline: {request.use_ai_pipeline}")
        
        success, message = await CICDDispatcher.dispatch(
            cicd_type=cicd_type,
            token=cicd_creds.token,
            repo_url=request.repo_url,
            branch=request.branch,
            resource_id=request.resource_id,
            environment=request.environment,
            organization=cicd_creds.organization,
            project=cicd_creds.project,
            azure_credentials=azure_credentials,
            client_info=client_info
        )
        
        logger.info(f"CICDDispatcher returned: success={success}, message={message}")
        
        if success:
            history.status = "completed"
            history.completed_at = datetime.utcnow()
            await db.commit()
            
            logger.info(f"Deployment {history.id} completed successfully via {cicd_type}")
            return {
                "status": "success",
                "message": f"Despliegue iniciado exitosamente vía {cicd_type}",
                "deployment_id": str(history.id),
                "cicd_provider": cicd_type,
                "details": message
            }
        else:
            logger.error(f"Deployment failed: {message}")
            history.status = "failed"
            history.error_message = f"Dispatcher error: {message}"
            history.completed_at = datetime.utcnow()
            await db.commit()
            raise HTTPException(status_code=500, detail=message)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en despliegue de código: {e}", exc_info=True)
        history.status = "failed"
        history.error_message = str(e)
        history.completed_at = datetime.utcnow()
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/history/{client_id}")
async def get_deployment_history(client_id: str, db: AsyncSession = Depends(get_db)):
    """
    Obtiene el historial de despliegues de un cliente
    """
    result = await db.execute(
        select(DeploymentHistoryModel)
        .where(DeploymentHistoryModel.client_id == client_id)
        .order_by(DeploymentHistoryModel.created_at.desc())
    )
    history = result.scalars().all()
    return history


class AppServiceRequest(BaseModel):
    """Request para crear un App Service"""
    resource_group: str = "rg_iop"
    app_service_name: str
    app_service_plan_name: Optional[str] = None
    location: str = "eastus"
    runtime: str = "PYTHON|3.11"


@router.post("/app-service")
async def create_app_service(request: AppServiceRequest, db: AsyncSession = Depends(get_db)):
    """
    Crea un App Service directamente en Azure (sin usar ARM Template)
    """
    from app.connectors.cloud.azure_connector import get_azure_connector
    
    try:
        azure_connector = get_azure_connector()
        
        result = await azure_connector.create_app_service(
            resource_group=request.resource_group,
            app_service_name=request.app_service_name,
            app_service_plan_name=request.app_service_plan_name,
            location=request.location,
            runtime=request.runtime
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error creating App Service: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


def _extract_resource_name(resource_id: str) -> str:
    """
    Extrae el nombre del recurso desde un Azure Resource ID
    
    Ejemplo: /subscriptions/xxx/resourceGroups/rg-app/providers/Microsoft.Web/sites/myapp
    Retorna: myapp
    """
    if not resource_id:
        return "app"
    
    # Tomar el último segmento después de /
    parts = resource_id.rstrip('/').split('/')
    if parts:
        return parts[-1]
    return "app"


def _extract_resource_group(resource_id: str) -> str:
    """
    Extrae el nombre del grupo de recursos desde un Azure Resource ID
    
    Ejemplo: /subscriptions/xxx/resourceGroups/rg-app/providers/Microsoft.Web/sites/myapp
    Retorna: rg-app
    """
    if not resource_id:
        return "rg-default"
    
    # Buscar resourceGroups en el path
    parts = resource_id.split('/')
    try:
        rg_index = parts.index('resourceGroups')
        if rg_index + 1 < len(parts):
            return parts[rg_index + 1]
    except ValueError:
        pass
    
    return "rg-default"
