from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Dict, Any
from app.models.database import ClientModel, ArchitectureGenerationModel, DeploymentHistoryModel
from app.core.database import get_db
from app.core.logging import logger

router = APIRouter()

@router.get("/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """
    Obtiene estadísticas consolidadas para el dashboard
    """
    logger.info("Calculando estadísticas del dashboard...")
    try:
        # Contar Clientes
        result_clients = await db.execute(select(func.count(ClientModel.id)))
        total_clients = result_clients.scalar() or 0
        logger.info(f"Total clientes: {total_clients}")
        
        # Contar Arquitecturas (solo de clientes existentes)
        result_arch = await db.execute(
            select(func.count(ArchitectureGenerationModel.id))
            .join(ClientModel, ArchitectureGenerationModel.client_id == ClientModel.id)
        )
        total_architectures = result_arch.scalar() or 0
        logger.info(f"Total arquitecturas: {total_architectures}")
        
        # Contar Despliegues Exitosos (solo de clientes existentes)
        result_deploy = await db.execute(
            select(func.count(DeploymentHistoryModel.id))
            .join(ClientModel, DeploymentHistoryModel.client_id == ClientModel.id)
            .where(DeploymentHistoryModel.status == "completed")
        )
        total_deployments = result_deploy.scalar() or 0
        logger.info(f"Total despliegues: {total_deployments}")
        
        # Obtener Actividad Reciente
        recent_activity = []
        
        # Últimos despliegues
        result_recent_deploys = await db.execute(
            select(DeploymentHistoryModel, ClientModel.name)
            .join(ClientModel, DeploymentHistoryModel.client_id == ClientModel.id)
            .order_by(DeploymentHistoryModel.created_at.desc())
            .limit(3)
        )
        for deploy, client_name in result_recent_deploys:
             recent_activity.append({
                "action": f"Despliegue {deploy.status}",
                "client": client_name,
                "time": deploy.created_at.isoformat(),
                "type": "deployment"
            })
            
        # Últimas arquitecturas
        result_recent_arch = await db.execute(
            select(ArchitectureGenerationModel, ClientModel.name)
            .join(ClientModel, ArchitectureGenerationModel.client_id == ClientModel.id)
            .order_by(ArchitectureGenerationModel.created_at.desc())
            .limit(3)
        )
        for arch, client_name in result_recent_arch:
            recent_activity.append({
                "action": "Arquitectura generada",
                "client": client_name,
                "time": arch.created_at.isoformat(),
                "type": "architecture"
            })
            
        # Ordenar por tiempo desc
        recent_activity.sort(key=lambda x: x["time"], reverse=True)
        
        # Cloud providers en uso (solo de clientes existentes)
        result_clouds = await db.execute(
            select(DeploymentHistoryModel.cloud_provider, func.count(DeploymentHistoryModel.id))
            .join(ClientModel, DeploymentHistoryModel.client_id == ClientModel.id)
            .group_by(DeploymentHistoryModel.cloud_provider)
        )
        # Convertir enum a string para evitar líos de serialización
        cloud_usage = {str(row[0].value if hasattr(row[0], 'value') else row[0]): row[1] for row in result_clouds}

        return {
            "total_clients": total_clients,
            "total_architectures": total_architectures,
            "total_deployments": total_deployments,
            "recent_activity": recent_activity[:5],
            "cloud_usage": cloud_usage
        }
        
    except Exception as e:
        logger.error(f"Error calculando stats de dashboard: {e}")
        logger.exception(e)
        return {
            "total_clients": 0,
            "total_architectures": 0,
            "total_deployments": 0,
            "recent_activity": [],
            "cloud_usage": {}
        }
