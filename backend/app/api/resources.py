from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.schemas import CloudProvider, Client
from app.models.database import ClientModel
from app.orchestrators.iaops_orchestrator import orchestrator
from app.core.database import get_db
from app.core.logging import logger

router = APIRouter()

@router.get("/deployable/{client_id}")
async def list_deployable_resources(
    client_id: str,
    cloud_provider: str = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Lista TODOS los recursos donde se puede desplegar código:
    - App Services
    - Virtual Machines
    - Azure Functions
    - Container Instances
    - Kubernetes clusters
    """
    # Verificar cliente
    result = await db.execute(select(ClientModel).where(ClientModel.id == client_id))
    client_model = result.scalar_one_or_none()
    
    if not client_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {client_id} no encontrado"
        )
    
    client = Client(
        id=client_model.id,
        name=client_model.name,
        description=client_model.description,
        tech_profile=client_model.tech_profile,
        is_active=client_model.is_active,
        created_at=client_model.created_at,
        updated_at=client_model.updated_at
    )
    
    deployable_types = [
        "Microsoft.Web/sites",  # App Services
        "Microsoft.Compute/virtualMachines",  # VMs
        "Microsoft.Web/sites/functions",  # Azure Functions
        "Microsoft.ContainerInstance/containerGroups",  # Container Instances
        "Microsoft.ContainerService/managedClusters"  # AKS
    ]
    
    all_resources = []
    
    try:
        # Si se especifica cloud provider, solo buscar en ese
        if cloud_provider:
            providers = [cloud_provider]
        else:
            # `tech_profile` es un Pydantic model; acceder a la lista `clouds`
            try:
                providers = client.tech_profile.clouds or ['azure']
            except Exception:
                logger.warning("tech_profile no tiene atributo 'clouds', usando 'azure' por defecto")
                providers = ['azure']
        
        for provider in providers:
            # Normalizar provider (acepta enums o strings)
            if hasattr(provider, 'value'):
                provider_str = str(provider.value)
            else:
                provider_str = str(provider)
            provider_str = provider_str.lower()

            try:
                provider_enum = CloudProvider(provider_str)
            except Exception:
                logger.warning(f"Proveedor desconocido en tech_profile: {provider}")
                continue

            for resource_type in deployable_types:
                try:
                    # Mapear tipos de recursos a los nombres entendidos por los conectores
                    mapping = {
                        "Microsoft.Web/sites": "app_services",
                        "Microsoft.Compute/virtualMachines": "vms",
                        "Microsoft.Web/sites/functions": "functions",
                        "Microsoft.ContainerInstance/containerGroups": "containers",
                        "Microsoft.ContainerService/managedClusters": "aks"
                    }

                    connector_resource_type = mapping.get(resource_type, resource_type)

                    resources = await orchestrator.list_client_resources(
                        client=client,
                        cloud_provider=provider_enum,
                        resource_type=connector_resource_type
                    )

                    # Enriquecer con metadata
                    for res in resources:
                        res['cloud_provider'] = provider_str
                        res['deployable'] = True
                        res['resource_type_display'] = _get_display_name(resource_type)

                    all_resources.extend(resources)
                except Exception as e:
                    logger.warning(f"Error fetching {resource_type} from {provider_str}: {e}")
                    continue
        
        return {
            'client_id': client_id,
            'count': len(all_resources),
            'resources': all_resources
        }
        
    except Exception as e:
        logger.error(f"Error listando recursos deployables: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

def _get_display_name(resource_type: str) -> str:
    """Convierte el tipo de recurso técnico a nombre legible"""
    mapping = {
        "Microsoft.Web/sites": "App Service",
        "Microsoft.Compute/virtualMachines": "Virtual Machine",
        "Microsoft.Web/sites/functions": "Azure Function",
        "Microsoft.ContainerInstance/containerGroups": "Container Instance",
        "Microsoft.ContainerService/managedClusters": "Kubernetes Cluster"
    }
    return mapping.get(resource_type, resource_type)

@router.get("/{client_id}/{cloud_provider}/{resource_type}")
async def list_resources(
    client_id: str,
    cloud_provider: CloudProvider,
    resource_type: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Lista recursos de un cliente en un cloud provider específico desde PostgreSQL
    """
    # Verificar cliente en DB
    result = await db.execute(select(ClientModel).where(ClientModel.id == client_id))
    client_model = result.scalar_one_or_none()
    
    if not client_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {client_id} no encontrado"
        )
    
    # Convertir a esquema Pydantic
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
        resources = await orchestrator.list_client_resources(
            client=client,
            cloud_provider=cloud_provider,
            resource_type=resource_type
        )
        
        return {
            'client_id': client_id,
            'cloud_provider': cloud_provider,
            'resource_type': resource_type,
            'count': len(resources),
            'resources': resources
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error listando recursos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
