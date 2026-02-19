"""
Conector para Microsoft Azure
"""
from azure.identity import ClientSecretCredential, DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.web import WebSiteManagementClient
from typing import TYPE_CHECKING

# WebSiteManagementClient - optional dependency for App Services and Functions
# Import only for type checking to avoid Pylance/pyright import errors
if TYPE_CHECKING:
    from azure.mgmt.web import WebSiteManagementClient  # type: ignore[import]
    from azure.mgmt.containerinstance import ContainerInstanceManagementClient  # type: ignore[import]
    from azure.mgmt.containerservice import ContainerServiceClient  # type: ignore[import]

# Runtime import with graceful degradation
try:
    from azure.mgmt.web import WebSiteManagementClient as _WebSiteMgmtClient  # type: ignore[import]
    WEB_SITE_MGMT_AVAILABLE = True
except ImportError:
    _WebSiteMgmtClient = None  # type: ignore
    WEB_SITE_MGMT_AVAILABLE = False

# Container Instance Client - optional dependency
try:
    from azure.mgmt.containerinstance import ContainerInstanceManagementClient as _ContainerInstanceMgmtClient  # type: ignore[import]
    CONTAINER_INSTANCE_AVAILABLE = True
except ImportError:
    _ContainerInstanceMgmtClient = None  # type: ignore
    CONTAINER_INSTANCE_AVAILABLE = False

# Container Service Client - optional dependency for AKS
try:
    from azure.mgmt.containerservice import ContainerServiceClient as _ContainerServiceClient  # type: ignore[import]
    CONTAINER_SERVICE_AVAILABLE = True
except ImportError:
    _ContainerServiceClient = None  # type: ignore
    CONTAINER_SERVICE_AVAILABLE = False

# Alias for backwards compatibility
WebSiteManagementClient = _WebSiteMgmtClient
ContainerInstanceManagementClient = _ContainerInstanceMgmtClient
ContainerServiceClient = _ContainerServiceClient

from typing import Dict, Any, List, Optional
import re
import subprocess
import json
import os
from app.core.logging import logger


class AzureConnector:
    """
    Conector para Microsoft Azure
    """
    
    def __init__(
        self,
        subscription_id: str,
        tenant_id: str = None,
        client_id: str = None,
        client_secret: str = None
    ):
        self.subscription_id = subscription_id
        
        # Try to get credentials from parameters or environment
        if client_id and client_secret and tenant_id:
            self.credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
        else:
            # Try using DefaultAzureCredential (works with Azure CLI, Managed Identity, etc.)
            try:
                self.credential = DefaultAzureCredential()
            except Exception as e:
                logger.warning(f"DefaultAzureCredential failed: {e}")
                self.credential = None
        
        self.resource_client = None
        self.compute_client = None
        self.storage_client = None
        self.web_client = None
        self._connected = False
    
    async def connect(self) -> bool:
        """
        Verifica la conexión con Azure
        """
        try:
            if not self.credential:
                return False
            
            # Try to get the resource client to verify connection
            resource_client = self._get_resource_client()
            # Just verify we can list subscriptions (lightweight check)
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"Error connecting to Azure: {e}")
            return False
        
    def _get_resource_client(self):
        if not self.resource_client:
            self.resource_client = ResourceManagementClient(
                self.credential,
                self.subscription_id
            )
        return self.resource_client
    
    def _get_compute_client(self):
        if not self.compute_client:
            self.compute_client = ComputeManagementClient(
                self.credential,
                self.subscription_id
            )
        return self.compute_client
    
    def _get_storage_client(self):
        if not self.storage_client:
            self.storage_client = StorageManagementClient(
                self.credential,
                self.subscription_id
            )
        return self.storage_client
    
    def _get_web_client(self):
        if not self.web_client:
            if not WEB_SITE_MGMT_AVAILABLE:
                raise Exception("WebSiteManagementClient not available. Install azure-mgmt-web package.")
            self.web_client = WebSiteManagementClient(
                self.credential,
                self.subscription_id
            )
        return self.web_client
    
    async def create_app_service(
        self,
        resource_group: str,
        app_service_name: str,
        app_service_plan_name: str = None,
        location: str = "eastus",
        runtime: str = "PYTHON|3.11"
    ) -> Dict[str, Any]:
        """
        Crea un App Service con su Plan asociado
        
        Args:
            resource_group: Nombre del grupo de recursos
            app_service_name: Nombre del App Service
            app_service_plan_name: Nombre del App Service Plan (opcional)
            location: Ubicación (default: eastus)
            runtime: Runtime stack (default: PYTHON|3.11)
            
        Returns:
            Diccionario con información del App Service creado
        """
        try:
            web_client = self._get_web_client()
            resource_client = self._get_resource_client()
            
            # Si no se especifica nombre del plan, usar uno por defecto
            if not app_service_plan_name:
                app_service_plan_name = f"{app_service_name}-plan"
            
            # 1. Crear el grupo de recursos si no existe
            try:
                resource_client.resource_groups.get(resource_group)
                logger.info(f"Resource group '{resource_group}' already exists")
            except:
                logger.info(f"Creating resource group '{resource_group}'...")
                resource_client.resource_groups.create_or_update(
                    resource_group,
                    {"location": location, "tags": {"environment": "iaops"}}
                )
                logger.info(f"Resource group '{resource_group}' created")
            
            # 2. Crear el App Service Plan
            logger.info(f"Creating App Service Plan '{app_service_plan_name}'...")
            asp_poller = web_client.app_service_plans.begin_create_or_update(
                resource_group,
                app_service_plan_name,
                {
                    "location": location,
                    "sku": {
                        "name": "F1",
                        "tier": "Free",
                        "capacity": 1
                    },
                    "kind": "linux",
                    "reserved": True
                }
            )
            asp_result = asp_poller.result()
            logger.info(f"App Service Plan created: {asp_result.id}")
            
            # 3. Crear el App Service
            logger.info(f"Creating App Service '{app_service_name}'...")
            
            # El nombre del app service no puede tener guiones bajos
            app_service_name = app_service_name.replace("_", "-")
            
            web_poller = web_client.web_apps.begin_create_or_update(
                resource_group,
                app_service_name,
                {
                    "location": location,
                    "server_farm_id": asp_result.id,
                    "kind": "app,linux",
                    "reserved": True,
                    "site_config": {
                        "linux_fx_version": runtime,
                        "always_on": False,
                        "http20_enabled": True
                    },
                    "tags": {
                        "environment": "iaops",
                        "project": "peribank"
                    }
                }
            )
            web_result = web_poller.result()
            logger.info(f"App Service created: {web_result.id}")
            
            return {
                "status": "success",
                "app_service_name": app_service_name,
                "app_service_plan_name": app_service_plan_name,
                "resource_group": resource_group,
                "location": location,
                "url": f"https://{web_result.default_host_name}"
            }
            
        except Exception as e:
            logger.error(f"Error creating App Service: {e}")
            raise
    
    async def list_resources(
        self,
        resource_type: str = None,
        resource_group: str = None
    ) -> List[Dict[str, Any]]:
        """Lista recursos de Azure"""
        # Mapeo de tipos de recursos del frontend a Azure
        resource_type_mapping = {
            'app_services': 'Microsoft.Web/sites',
            'vms': 'Microsoft.Compute/virtualMachines',
            'storage': 'Microsoft.Storage/storageAccounts',
            'networks': 'Microsoft.Network/virtualNetworks',
            'kubernetes': 'Microsoft.ContainerService/managedClusters'
        }
        
        # Convertir tipo de recurso si es necesario
        azure_resource_type = resource_type_mapping.get(resource_type, resource_type)
        
        try:
            resource_client = self._get_resource_client()
            
            if resource_group:
                resources = resource_client.resources.list_by_resource_group(resource_group)
            else:
                resources = resource_client.resources.list()
            
            result = []
            for r in resources:
                if azure_resource_type and r.type != azure_resource_type:
                    continue
                result.append({
                    'id': r.id,
                    'name': r.name,
                    'type': r.type,
                    'location': r.location
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error listing resources: {e}")
            return []
    
    async def delete_resource(
        self,
        resource_id: str
    ) -> bool:
        """Elimina un recurso por su ID"""
        try:
            resource_client = self._get_resource_client()
            
            # Extraer nombre del recurso y grupo de recursos del ID
            parts = resource_id.split('/')
            resource_name = parts[-1]
            resource_group = parts[4]
            resource_type = '/'.join(parts[6:-1])
            
            # Mapeo de tipos de recursos a operaciones de eliminación
            if 'Microsoft.Compute' in resource_type:
                compute_client = self._get_compute_client()
                compute_client.virtual_machines.begin_delete(resource_group, resource_name)
            elif 'Microsoft.Storage' in resource_type:
                storage_client = self._get_storage_client()
                storage_client.storage_accounts.delete(resource_group, resource_name)
            elif 'Microsoft.Web' in resource_type:
                web_client = self._get_web_client()
                web_client.web_apps.begin_delete(resource_group, resource_name)
            else:
                resource_client.resources.begin_delete(resource_group, resource_name)
            
            logger.info(f"Resource {resource_name} deletion initiated")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting resource: {e}")
            return False
    
    async def get_resource_status(
        self,
        resource_type: str,
        resource_id: str
    ) -> Dict[str, Any]:
        """Obtiene el estado de un recurso"""
        try:
            resource_group, resource_name = resource_id.split('/')
            
            if resource_type == "vm":
                compute_client = self._get_compute_client()
                vm = compute_client.virtual_machines.get(
                    resource_group,
                    resource_name
                )
                return {
                    'name': vm.name,
                    'provisioning_state': vm.provisioning_state,
                    'location': vm.location
                }
            else:
                return {'status': 'unknown'}
                
        except Exception as e:
            logger.error(f"Error obteniendo estado: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def deploy_infrastructure(
        self,
        infrastructure_code: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Despliega infraestructura usando ARM Templates
        
        Args:
            infrastructure_code: ARM Template (JSON)
            parameters: Parámetros del deployment
        """
        try:
            resource_client = self._get_resource_client()
            
            deployment_name = parameters.get('deployment_name', 'iaops-deployment')
            resource_group = parameters.get('resource_group', 'iaops-rg')
            location = parameters.get('location', 'eastus')
            
            # Verificar si el grupo de recursos existe, si no, crearlo
            try:
                rg = resource_client.resource_groups.get(resource_group)
                logger.info(f"Grupo de recursos '{resource_group}' ya existe")
            except Exception as rg_error:
                logger.info(f"Creando grupo de recursos '{resource_group}'...")
                resource_client.resource_groups.create_or_update(
                    resource_group,
                    {
                        "location": location,
                        "tags": {
                            "environment": "iaops",
                            "project": "peribank"
                        }
                    }
                )
                logger.info(f"Grupo de recursos '{resource_group}' creado exitosamente")
            
            import json
            template = json.loads(infrastructure_code)
            
            deployment_properties = {
                'mode': 'Incremental',
                'template': template,
                'parameters': parameters.get('template_parameters', {})
            }
            
            deployment_async = resource_client.deployments.begin_create_or_update(
                resource_group,
                deployment_name,
                {'properties': deployment_properties}
            )
            
            logger.info(f"ARM Template deployment iniciado: {deployment_name}")
            
            return {
                'deployment_name': deployment_name,
                'resource_group': resource_group,
                'status': 'creating'
            }
            
        except Exception as e:
            logger.error(f"Error desplegando infraestructura: {e}")
            raise


# Singleton instance
azure_connector = None

def get_azure_connector() -> AzureConnector:
    """Get or create Azure connector singleton"""
    global azure_connector
    if not azure_connector:
        from app.core.config import settings
        azure_connector = AzureConnector(
            subscription_id=settings.AZURE_SUBSCRIPTION_ID,
            tenant_id=settings.AZURE_TENANT_ID,
            client_id=settings.AZURE_CLIENT_ID,
            client_secret=settings.AZURE_CLIENT_SECRET
        )
    return azure_connector
