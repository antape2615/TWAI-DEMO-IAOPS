"""
Conector para Google Cloud Platform (GCP)
"""
from google.cloud import compute_v1, storage, resourcemanager_v3
from google.oauth2 import service_account
from typing import Dict, Any, List, Optional
from app.connectors.cloud.base import BaseCloudConnector
from app.core.logging import logger


class GCPConnector(BaseCloudConnector):
    """
    Conector para Google Cloud Platform
    
    Soporta: Compute Engine, Cloud Storage, Cloud Functions, GKE, Cloud SQL, etc.
    """
    
    def __init__(self, credentials: Dict[str, Any], region: Optional[str] = "us-central1"):
        super().__init__(credentials, region)
        self.project_id = credentials.get('project_id')
        self.credentials_obj = None
        
    async def connect(self) -> bool:
        """Establece conexión con GCP"""
        try:
            # Cargar credenciales desde archivo o dict
            credentials_path = self.credentials.get('credentials_path')
            
            if credentials_path:
                self.credentials_obj = service_account.Credentials.from_service_account_file(
                    credentials_path
                )
            else:
                # Usar credenciales default
                import google.auth
                self.credentials_obj, _ = google.auth.default()
            
            # Test connection
            project_client = resourcemanager_v3.ProjectsClient(
                credentials=self.credentials_obj
            )
            
            project_name = f"projects/{self.project_id}"
            project_client.get_project(name=project_name)
            
            logger.info(f"Conectado a GCP - Project: {self.project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error conectando a GCP: {e}")
            return False
    
    async def validate_credentials(self) -> bool:
        """Valida las credenciales de GCP"""
        try:
            if not self.credentials_obj:
                await self.connect()
            
            project_client = resourcemanager_v3.ProjectsClient(
                credentials=self.credentials_obj
            )
            project_name = f"projects/{self.project_id}"
            project_client.get_project(name=project_name)
            return True
            
        except Exception as e:
            logger.error(f"Credenciales GCP inválidas: {e}")
            return False
    
    async def list_resources(self, resource_type: str) -> List[Dict[str, Any]]:
        """
        Lista recursos de GCP
        
        Args:
            resource_type: instances, storage, functions, gke, sql, etc.
        """
        try:
            if resource_type == "instances":
                return await self._list_compute_instances()
            elif resource_type == "storage":
                return await self._list_storage_buckets()
            else:
                logger.warning(f"Tipo de recurso no soportado: {resource_type}")
                return []
                
        except Exception as e:
            logger.error(f"Error listando recursos {resource_type}: {e}")
            return []
    
    async def _list_compute_instances(self) -> List[Dict[str, Any]]:
        """Lista instancias de Compute Engine"""
        instances_client = compute_v1.InstancesClient(
            credentials=self.credentials_obj
        )
        
        instances = []
        
        # GCP requiere listar por zona
        zones_client = compute_v1.ZonesClient(credentials=self.credentials_obj)
        zones = zones_client.list(project=self.project_id)
        
        for zone in zones:
            zone_instances = instances_client.list(
                project=self.project_id,
                zone=zone.name
            )
            
            for instance in zone_instances:
                status_map = {
                    'RUNNING': 'running',
                    'TERMINATED': 'stopped',
                    'STAGING': 'pending',
                    'PROVISIONING': 'pending',
                    'STOPPING': 'stopped'
                }
                instances.append({
                    'id': f"{zone.name}/{instance.name}",
                    'name': instance.name,
                    'type': 'gce_instance',
                    'zone': zone.name,
                    'machine_type': instance.machine_type.split('/')[-1],
                    'status': status_map.get(instance.status, 'unknown'),
                    'behavior': {
                        'status': instance.status,
                        'creation_timestamp': instance.creation_timestamp
                    }
                })
        
        return instances
    
    async def _list_storage_buckets(self) -> List[Dict[str, Any]]:
        """Lista buckets de Cloud Storage"""
        storage_client = storage.Client(
            project=self.project_id,
            credentials=self.credentials_obj
        )
        
        buckets = []
        for bucket in storage_client.list_buckets():
            buckets.append({
                'name': bucket.name,
                'location': bucket.location,
                'storage_class': bucket.storage_class,
                'created': str(bucket.time_created)
            })
        
        return buckets
    
    async def create_resource(
        self,
        resource_type: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Crea un recurso en GCP"""
        try:
            if resource_type == "instance":
                return await self._create_compute_instance(config)
            elif resource_type == "storage":
                return await self._create_storage_bucket(config)
            else:
                raise ValueError(f"Tipo de recurso no soportado: {resource_type}")
                
        except Exception as e:
            logger.error(f"Error creando recurso {resource_type}: {e}")
            raise
    
    async def _create_compute_instance(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Crea una instancia de Compute Engine"""
        instances_client = compute_v1.InstancesClient(
            credentials=self.credentials_obj
        )
        
        zone = config.get('zone', f"{self.region}-a")
        
        # Configuración básica de la instancia
        instance = compute_v1.Instance()
        instance.name = config['instance_name']
        instance.machine_type = f"zones/{zone}/machineTypes/{config.get('machine_type', 'e2-micro')}"
        
        # Disco de arranque
        disk = compute_v1.AttachedDisk()
        disk.boot = True
        disk.auto_delete = True
        disk.initialize_params = compute_v1.AttachedDiskInitializeParams()
        disk.initialize_params.source_image = config.get(
            'source_image',
            'projects/debian-cloud/global/images/family/debian-11'
        )
        disk.initialize_params.disk_size_gb = config.get('disk_size_gb', 10)
        
        instance.disks = [disk]
        
        # Red
        network_interface = compute_v1.NetworkInterface()
        network_interface.name = 'global/networks/default'
        
        # Acceso externo
        access_config = compute_v1.AccessConfig()
        access_config.name = 'External NAT'
        access_config.type_ = 'ONE_TO_ONE_NAT'
        network_interface.access_configs = [access_config]
        
        instance.network_interfaces = [network_interface]
        
        # Crear instancia
        operation = instances_client.insert(
            project=self.project_id,
            zone=zone,
            instance_resource=instance
        )
        
        logger.info(f"Creando instancia: {config['instance_name']}")
        
        return {
            'name': config['instance_name'],
            'zone': zone,
            'status': 'creating'
        }
    
    async def _create_storage_bucket(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un bucket de Cloud Storage"""
        storage_client = storage.Client(
            project=self.project_id,
            credentials=self.credentials_obj
        )
        
        bucket_name = config['bucket_name']
        location = config.get('location', self.region)
        storage_class = config.get('storage_class', 'STANDARD')
        
        bucket = storage_client.bucket(bucket_name)
        bucket.storage_class = storage_class
        bucket = storage_client.create_bucket(bucket, location=location)
        
        logger.info(f"Bucket creado: {bucket_name}")
        
        return {
            'name': bucket.name,
            'location': bucket.location,
            'storage_class': bucket.storage_class
        }
    
    async def delete_resource(
        self,
        resource_type: str,
        resource_id: str
    ) -> bool:
        """Elimina un recurso de GCP"""
        try:
            if resource_type == "instance":
                zone, instance_name = resource_id.split('/')
                instances_client = compute_v1.InstancesClient(
                    credentials=self.credentials_obj
                )
                instances_client.delete(
                    project=self.project_id,
                    zone=zone,
                    instance=instance_name
                )
            elif resource_type == "storage":
                storage_client = storage.Client(
                    project=self.project_id,
                    credentials=self.credentials_obj
                )
                bucket = storage_client.bucket(resource_id)
                bucket.delete()
            else:
                raise ValueError(f"Tipo de recurso no soportado: {resource_type}")
            
            logger.info(f"Recurso {resource_type}/{resource_id} eliminado")
            return True
            
        except Exception as e:
            logger.error(f"Error eliminando recurso: {e}")
            return False
    
    async def get_resource_status(
        self,
        resource_type: str,
        resource_id: str
    ) -> Dict[str, Any]:
        """Obtiene el estado de un recurso"""
        try:
            if resource_type == "instance":
                zone, instance_name = resource_id.split('/')
                instances_client = compute_v1.InstancesClient(
                    credentials=self.credentials_obj
                )
                instance = instances_client.get(
                    project=self.project_id,
                    zone=zone,
                    instance=instance_name
                )
                return {
                    'name': instance.name,
                    'status': instance.status,
                    'machine_type': instance.machine_type.split('/')[-1]
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
        Despliega infraestructura usando Deployment Manager o Terraform
        
        Args:
            infrastructure_code: Configuración de Deployment Manager (YAML)
            parameters: Parámetros del deployment
        """
        try:
            # En GCP, normalmente se usa Deployment Manager o Terraform
            # Este es un placeholder para la implementación
            
            deployment_name = parameters.get('deployment_name', 'iaops-deployment')
            
            logger.info(f"Deployment GCP iniciado: {deployment_name}")
            logger.warning("GCP Deployment Manager requiere implementación específica")
            
            return {
                'deployment_name': deployment_name,
                'project': self.project_id,
                'status': 'not_implemented'
            }
            
        except Exception as e:
            logger.error(f"Error desplegando infraestructura: {e}")
            raise
