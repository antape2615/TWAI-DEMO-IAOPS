"""
Servicio para interactuar con Grafana HTTP API
"""
import httpx
from typing import Dict, Any, Optional
from app.core.logging import logger


class GrafanaService:
    """
    Servicio para gestión de Grafana
    - Crear datasources de Azure Monitor
    - Crear dashboards automáticamente
    - Obtener URLs de dashboards
    """
    
    def __init__(self, grafana_url: str = "http://grafana:3000", public_url: str = "http://localhost:3001", api_key: Optional[str] = None):
        self.base_url = grafana_url
        self.public_url = public_url
        self.api_key = api_key or "admin"  # Default para desarrollo
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        # Si no hay API key, usar basic auth con admin:admin
        if not api_key:
            import base64
            auth = base64.b64encode(b"admin:admin").decode()
            self.headers = {
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/json"
            }
    
    async def create_azure_datasource(
        self,
        name: str,
        tenant_id: str,
        subscription_id: str,
        client_id: str,
        client_secret: str
    ) -> Dict[str, Any]:
        """
        Crea un datasource de Azure Monitor en Grafana
        
        Args:
            name: Nombre del datasource (ej: "azure-monitor-peribank")
            tenant_id: Azure Tenant ID
            subscription_id: Azure Subscription ID
            client_id: Azure Client ID (Service Principal)
            client_secret: Azure Client Secret
        
        Returns:
            Respuesta de Grafana con datasource creado
        """
        try:
            datasource_config = {
                "name": name,
                "type": "grafana-azure-monitor-datasource",
                "access": "proxy",
                "jsonData": {
                    "azureAuthType": "clientsecret",
                    "cloudName": "azuremonitor",
                    "tenantId": tenant_id,
                    "clientId": client_id,
                    "subscriptionId": subscription_id
                },
                "secureJsonData": {
                    "clientSecret": client_secret
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/datasources",
                    json=datasource_config,
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code in [200, 201]:
                    logger.info(f"Datasource {name} creado exitosamente")
                    return response.json()
                elif response.status_code == 409:
                    # Datasource ya existe
                    logger.warning(f"Datasource {name} ya existe")
                    return {"status": "exists", "name": name}
                else:
                    logger.error(f"Error creando datasource: {response.status_code} - {response.text}")
                    raise Exception(f"Error creando datasource: {response.text}")
                    
        except Exception as e:
            logger.error(f"Error en create_azure_datasource: {e}")
            raise
    
    async def create_dashboard(
        self,
        dashboard_json: Dict[str, Any],
        folder_id: int = 0,
        overwrite: bool = True
    ) -> Dict[str, Any]:
        """
        Crea un dashboard en Grafana
        
        Args:
            dashboard_json: JSON del dashboard
            folder_id: ID de la carpeta (0 = General)
            overwrite: Si sobrescribir dashboard existente
        
        Returns:
            Respuesta con UID y URL del dashboard
        """
        try:
            payload = {
                "dashboard": dashboard_json,
                "folderId": folder_id,
                "overwrite": overwrite
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/dashboards/db",
                    json=payload,
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code in [200, 201]:
                    result = response.json()
                    logger.info(f"Dashboard creado: {result.get('uid')}")
                    return result
                else:
                    logger.error(f"Error creando dashboard: {response.status_code} - {response.text}")
                    raise Exception(f"Error creando dashboard: {response.text}")
                    
        except Exception as e:
            logger.error(f"Error en create_dashboard: {e}")
            raise
    
    def get_dashboard_url(self, dashboard_uid: str, refresh: str = "30s") -> str:
        """
        Obtiene la URL embebible de un dashboard
        
        Args:
            dashboard_uid: UID del dashboard
            refresh: Intervalo de refresh (ej: "30s", "1m")
        
        Returns:
            URL completa del dashboard
        """
        # URL para embedding con rango de tiempo explícito para evitar "invalid time range"
        return f"{self.public_url}/d/{dashboard_uid}?from=now-6h&to=now&refresh={refresh}&kiosk=tv"
    
    async def create_cloudwatch_datasource(
        self,
        name: str,
        access_key_id: str,
        secret_access_key: str,
        session_token: Optional[str],
        region: str = "us-east-1"
    ) -> Dict[str, Any]:
        """
        Crea un datasource de AWS CloudWatch en Grafana
        """
        try:
            datasource_config = {
                "name": name,
                "type": "cloudwatch",
                "access": "proxy",
                "jsonData": {
                    "defaultRegion": region,
                    "authType": "default",
                    "assumeRoleArn": "",
                    "externalId": ""
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/datasources",
                    json=datasource_config,
                    headers=self.headers,
                    timeout=10.0
                )
                if response.status_code in [200, 201]:
                    logger.info(f"CloudWatch datasource {name} creado exitosamente")
                    return response.json()
                elif response.status_code == 409:
                    logger.warning(f"CloudWatch datasource {name} ya existe")
                    return {"status": "exists", "name": name}
                else:
                    logger.error(f"Error creando CloudWatch datasource: {response.status_code} - {response.text}")
                    raise Exception(f"Error creando CloudWatch datasource: {response.text}")
        except Exception as e:
            logger.error(f"Error en create_cloudwatch_datasource: {e}")
            raise

    async def get_datasources(self) -> list:
        """Lista todos los datasources"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/datasources",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Error listando datasources: {response.text}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error en get_datasources: {e}")
            return []
    
    async def test_connection(self) -> bool:
        """Prueba la conexión con Grafana"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/health",
                    timeout=5.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Error probando conexión con Grafana: {e}")
            return False
