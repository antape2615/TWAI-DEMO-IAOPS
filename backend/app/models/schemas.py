from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class CloudProvider(str, Enum):
    """Proveedores de nube soportados"""
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"


class RepositoryProvider(str, Enum):
    """Proveedores de repositorios soportados"""
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"


class InfrastructureStandard(str, Enum):
    """Estándares de infraestructura"""
    TERRAFORM = "terraform"
    CLOUDFORMATION = "cloudformation"
    ARM_TEMPLATES = "arm_templates"
    PULUMI = "pulumi"


class CICDStandard(str, Enum):
    """Estándares de CI/CD"""
    GITHUB_ACTIONS = "github-actions"
    GITLAB_CI = "gitlab-ci"
    AZURE_DEVOPS = "azure-devops"
    JENKINS = "jenkins"
    CIRCLECI = "circleci"


class TechStandards(BaseModel):
    """Estándares tecnológicos del cliente"""
    model_config = ConfigDict(use_enum_values=True)
    
    infrastructure: InfrastructureStandard
    cicd: CICDStandard
    container_orchestration: Optional[str] = "kubernetes"
    monitoring: Optional[str] = "prometheus"
    logging: Optional[str] = "elk"


class TechProfile(BaseModel):
    """Perfil tecnológico del cliente"""
    model_config = ConfigDict(use_enum_values=True)
    
    clouds: List[CloudProvider]
    repositories: List[RepositoryProvider]
    standards: TechStandards
    allowed_services: Optional[Dict[str, List[str]]] = Field(
        default_factory=dict,
        description="Servicios permitidos por cloud: {'aws': ['ec2', 's3'], 'azure': ['vms']}"
    )
    restrictions: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Restricciones adicionales del cliente"
    )


class ClientBase(BaseModel):
    """Base para cliente"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    tech_profile: TechProfile


class ClientCreate(ClientBase):
    """Schema para crear cliente"""
    pass


class ClientUpdate(BaseModel):
    """Schema para actualizar cliente"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    tech_profile: Optional[TechProfile] = None


class ClientInDB(ClientBase):
    """Cliente en base de datos"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_active: bool = True


class Client(ClientInDB):
    """Cliente para respuestas API"""
    pass


class CloudCredentials(BaseModel):
    """Credenciales para proveedores de nube"""
    provider: CloudProvider
    credentials: Dict[str, Any] = Field(
        ...,
        description="Credenciales específicas del proveedor"
    )
    region: Optional[str] = None


class RepositoryCredentials(BaseModel):
    """Credenciales para repositorios"""
    provider: RepositoryProvider
    credentials: Dict[str, Any] = Field(
        ...,
        description="Token, usuario/contraseña, etc."
    )
    organization: Optional[str] = None


class DeploymentTarget(BaseModel):
    """Target de despliegue"""
    client_id: str
    cloud_provider: CloudProvider
    region: str
    environment: str = Field(..., description="dev, staging, prod")
    resource_tags: Optional[Dict[str, str]] = Field(default_factory=dict)


class ArchitectureRequest(BaseModel):
    """Request para generar arquitectura"""
    client_id: str
    description: str = Field(
        ...,
        description="Descripción de lo que se quiere construir"
    )
    requirements: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Requerimientos específicos (escalabilidad, seguridad, etc.)"
    )
    target_clouds: Optional[List[CloudProvider]] = None


class ArchitectureResponse(BaseModel):
    """Respuesta de generación de arquitectura"""
    client_id: str
    architecture: Dict[str, Any] = Field(
        ...,
        description="Arquitectura generada respetando el tech profile del cliente"
    )
    infrastructure_code: Optional[str] = None
    diagram: Optional[str] = None
    estimated_cost: Optional[Dict[str, Any]] = None
    recommendations: List[str] = Field(default_factory=list)
