from fastapi import APIRouter, HTTPException, status, Depends
from typing import Dict, Any, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.database import ClientModel, GrafanaDashboardModel, GrafanaConfigModel
from app.services.grafana_service import GrafanaService
from app.core.database import get_db
from app.core.logging import logger
import json

router = APIRouter()

# Pydantic models
class GrafanaConfigRequest(BaseModel):
    """Request para configurar Grafana"""
    client_id: str
    azure_tenant_id: str
    azure_subscription_id: str
    azure_client_id: str
    azure_client_secret: str

class DashboardCreateRequest(BaseModel):
    """Request para crear dashboard"""
    client_id: str
    resource_id: str
    resource_type: str
    resource_name: str

@router.post("/configure-grafana")
async def configure_grafana(request: GrafanaConfigRequest, db: AsyncSession = Depends(get_db)):
    """
    Configura Grafana con datasource de Azure Monitor para un cliente
    """
    # Verificar cliente
    result = await db.execute(select(ClientModel).where(ClientModel.id == request.client_id))
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {request.client_id} no encontrado"
        )
    
    try:
        # Crear datasource en Grafana
        grafana = GrafanaService()
        datasource_name = f"azure-monitor-{request.client_id}"
        
        datasource_result = await grafana.create_azure_datasource(
            name=datasource_name,
            tenant_id=request.azure_tenant_id,
            subscription_id=request.azure_subscription_id,
            client_id=request.azure_client_id,
            client_secret=request.azure_client_secret
        )
        
        # Guardar configuración en DB
        # Verificar si ya existe
        existing = await db.execute(
            select(GrafanaConfigModel).where(GrafanaConfigModel.client_id == request.client_id)
        )
        config = existing.scalar_one_or_none()
        
        if config:
            # Actualizar
            config.azure_tenant_id = request.azure_tenant_id
            config.azure_subscription_id = request.azure_subscription_id
            config.azure_client_id = request.azure_client_id
            config.azure_client_secret = request.azure_client_secret
            config.datasource_name = datasource_name
            config.datasource_id = str(datasource_result.get('id') or datasource_result.get('datasource', {}).get('id'))
        else:
            # Crear nuevo
            config = GrafanaConfigModel(
                client_id=request.client_id,
                azure_tenant_id=request.azure_tenant_id,
                azure_subscription_id=request.azure_subscription_id,
                azure_client_id=request.azure_client_id,
                azure_client_secret=request.azure_client_secret,
                datasource_name=datasource_name,
                datasource_id=str(datasource_result.get('id') or datasource_result.get('datasource', {}).get('id'))
            )
            db.add(config)
        
        await db.commit()
        
        return {
            "status": "success",
            "message": "Grafana configurado correctamente",
            "datasource_name": datasource_name
        }
        
    except Exception as e:
        logger.error(f"Error configurando Grafana: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/create-dashboard")
async def create_dashboard(request: DashboardCreateRequest, db: AsyncSession = Depends(get_db)):
    """
    Crea un dashboard de Grafana para un recurso específico
    """
    # Verificar cliente
    result = await db.execute(select(ClientModel).where(ClientModel.id == request.client_id))
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {request.client_id} no encontrado"
        )
    
    # Verificar configuración de Grafana
    config_result = await db.execute(
        select(GrafanaConfigModel).where(GrafanaConfigModel.client_id == request.client_id)
    )
    grafana_config = config_result.scalar_one_or_none()
    
    # Auto-configuración si no existe
    if not grafana_config:
        from app.models.database import CloudCredentialsModel
        cloud_creds_result = await db.execute(
            select(CloudCredentialsModel).where(
                CloudCredentialsModel.client_id == request.client_id,
                CloudCredentialsModel.provider == 'azure'
            )
        )
        cloud_creds = cloud_creds_result.scalar_one_or_none()
        
        if cloud_creds and cloud_creds.credentials:
            try:
                logger.info(f"Auto-configurando Grafana para cliente {request.client_id} usando credenciales existentes")
                grafana = GrafanaService()
                datasource_name = f"azure-monitor-{request.client_id}"
                creds = cloud_creds.credentials
                
                # Crear datasource
                datasource_result = await grafana.create_azure_datasource(
                    name=datasource_name,
                    tenant_id=creds.get('tenant_id'),
                    subscription_id=creds.get('subscription_id'),
                    client_id=creds.get('client_id'),
                    client_secret=creds.get('client_secret')
                )
                
                # Guardar configuración
                grafana_config = GrafanaConfigModel(
                    client_id=request.client_id,
                    azure_tenant_id=creds.get('tenant_id'),
                    azure_subscription_id=creds.get('subscription_id'),
                    azure_client_id=creds.get('client_id'),
                    azure_client_secret=creds.get('client_secret'),
                    datasource_name=datasource_name,
                    datasource_id=str(datasource_result.get('id') or datasource_result.get('datasource', {}).get('id'))
                )
                db.add(grafana_config)
                await db.commit()
                logger.info("Auto-configuración completada")
                
            except Exception as e:
                logger.error(f"Error en auto-configuración de DB: {e}")
                # Fallthrough al siguiente intento

    # Auto-configuración con AWS CloudWatch si el recurso es de AWS
    if not grafana_config:
        from app.core.config import settings
        is_aws_resource = request.resource_type in [
            "amplify_app", "ec2_instance", "s3_bucket", "lambda_function",
            "rds_instance", "ecs_cluster", "eks_cluster"
        ]
        if is_aws_resource and settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            try:
                logger.info(f"Auto-configurando Grafana CloudWatch para cliente {request.client_id}")
                grafana = GrafanaService()
                datasource_name = f"cloudwatch-{request.client_id[:8]}"
                cw_result = await grafana.create_cloudwatch_datasource(
                    name=datasource_name,
                    access_key_id=settings.AWS_ACCESS_KEY_ID,
                    secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    session_token=settings.AWS_SESSION_TOKEN or None,
                    region=settings.AWS_DEFAULT_REGION or "us-east-1"
                )
                grafana_config = GrafanaConfigModel(
                    client_id=request.client_id,
                    azure_tenant_id="aws",
                    azure_subscription_id=settings.AWS_DEFAULT_REGION or "us-east-1",
                    azure_client_id=settings.AWS_ACCESS_KEY_ID,
                    azure_client_secret=settings.AWS_SECRET_ACCESS_KEY,
                    datasource_name=datasource_name,
                    datasource_id=str(cw_result.get('id') or cw_result.get('datasource', {}).get('id', ''))
                )
                db.add(grafana_config)
                await db.commit()
                logger.info("Auto-configuración CloudWatch completada")
            except Exception as e:
                logger.error(f"Error en auto-configuración CloudWatch: {e}")

    # Fallback: Intentar con variables de entorno Azure (config.py / .env)
    if not grafana_config:
        from app.core.config import settings

        if (settings.AZURE_TENANT_ID and settings.AZURE_SUBSCRIPTION_ID and
            settings.AZURE_CLIENT_ID and settings.AZURE_CLIENT_SECRET):
            
            try:
                logger.info(f"Auto-configurando Grafana para cliente {request.client_id} usando variables de entorno")
                grafana = GrafanaService()
                datasource_name = f"azure-monitor-{request.client_id}"
                
                # Crear datasource
                datasource_result = await grafana.create_azure_datasource(
                    name=datasource_name,
                    tenant_id=settings.AZURE_TENANT_ID,
                    subscription_id=settings.AZURE_SUBSCRIPTION_ID,
                    client_id=settings.AZURE_CLIENT_ID,
                    client_secret=settings.AZURE_CLIENT_SECRET
                )
                
                # Guardar configuración
                grafana_config = GrafanaConfigModel(
                    client_id=request.client_id,
                    azure_tenant_id=settings.AZURE_TENANT_ID,
                    azure_subscription_id=settings.AZURE_SUBSCRIPTION_ID,
                    azure_client_id=settings.AZURE_CLIENT_ID,
                    azure_client_secret=settings.AZURE_CLIENT_SECRET,
                    datasource_name=datasource_name,
                    datasource_id=str(datasource_result.get('id') or datasource_result.get('datasource', {}).get('id'))
                )
                db.add(grafana_config)
                await db.commit()
                logger.info("Auto-configuración por entorno completada")
                
            except Exception as e:
                logger.error(f"Error en auto-configuración por entorno: {e}")
                # Fallthrough al error 400

    if not grafana_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Grafana no está configurado. No se encontraron credenciales en DB ni en variables de entorno (.env). Configure en Settings."
        )
    
    try:
        # Crear dashboard JSON
        dashboard_json = _create_dashboard_json(
            resource_name=request.resource_name,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            datasource_name=grafana_config.datasource_name,
            subscription_id=grafana_config.azure_subscription_id
        )
        
        # Crear dashboard en Grafana
        grafana = GrafanaService()
        result = await grafana.create_dashboard(dashboard_json)
        
        dashboard_uid = result.get('uid')
        dashboard_url = grafana.get_dashboard_url(dashboard_uid)
        
        # Guardar o actualizar en DB
        existing_result = await db.execute(
            select(GrafanaDashboardModel).where(GrafanaDashboardModel.resource_id == request.resource_id)
        )
        existing_dashboard = existing_result.scalar_one_or_none()
        
        if existing_dashboard:
            existing_dashboard.dashboard_uid = dashboard_uid
            existing_dashboard.dashboard_url = dashboard_url
            existing_dashboard.datasource_name = grafana_config.datasource_name
        else:
            dashboard = GrafanaDashboardModel(
                client_id=request.client_id,
                resource_id=request.resource_id,
                resource_type=request.resource_type,
                resource_name=request.resource_name,
                dashboard_uid=dashboard_uid,
                dashboard_url=dashboard_url,
                datasource_name=grafana_config.datasource_name
            )
            db.add(dashboard)
            
        await db.commit()
        
        return {
            "status": "success",
            "message": f"Dashboard creado para {request.resource_name}",
            "dashboard_uid": dashboard_uid,
            "dashboard_url": dashboard_url
        }
        
    except Exception as e:
        logger.error(f"Error creando dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/dashboard-url/{resource_id:path}")
async def get_dashboard_url(resource_id: str, db: AsyncSession = Depends(get_db)):
    """
    Obtiene la URL del dashboard para un recurso
    """
    result = await db.execute(
        select(GrafanaDashboardModel).where(GrafanaDashboardModel.resource_id == resource_id)
    )
    dashboard = result.scalar_one_or_none()
    
    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dashboard no encontrado para este recurso"
        )
    
    # Generar URL dinámica usando la configuración actual
    grafana = GrafanaService()
    current_url = grafana.get_dashboard_url(dashboard.dashboard_uid)
    
    return {
        "dashboard_url": current_url,
        "dashboard_uid": dashboard.dashboard_uid
    }

def _create_dashboard_json(
    resource_name: str,
    resource_type: str,
    resource_id: str,
    datasource_name: str,
    subscription_id: str
) -> Dict[str, Any]:
    """
    Crea el JSON del dashboard basado en el tipo de recurso
    """
    # UID único basado en resource_id
    import hashlib
    dashboard_uid = hashlib.md5(resource_id.encode()).hexdigest()[:16]
    
    # Dashboard base
    dashboard = {
        "uid": dashboard_uid,
        "title": f"{resource_name} - Monitoring",
        "tags": [resource_type, "azure", "auto-generated"],
        "timezone": "browser",
        "schemaVersion": 16,
        "version": 0,
        "refresh": "30s",
        "panels": []
    }
    
    # Agregar paneles según tipo de recurso
    if resource_type in ["app_service", "function_app"]:
        dashboard["panels"] = _get_app_service_panels(resource_id, datasource_name, subscription_id)
    elif resource_type == "virtual_machine":
        dashboard["panels"] = _get_vm_panels(resource_id, datasource_name, subscription_id)
    elif resource_type in ["container_instance", "kubernetes_cluster"]:
        dashboard["panels"] = _get_container_panels(resource_id, datasource_name, subscription_id)
    elif resource_type == "amplify_app":
        dashboard["panels"] = _get_amplify_panels(resource_id, datasource_name, subscription_id)
    elif resource_type == "ec2_instance":
        dashboard["panels"] = _get_ec2_panels(resource_id, datasource_name, subscription_id)
    else:
        # Paneles genéricos
        dashboard["panels"] = _get_generic_panels(resource_id, datasource_name, subscription_id)
    
    return dashboard

def _get_app_service_panels(resource_id: str, datasource: str, subscription_id: str) -> list:
    """Paneles para App Services y Functions"""
    return [
        {
            "id": 1,
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
            "type": "graph",
            "title": "CPU Percentage",
            "targets": [{
                "datasource": datasource,
                "azureMonitor": {
                    "resourceGroup": resource_id.split("/")[4],
                    "metricDefinition": "Microsoft.Web/sites",
                    "resourceName": resource_id.split("/")[-1],
                    "metricName": "CpuPercentage",
                    "aggregation": "Average"
                }
            }]
        },
        {
            "id": 2,
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
            "type": "graph",
            "title": "Memory Percentage",
            "targets": [{
                "datasource": datasource,
                "azureMonitor": {
                    "resourceGroup": resource_id.split("/")[4],
                    "metricDefinition": "Microsoft.Web/sites",
                    "resourceName": resource_id.split("/")[-1],
                    "metricName": "MemoryPercentage",
                    "aggregation": "Average"
                }
            }]
        },
        {
            "id": 3,
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
            "type": "graph",
            "title": "HTTP Requests",
            "targets": [{
                "datasource": datasource,
                "azureMonitor": {
                    "resourceGroup": resource_id.split("/")[4],
                    "metricDefinition": "Microsoft.Web/sites",
                    "resourceName": resource_id.split("/")[-1],
                    "metricName": "Requests",
                    "aggregation": "Total"
                }
            }]
        },
        {
            "id": 4,
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
            "type": "graph",
            "title": "Response Time",
            "targets": [{
                "datasource": datasource,
                "azureMonitor": {
                    "resourceGroup": resource_id.split("/")[4],
                    "metricDefinition": "Microsoft.Web/sites",
                    "resourceName": resource_id.split("/")[-1],
                    "metricName": "AverageResponseTime",
                    "aggregation": "Average"
                }
            }]
        }
    ]

def _get_vm_panels(resource_id: str, datasource: str, subscription_id: str) -> list:
    """Paneles para VMs"""
    return [
        {
            "id": 1,
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
            "type": "graph",
            "title": "CPU Usage",
            "targets": [{
                "datasource": datasource,
                "azureMonitor": {
                    "resourceGroup": resource_id.split("/")[4],
                    "metricDefinition": "Microsoft.Compute/virtualMachines",
                    "resourceName": resource_id.split("/")[-1],
                    "metricName": "Percentage CPU",
                    "aggregation": "Average"
                }
            }]
        },
        {
            "id": 2,
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
            "type": "graph",
            "title": "Network In/Out",
            "targets": [{
                "datasource": datasource,
                "azureMonitor": {
                    "resourceGroup": resource_id.split("/")[4],
                    "metricDefinition": "Microsoft.Compute/virtualMachines",
                    "resourceName": resource_id.split("/")[-1],
                    "metricName": "Network In Total",
                    "aggregation": "Total"
                }
            }]
        }
    ]

def _get_container_panels(resource_id: str, datasource: str, subscription_id: str) -> list:
    """Paneles para Containers"""
    return _get_generic_panels(resource_id, datasource, subscription_id)

def _get_amplify_panels(resource_id: str, datasource: str, region: str) -> list:
    """Paneles de CloudWatch para AWS Amplify"""
    def cw_target(metric: str, stat: str = "Average") -> dict:
        return {
            "datasource": datasource,
            "dimensions": {"App": resource_id},
            "expression": "",
            "id": "",
            "matchExact": True,
            "metricName": metric,
            "namespace": "AWS/AmplifyHosting",
            "period": "",
            "refId": "A",
            "region": "default",
            "statistics": [stat]
        }
    return [
        {
            "id": 1, "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
            "type": "timeseries", "title": "Requests",
            "targets": [cw_target("Requests", "Sum")]
        },
        {
            "id": 2, "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
            "type": "timeseries", "title": "4xx Errors",
            "targets": [cw_target("4xxErrors", "Sum")]
        },
        {
            "id": 3, "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
            "type": "timeseries", "title": "5xx Errors",
            "targets": [cw_target("5xxErrors", "Sum")]
        },
        {
            "id": 4, "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
            "type": "timeseries", "title": "Bytes Downloaded",
            "targets": [cw_target("BytesDownloaded", "Sum")]
        }
    ]


def _get_ec2_panels(resource_id: str, datasource: str, region: str) -> list:
    """Paneles de CloudWatch para EC2"""
    def cw_target(metric: str, stat: str = "Average") -> dict:
        return {
            "datasource": datasource,
            "dimensions": {"InstanceId": resource_id},
            "metricName": metric,
            "namespace": "AWS/EC2",
            "refId": "A",
            "region": "default",
            "statistics": [stat]
        }
    return [
        {
            "id": 1, "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
            "type": "timeseries", "title": "CPU Utilization",
            "targets": [cw_target("CPUUtilization")]
        },
        {
            "id": 2, "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
            "type": "timeseries", "title": "Network In/Out",
            "targets": [cw_target("NetworkIn", "Sum"), {**cw_target("NetworkOut", "Sum"), "refId": "B"}]
        }
    ]


def _get_generic_panels(resource_id: str, datasource: str, subscription_id: str) -> list:
    """Paneles genéricos"""
    return [
        {
            "id": 1,
            "gridPos": {"h": 8, "w": 24, "x": 0, "y": 0},
            "type": "text",
            "title": "Resource Information",
            "options": {
                "content": f"**Resource ID:** `{resource_id}`\n\nDashboard created automatically. Configure specific metrics in Grafana.",
                "mode": "markdown"
            }
        }
    ]
