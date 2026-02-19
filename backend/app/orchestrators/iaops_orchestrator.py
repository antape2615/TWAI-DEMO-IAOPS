"""
Orquestador principal de IAOPS
"""
from typing import Dict, Any, List, Optional
from app.core.logging import logger
from app.models.schemas import (
    Client, CloudProvider, RepositoryProvider,
    DeploymentTarget, ArchitectureRequest
)
from app.connectors.cloud.aws_connector import AWSConnector
from app.connectors.cloud.azure_connector import AzureConnector
from app.connectors.cloud.gcp_connector import GCPConnector
from app.connectors.repository.github_connector import GitHubConnector
from app.connectors.repository.gitlab_connector import GitLabConnector


class IAOPSOrchestrator:
    """
    Orquestador principal de la plataforma IAOPS
    
    Coordina:
    - Conectores de nube (AWS, Azure, GCP)
    - Conectores de repositorios (GitHub, GitLab, Bitbucket)
    - Generación de arquitecturas con IA
    - Despliegues multi-cloud
    """
    
    def __init__(self):
        self.cloud_connectors = {}
        self.repo_connectors = {}
        
    async def get_cloud_connector(
        self,
        provider: CloudProvider,
        credentials: Dict[str, Any],
        region: Optional[str] = None
    ):
        """
        Obtiene o crea un conector de nube
        
        Args:
            provider: Proveedor de nube (aws, azure, gcp)
            credentials: Credenciales del proveedor
            region: Región
            
        Returns:
            Conector inicializado
        """
        key = f"{provider}_{region}"
        
        if key not in self.cloud_connectors:
            if provider == CloudProvider.AWS:
                connector = AWSConnector(credentials, region)
            elif provider == CloudProvider.AZURE:
                connector = AzureConnector(
                    subscription_id=credentials.get('subscription_id', ''),
                    tenant_id=credentials.get('tenant_id', ''),
                    client_id=credentials.get('client_id', ''),
                    client_secret=credentials.get('client_secret', '')
                )
            elif provider == CloudProvider.GCP:
                connector = GCPConnector(credentials, region)
            else:
                raise ValueError(f"Proveedor no soportado: {provider}")
            
            connected = await connector.connect()
            if not connected:
                raise ValueError(f"No se pudo establecer conexión con {provider} ({region}). Verifique sus credenciales.")
            self.cloud_connectors[key] = connector
        
        return self.cloud_connectors[key]
    
    async def get_repository_connector(
        self,
        provider: RepositoryProvider,
        credentials: Dict[str, Any],
        organization: Optional[str] = None
    ):
        """
        Obtiene o crea un conector de repositorio
        
        Args:
            provider: Proveedor de repositorio
            credentials: Credenciales
            organization: Organización
            
        Returns:
            Conector inicializado
        """
        key = f"{provider}_{organization}"
        
        if key not in self.repo_connectors:
            if provider == RepositoryProvider.GITHUB:
                connector = GitHubConnector(credentials, organization)
            elif provider == RepositoryProvider.GITLAB:
                connector = GitLabConnector(credentials, organization)
            else:
                raise ValueError(f"Proveedor no soportado: {provider}")
            
            await connector.connect()
            self.repo_connectors[key] = connector
        
        return self.repo_connectors[key]
    
    async def orchestrate_deployment(
        self,
        client: Client,
        target: DeploymentTarget,
        infrastructure_code: str,
        architecture_metadata: Optional[Dict[str, Any]] = None,
        repository_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Orquesta un despliegue completo
        
        1. Valida que el cliente puede usar el cloud provider
        2. Obtiene el conector apropiado
        3. Despliega la infraestructura
        4. Opcionalmente crea/actualiza el repositorio con el código
        
        Args:
            client: Cliente que realiza el despliegue
            target: Target de despliegue
            infrastructure_code: Código de infraestructura
            repository_config: Configuración del repositorio (opcional)
            
        Returns:
            Resultado del despliegue
        """
        logger.info(f"Iniciando despliegue para cliente {client.id} en {target.cloud_provider}/{target.region}")
        
        # Validar que el cliente puede usar este proveedor
        if target.cloud_provider not in client.tech_profile.clouds:
            raise ValueError(
                f"Cliente {client.id} no tiene permitido usar {target.cloud_provider}. "
                f"Clouds permitidos: {client.tech_profile.clouds}"
            )
        
        # Obtener credenciales del cliente (esto debería venir de la BD)
        # Por ahora es un placeholder
        credentials = await self._get_client_cloud_credentials(
            client.id,
            target.cloud_provider
        )
        
        # Obtener conector
        connector = await self.get_cloud_connector(
            target.cloud_provider,
            credentials,
            target.region
        )
        
        # Determinar Resource Group (usar metadata de la arquitectura si existe)
        resource_group = 'iaops-rg'
        if architecture_metadata and architecture_metadata.get('resource_group_name'):
            resource_group = architecture_metadata.get('resource_group_name')
            logger.info(f"Usando Resource Group personalizado: {resource_group}")

        # Desplegar infraestructura
        deployment_result = await connector.deploy_infrastructure(
            infrastructure_code,
            parameters={
                'deployment_name': f"iaops-deploy-{target.environment}",
                'environment': target.environment,
                'tags': target.resource_tags,
                'resource_group': resource_group,
                'location': target.region or 'eastus'
            }
        )
        
        # Si hay configuración de repositorio, crear/actualizar
        if repository_config:
            await self._sync_with_repository(
                client,
                repository_config,
                infrastructure_code
            )
        
        logger.info(f"Despliegue completado: {deployment_result}")
        
        return {
            'client_id': client.id,
            'deployment': deployment_result,
            'target': target.dict(),
            'status': 'success'
        }
    
    async def _get_client_cloud_credentials(
        self,
        client_id: str,
        provider: CloudProvider
    ) -> Dict[str, Any]:
        """
        Obtiene las credenciales de cloud del cliente desde la BD
        
        TODO: Implementar consulta a base de datos real
        """
        from app.core.config import settings
        
        logger.warning(f"Obteniendo credenciales para {client_id}/{provider} - Usando Env Vars")
        
        if provider == CloudProvider.AZURE:
            return {
                'client_id': (settings.AZURE_CLIENT_ID or "").strip(),
                'client_secret': (settings.AZURE_CLIENT_SECRET or "").strip(),
                'tenant_id': (settings.AZURE_TENANT_ID or "").strip(),
                'subscription_id': (settings.AZURE_SUBSCRIPTION_ID or "").strip()
            }
        elif provider == CloudProvider.AWS:
            return {
                'access_key_id': (settings.AWS_ACCESS_KEY_ID or "").strip(),
                'secret_access_key': (settings.AWS_SECRET_ACCESS_KEY or "").strip(),
                'session_token': (settings.AWS_SESSION_TOKEN or "").strip() or None,
                'region': (settings.AWS_DEFAULT_REGION or "").strip()
            }
        
        # Default placeholder
        return {
            'access_key_id': 'placeholder',
            'secret_access_key': 'placeholder'
        }
    
    async def _sync_with_repository(
        self,
        client: Client,
        repository_config: Dict[str, Any],
        infrastructure_code: str
    ):
        """
        Sincroniza el código de infraestructura con el repositorio
        """
        provider = repository_config['provider']
        repo_name = repository_config['repository']
        
        # Validar que el cliente puede usar este proveedor
        if provider not in client.tech_profile.repositories:
            raise ValueError(
                f"Cliente {client.id} no tiene permitido usar {provider}"
            )
        
        # Obtener credenciales
        credentials = await self._get_client_repo_credentials(client.id, provider)
        
        # Obtener conector
        connector = await self.get_repository_connector(
            provider,
            credentials,
            repository_config.get('organization')
        )
        
        # Crear o actualizar archivo
        await connector.commit_file(
            repo_name=repo_name,
            file_path=repository_config.get('file_path', 'infrastructure/main.tf'),
            content=infrastructure_code,
            message=f"Update infrastructure code - IAOPS automated commit",
            branch=repository_config.get('branch', 'main')
        )
        
        logger.info(f"Código sincronizado con {provider}/{repo_name}")
    
    async def _get_client_repo_credentials(
        self,
        client_id: str,
        provider: RepositoryProvider
    ) -> Dict[str, Any]:
        """
        Obtiene las credenciales de repositorio del cliente
        
        TODO: Implementar consulta a base de datos
        """
        logger.warning(f"Obteniendo credenciales repo para {client_id}/{provider} - Placeholder")
        
        return {
            'token': 'placeholder'
        }
    
    async def list_client_resources(
        self,
        client: Client,
        cloud_provider: CloudProvider,
        resource_type: str
    ) -> List[Dict[str, Any]]:
        """
        Lista recursos de un cliente en un proveedor específico
        
        Args:
            client: Cliente
            cloud_provider: Proveedor de nube
            resource_type: Tipo de recurso (ec2, s3, vms, etc.)
            
        Returns:
            Lista de recursos
        """
        # Validar permisos
        if cloud_provider not in client.tech_profile.clouds:
            raise ValueError(f"Cliente no tiene acceso a {cloud_provider}")
        
        # Obtener credenciales y conector (pasar región si viene en las credenciales)
        credentials = await self._get_client_cloud_credentials(client.id, cloud_provider)
        region = credentials.get('region') or None
        connector = await self.get_cloud_connector(cloud_provider, credentials, region)
        
        # Listar recursos
        resources = await connector.list_resources(resource_type)
        
        return resources
    
    async def validate_tech_profile(self, client: Client) -> Dict[str, Any]:
        """
        Valida el perfil tecnológico del cliente
        
        Verifica:
        - Credenciales de clouds configuradas
        - Credenciales de repositorios configuradas
        - Permisos y conectividad
        
        Returns:
            Reporte de validación
        """
        report = {
            'client_id': client.id,
            'clouds': {},
            'repositories': {},
            'overall_status': 'valid'
        }
        
        # Validar clouds
        for cloud in client.tech_profile.clouds:
            try:
                credentials = await self._get_client_cloud_credentials(client.id, cloud)
                connector = await self.get_cloud_connector(cloud, credentials)
                is_valid = await connector.validate_credentials()
                
                report['clouds'][cloud] = {
                    'status': 'valid' if is_valid else 'invalid',
                    'message': 'Credentials validated' if is_valid else 'Invalid credentials'
                }
                
                if not is_valid:
                    report['overall_status'] = 'invalid'
                    
            except Exception as e:
                report['clouds'][cloud] = {
                    'status': 'error',
                    'message': str(e)
                }
                report['overall_status'] = 'invalid'
        
        # Validar repositorios
        for repo in client.tech_profile.repositories:
            try:
                credentials = await self._get_client_repo_credentials(client.id, repo)
                connector = await self.get_repository_connector(repo, credentials)
                is_valid = await connector.validate_credentials()
                
                report['repositories'][repo] = {
                    'status': 'valid' if is_valid else 'invalid',
                    'message': 'Credentials validated' if is_valid else 'Invalid credentials'
                }
                
                if not is_valid:
                    report['overall_status'] = 'invalid'
                    
            except Exception as e:
                report['repositories'][repo] = {
                    'status': 'error',
                    'message': str(e)
                }
                report['overall_status'] = 'invalid'
        
        return report
    
    async def cleanup(self):
        """Limpia las conexiones"""
        for connector in self.cloud_connectors.values():
            await connector.disconnect()
        
        for connector in self.repo_connectors.values():
            await connector.disconnect()
        
        self.cloud_connectors.clear()
        self.repo_connectors.clear()


# Singleton global
orchestrator = IAOPSOrchestrator()
