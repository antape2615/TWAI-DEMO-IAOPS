"""
Orquestador de IA para generación de soluciones y arquitecturas
"""
from typing import Dict, Any, List, Optional
import json
import re
from app.core.logging import logger
from app.core.config import settings
from app.models.schemas import Client, ArchitectureRequest, CloudProvider, ArchitectureResponse


class AIOrchestrator:
    """
    Orquestador de IA para IAOPS
    
    Responsable de:
    - Generar arquitecturas respetando el tech profile del cliente
    - Generar código de infraestructura (Terraform, CloudFormation, ARM/Bicep)
    - Generar pipelines de CI/CD automáticamente
    - Diseñar soluciones alineadas a las tecnologías del cliente
    - Estimar costos
    - Generar recomendaciones
    """
    
    def __init__(self):
        self.openai_client = None
        self.azure_openai_client = None
        self.anthropic_client = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Inicializa los clientes de IA"""
        try:
            # OpenAI standard
            if settings.OPENAI_API_KEY:
                import openai
                self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("OpenAI client initialized")
            
            # Azure OpenAI
            if settings.AZURE_OPENAI_API_KEY and settings.AZURE_OPENAI_ENDPOINT:
                from openai import AzureOpenAI
                self.azure_openai_client = AzureOpenAI(
                    api_key=settings.AZURE_OPENAI_API_KEY,
                    api_version=settings.AZURE_OPENAI_API_VERSION,
                    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
                )
                logger.info(f"Azure OpenAI client initialized: {settings.AZURE_OPENAI_DEPLOYMENT_NAME}")
            
            # Anthropic
            if settings.ANTHROPIC_API_KEY:
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
                logger.info("Anthropic client initialized")
        except Exception as e:
            logger.warning(f"Error inicializando clientes de IA: {e}")

    async def generate_architecture(
        self,
        client: Client,
        request: ArchitectureRequest
    ) -> ArchitectureResponse:
        """
        Genera una arquitectura completa respetando el tech profile del cliente
        
        Args:
            client: Cliente con su perfil tecnológico
            request: Request con descripción y requerimientos
            
        Returns:
            Arquitectura generada con código de infraestructura
        """
        logger.info(f"Generando arquitectura para cliente {client.id}")
        
        # Construir contexto del cliente
        client_context = self._build_client_context(client)
        
        # Construir prompt
        prompt = self._build_architecture_prompt(
            client_context,
            request.description,
            request.requirements
        )
        
        # Generar con IA
        architecture_response = await self._call_ai(prompt)
        
        # Parsear respuesta
        architecture = self._parse_architecture_response(architecture_response)
        
        # Generar código de infraestructura
        infrastructure_code = await self._generate_infrastructure_code(
            client,
            architecture,
            infrastructure_standard=request.infrastructure_standard
        )
        
        # Estimar costos (placeholder)
        estimated_cost = await self._estimate_costs(client, architecture)
        
        # Generar recomendaciones
        recommendations = await self._generate_recommendations(client, architecture)
        
        return ArchitectureResponse(
            client_id=client.id,
            architecture=architecture,
            infrastructure_code=infrastructure_code,
            estimated_cost=estimated_cost,
            recommendations=recommendations
        )
    
    def _build_client_context(self, client: Client) -> str:
        """
        Construye el contexto del cliente para el prompt
        """
        tech_profile = client.tech_profile
        
        context = f"""
# Perfil Tecnológico del Cliente: {client.name}

## Clouds Permitidos
{', '.join(tech_profile.clouds)}

## Repositorios
{', '.join(tech_profile.repositories)}

## Estándares
- Infraestructura como Código: {tech_profile.standards.infrastructure}
- CI/CD: {tech_profile.standards.cicd}
- Orquestación de Contenedores: {tech_profile.standards.container_orchestration}
- Monitoring: {tech_profile.standards.monitoring or 'No especificado'}
- Logging: {tech_profile.standards.logging or 'No especificado'}

## Servicios Permitidos
{json.dumps(tech_profile.allowed_services, indent=2) if tech_profile.allowed_services else 'Todos los servicios estándar'}

## Restricciones
{json.dumps(tech_profile.restrictions, indent=2) if tech_profile.restrictions else 'Sin restricciones adicionales'}
"""
        return context
    
    def _build_architecture_prompt(
        self,
        client_context: str,
        description: str,
        requirements: Dict[str, Any]
    ) -> str:
        """
        Construye el prompt para generar la arquitectura
        """
        prompt = f"""
Eres un arquitecto de soluciones experto en cloud. Tu tarea es diseñar una arquitectura basada en el requerimiento del cliente.

{client_context}

## Requerimiento del Cliente (PRIORIDAD MÁXIMA)
{description}

## Requerimientos Técnicos
{json.dumps(requirements, indent=2)}

## Tu Tarea
Diseña una arquitectura que:
1. Resuelva EL REQUERIMIENTO DEL CLIENTE usando SOLO los recursos necesarios. NO agregues recursos no solicitados (como Kubernetes, Grafana, ELK, Application Gateway) a menos que el usuario los pida explícitamente.
2. Use EL MENOR COSTO posible para entornos de prueba (ej: App Service Plan F1/B1, VMs B-series) a menos que se especifique producción.
3. Use el Perfil Tecnológico anterior solo como lista de "servicios permitidos", NO como mandato de inclusión. Si el perfil menciona Kubernetes pero el usuario pide una Web App, SOLO genera la Web App.
4. Use SOLO las nubes permitidas por el cliente.
5. Siga las mejores prácticas de seguridad (pero sin agregar complejidad innecesaria).

## Formato de Respuesta (JSON)
{{
    "architecture_overview": "Descripción general de la arquitectura",
    "resource_group_name": "Nombre del grupo de recursos (ej: rg_peribank_app). Usa el indicado por el usuario o uno descriptivo.",
    "components": [
        {{
            "name": "Nombre del componente",
            "type": "Tipo (compute, storage, database, etc.)",
            "cloud_service": "Servicio específico (ej: AWS EC2, Azure VM, etc.)",
            "description": "Descripción del componente",
            "configuration": {{}}
        }}
    ],
    "data_flow": "Descripción del flujo de datos",
    "security": {{
        "authentication": "Método de autenticación",
        "encryption": "Estrategia de encriptación",
        "network_isolation": "Aislamiento de red"
    }},
    "scalability": {{
        "horizontal": "Estrategia de escalado horizontal",
        "vertical": "Estrategia de escalado vertical",
        "auto_scaling": "Configuración de auto-scaling"
    }},
    "disaster_recovery": {{
        "backup_strategy": "Estrategia de backups",
        "rto": "Recovery Time Objective",
        "rpo": "Recovery Point Objective"
    }}
}}

Genera SOLO el JSON, sin explicaciones adicionales.
"""
        return prompt
    
    async def _call_ai(self, prompt: str) -> str:
        """
        Llama al servicio de IA para generar la arquitectura
        Prioridad: Azure OpenAI > OpenAI > Anthropic
        """
        try:
            # Prioridad 1: Azure OpenAI (si está configurado)
            if self.azure_openai_client and settings.AZURE_OPENAI_DEPLOYMENT_NAME:
                logger.info(f"Usando Azure OpenAI: {settings.AZURE_OPENAI_DEPLOYMENT_NAME}")
                response = self.azure_openai_client.chat.completions.create(
                    model=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                    messages=[
                        {
                            "role": "system",
                            "content": "Eres un arquitecto de soluciones cloud experto. Respondes SOLO con JSON válido."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.7,
                    max_tokens=4000
                )
                
                return response.choices[0].message.content
            
            # Prioridad 2: OpenAI standard
            elif self.openai_client:
                logger.info(f"Usando OpenAI: {settings.OPENAI_MODEL}")
                response = self.openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "Eres un arquitecto de soluciones cloud experto. Respondes SOLO con JSON válido."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.7,
                    max_tokens=4000
                )
                
                return response.choices[0].message.content
            
            # Prioridad 3: Anthropic
            elif self.anthropic_client:
                logger.info(f"Usando Anthropic: {settings.ANTHROPIC_MODEL}")
                response = self.anthropic_client.messages.create(
                    model=settings.ANTHROPIC_MODEL,
                    max_tokens=4000,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )
                
                return response.content[0].text
            
            else:
                raise Exception("No hay cliente de IA configurado. Configura AZURE_OPENAI_API_KEY o OPENAI_API_KEY en .env")
                
        except Exception as e:
            logger.error(f"Error llamando a IA: {e}")
            raise
    
    def _parse_architecture_response(self, response: str) -> Dict[str, Any]:
        """
        Parsea la respuesta de la IA
        """
        try:
            # Limpiar respuesta si tiene markdown
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            return json.loads(response.strip())
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando respuesta de IA: {e}")
            logger.error(f"Respuesta: {response}")
            
            # Retornar estructura básica
            return {
                "architecture_overview": "Error parseando respuesta de IA",
                "components": [],
                "raw_response": response
            }
    
    async def _generate_infrastructure_code(
        self,
        client: Client,
        architecture: Dict[str, Any],
        infrastructure_standard: Optional[str] = None
    ) -> str:
        """
        Genera código de infraestructura basado en la arquitectura
        """
        # Si no se especifica, usar Bicep por defecto para Azure (más simple que ARM)
        if not infrastructure_standard:
            infrastructure_standard = client.tech_profile.standards.infrastructure
        
        # ARM templates work better with Azure CLI - no conversion needed
        # El código ARM (JSON) se despliega directamente sin problemas
        
        prompt = f"""
Genera código de infraestructura usando {infrastructure_standard} para la siguiente arquitectura:

{json.dumps(architecture, indent=2)}

Clouds a usar: {', '.join(client.tech_profile.clouds)}

## REGLAS CRÍTICAS DE AZURE (ARM Templates JSON):

1. GENERAL:
    - NO incluyas el recurso 'Microsoft.Resources/resourceGroups'.
    - **UBICACIÓN: Usa solo 'eastus' o 'westus2' (sin espacios, minúsculas).**
    - **API VERSIONS - Usa SOLO estas versiones probadas:**
      - Microsoft.Web/serverFarms: '2022-09-01' (NO usar 2023+)
      - Microsoft.Web/sites: '2022-09-01'
      - Microsoft.Compute/virtualMachines: '2021-03-01'
      - Microsoft.Compute/disks: '2021-04-01' (NO usar 2021-08-01)
      - Microsoft.Network/virtualNetworks: '2021-03-01'
      - Microsoft.Network/publicIPAddresses: '2021-03-01'
      - Microsoft.Network/networkInterfaces: '2021-03-01'
      - Microsoft.Storage/storageAccounts: '2021-04-01'
    - HARDCODEA valores directamente en la sección 'resources'. NO uses 'parameters' ni 'variables' en el JSON final para evitar errores de deserialización.
    - **Usa formato JSON estándar con comillas dobles (").**

2. MICROSOFT.WEB/SITES (App Service):
    - 'name': NO puede contener guiones bajos (_). Usa solo guiones medios (-).
    - 'kind': SIEMPRE usar 'app,linux' para Linux (con coma, NO con espacios)
    - 'properties.serverFarmId': Debe estar dentro de 'properties'.
    - 'dependsOn': DEBE incluir explícitamente el resourceId del App Service Plan.
    - 'siteConfig.linuxFxVersion' (CRÍTICO): Usa solo formatos con pipe (|). Valores permitidos: 'NODE|20-lts', 'PYTHON|3.11', 'DOTNETCORE|8.0', 'JAVA|17-java17'.
    - **IMPORTANTE: Si necesitas un App Service (Microsoft.Web/sites), DEBES crear primero el App Service Plan (Microsoft.Web/serverFarms) en el mismo template.**
    - **EJEMPLO CORRECTO:**
      {{
        "type": "Microsoft.Web/sites",
        "apiVersion": "2022-09-01",
        "name": "peribank-mobile",
        "location": "eastus",
        "kind": "app,linux",
        "dependsOn": ["[resourceId('Microsoft.Web/serverFarms', 'peribank-mobile-plan')]"],
        "properties": {{
          "serverFarmId": "[resourceId('Microsoft.Web/serverFarms', 'peribank-mobile-plan')]",
          "siteConfig": {{
            "linuxFxVersion": "PYTHON|3.11"
          }}
        }}
      }}

3. MICROSOFT.WEB/SERVERFARMS (App Service Plan):
    - **NUNCA usar 'computeMode' en las propiedades.**
    - Para Linux: 'kind': 'linux' y agregar 'reserved': true
    - Para Windows: 'kind': 'windows'
    - **EJEMPLO CORRECTO:**
      {{
        "type": "Microsoft.Web/serverFarms",
        "apiVersion": "2022-09-01",
        "name": "peribank-mobile-plan",
        "location": "eastus",
        "kind": "linux",
        "sku": {{ "name": "F1", "tier": "Free" }},
        "properties": {{ "reserved": true }}
      }}

3. MICROSOFT.WEB/SERVERFARMS (App Service Plan):
    - **NUNCA usar 'computeMode' en las propiedades.**
    - Para Linux: sku.tier = 'Basic', sku.name = 'B1', kind = 'linux'
    - Para Windows: sku.tier = 'Basic', sku.name = 'B1', kind = 'windows'
    - **NO incluir reserved para Linux si no es necesario.**

4. MICROSOFT.WEB/SITES (Azure Functions):
    - tipo = 'functionapp'
    - **NO usar serverFarmId** - usar el plan de consumo o el app service plan directamente.
    - Para Functions Linux: 'kind': 'functionapp,linux'
    - Para Functions Windows: 'kind': 'functionapp'
    - **NO especificar computeMode en el siteConfig.**

3. MICROSOFT.COMPUTE (VMs & Disks):
    - 'disks': Usa apiVersion '2021-04-01'. Usa 'sku': {{ 'name': 'Standard_LRS' }} (nunca properties.accountType).
    - 'virtualMachines': Cada disco en 'dataDisks' DEBE tener un 'lun' único empezando en 0.
    - 'adminUsername': Sin '@' ni puntos. Máximo 20 caracteres.
    - 'adminPassword': Usa siempre 'IaOps.2026.Deploy!'.

4. MICROSOFT.NETWORK:
    - 'publicIPAddresses': El 'sku': {{ 'name': 'Standard' }} debe estar al mismo nivel que 'name' y 'type' (FUERA de properties).
    - 'networkInterfaces': El 'networkSecurityGroup' debe ir en la raíz de 'properties' del NIC, NO en 'ipConfigurations'.
    - SUBREDES: Al usar resourceId para subnets, pasa SIEMPRE 2 argumentos: [VNET_Name, Subnet_Name].

5. MICROSOFT.CONTAINERSERVICE (AKS):
    - apiVersion: '2024-01-01'.
    - 'kubernetesVersion': '1.29.0'.
    - 'dnsPrefix': Debe ser 'aks-dns' o similar (no puede estar vacío).
    - 'identity': Usa {{ 'type': 'SystemAssigned' }}. OMITIR 'servicePrincipalProfile'.
    - 'agentPoolProfiles': El primero debe ser name: 'agentpool' y mode: 'System'.

6. MICROSOFT.STORAGE:
    - apiVersion: '2021-09-01'.
    - Nombre: 3-24 caracteres, solo minúsculas y números.

7. MICROSOFT.LOGIC/WORKFLOWS (Logic Apps):
    - apiVersion: '2019-05-01' (NO usar versiones más recientes).
    - DEFINICIÓN: Usa 'definition' en la raíz, NO en 'properties.definition'.

8. MICROSOFT.WEB/CONNECTIONS (API Connections):
    - CRÍTICO: NO uses este recurso. Si necesitas una conexión, créala manualmente en el portal o usa Managed Identity.
    - Este recurso tiene apiVersions limitadas (2015-08-01-preview a 2018-07-01-preview) y no está disponible en todas las ubicaciones.

## REGLAS DE SEGURIDAD Y FORMATO:
- Si es Terraform, incluye provider configuration y el resource group '{architecture.get('resource_group_name', 'iaops-rg')}'.
- Retorna SOLO el código. NO incluyas bloques de markdown (```), ni explicaciones, ni comentarios.

Retorna SOLO el código, sin explicaciones ni markdown.
"""
        
        try:
            code = await self._call_ai(prompt)
            
            # Limpiar markdown si existe
            if "```" in code:
                lines = code.split("\n")
                code_lines = []
                in_code_block = False
                
                for line in lines:
                    if line.strip().startswith("```"):
                        in_code_block = not in_code_block
                        continue
                    if in_code_block or not line.strip().startswith("#"):
                        code_lines.append(line)
                
                code = "\n".join(code_lines)
            
            return code.strip()
            
        except Exception as e:
            logger.error(f"Error generando código de infraestructura: {e}")
            return f"# Error generating infrastructure code: {e}"
    
    async def _estimate_costs(
        self,
        client: Client,
        architecture: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Estima los costos de la arquitectura
        
        TODO: Implementar estimación real de costos usando APIs de pricing
        """
        logger.info(f"Estimando costos para cliente {client.id}")
        
        # Placeholder - en producción usar APIs de pricing
        return {
            'monthly_estimate': {
                'min': 100,
                'max': 500,
                'currency': 'USD'
            },
            'breakdown': {
                'compute': 'Est. $200-300/month',
                'storage': 'Est. $50-100/month',
                'network': 'Est. $50-100/month'
            },
            'note': 'Estimación preliminar. Costos reales dependen del uso.'
        }
    
    async def _generate_recommendations(
        self,
        client: Client,
        architecture: Dict[str, Any]
    ) -> List[str]:
        """
        Genera recomendaciones para optimizar la arquitectura
        """
        recommendations = []
        
        # Recomendaciones basadas en el perfil del cliente
        if len(client.tech_profile.clouds) > 1:
            recommendations.append(
                "Multi-cloud detectado: Considere usar Terraform para gestión unificada"
            )
        
        # Recomendaciones de seguridad
        recommendations.append(
            "Implemente WAF y DDoS protection para endpoints públicos"
        )
        
        recommendations.append(
            "Configure monitoring y alertas desde el inicio (Prometheus, CloudWatch, etc.)"
        )
        
        recommendations.append(
            "Use IaC versionado en repositorio con revisiones de código"
        )
        
        return recommendations

    async def generate_cicd_pipeline(
        self,
        client: Client,
        resource_type: str,
        resource_name: str,
        resource_group: str,
        cloud_provider: str,
        application_type: str = "nodejs"
    ) -> Dict[str, Any]:
        """
        Genera un pipeline de CI/CD basado en la configuración del cliente
        
        Args:
            client: Cliente con su perfil tecnológico
            resource_type: Tipo de recurso (sites, containerApps, managedClusters, etc.)
            resource_name: Nombre del recurso
            resource_group: Grupo de recursos
            cloud_provider: Proveedor de nube (azure, aws, gcp)
            application_type: Tipo de aplicación (nodejs, python, dotnet, java, go)
            
        Returns:
            Diccionario con el pipeline generado y metadatos
        """
        logger.info(f"Generando pipeline CI/CD para {client.id} - {resource_type}")
        
        # Obtener el tipo de CI/CD del cliente
        cicd_provider = client.tech_profile.standards.cicd if client.tech_profile.standards else "github_actions"
        
        # Construir el contexto
        prompt = self._build_cicd_prompt(
            client_name=client.name,
            cicd_provider=cicd_provider,
            cloud_provider=cloud_provider,
            resource_type=resource_type,
            resource_name=resource_name,
            resource_group=resource_group,
            application_type=application_type
        )
        
        # Generar con IA
        pipeline_response = await self._call_ai(prompt)
        
        # Parsear respuesta
        pipeline = self._parse_cicd_response(pipeline_response, cicd_provider)
        
        return {
            'pipeline_content': pipeline.get('content', ''),
            'file_path': pipeline.get('file_path', ''),
            'cicd_provider': cicd_provider,
            'cloud_provider': cloud_provider,
            'resource_type': resource_type,
            'metadata': pipeline.get('metadata', {})
        }

    def _build_cicd_prompt(
        self,
        client_name: str,
        cicd_provider: str,
        cloud_provider: str,
        resource_type: str,
        resource_name: str,
        resource_group: str,
        application_type: str
    ) -> str:
        """
        Construye el prompt para generar el pipeline CI/CD
        """
        # Mapeo de tipos de recurso a servicios
        resource_mapping = {
            'sites': 'Azure App Service',
            'containerApps': 'Azure Container Apps',
            'managedClusters': 'Azure Kubernetes Service (AKS)',
            'functionApp': 'Azure Functions',
            'virtualMachines': 'Azure Virtual Machines',
            'aws_instance': 'AWS EC2',
            'aws_ecs': 'AWS ECS',
            'aws_eks': 'AWS EKS',
            'aws_lambda': 'AWS Lambda',
            'compute.googleapis.com': 'Google Compute Engine',
            'kubernetes.io/cluster': 'GKE'
        }
        
        # Mapeo de tipos de aplicación a versiones
        app_versions = {
            'nodejs': '18',
            'python': '3.11',
            'dotnet': '7.0',
            'java': '17',
            'go': '1.21'
        }
        
        app_version = app_versions.get(application_type, 'latest')
        
        # Detectar el tipo de pipeline
        cicd_info = self._get_cicd_info(cicd_provider)
        
        prompt = f"""
Eres un experto en CI/CD y DevOps. Tu tarea es generar un pipeline de CI/CD completo y funcional.

## Contexto del Cliente
- Cliente: {client_name}
- Proveedor CI/CD: {cicd_provider}
- Proveedor Cloud: {cloud_provider}
- Tipo de Recurso: {resource_type} ({resource_mapping.get(resource_type, resource_type)})
- Nombre del Recurso: {resource_name}
- Grupo de Recursos: {resource_group}
- Tipo de Aplicación: {application_type}
- Versión: {app_version}

## Tu Tarea
Genera un archivo de pipeline CI/CD COMPLETO y FUNCIONAL que:
1. Haga checkout del código
2. Instale las dependencias apropiadas
3. Ejecute tests (si aplica)
4. Haga build de la aplicación
5. Haga deploy al recurso especificado

## Reglas CRÍTICAS:

### Para GitHub Actions (.github/workflows/deploy.yml):
- El pipeline DEBE incluir `workflow_dispatch` trigger para permitir ejecución manual
- Usa la acción `azure/login@v1` para autenticarse en Azure
- Para Azure App Service: usa `az webapp deployment source config-zip`
- Para AKS: usa `az aks get-credentials` y `kubectl apply`
- Para Container Apps: usa `az containerapp up` o `az containerapp deployment`
- Para Functions: usa `azure/functions-action@v1`
- Incluye secretos: AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID
- Parsing del resource ID: extrae subscription, resource group, y nombre del recurso
- Incluye pasos de verificación post-despliegue

### Formato de workflow_dispatch:
```yaml
on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment'
        required: true
        default: 'production'
```

### Para Azure DevOps (azure-pipelines.yml):
- Usa el task `AzureWebApp@1` para App Service
- Usa `Kubernetes@1` para AKS
- Usa `AzureContainerApp@1` para Container Apps

### Para GitLab CI (.gitlab-ci.yml):
- Usa `azure/cli` o `docker` con Azure CLI
- Implementa stages: build, test, deploy

### Para Jenkins (Jenkinsfile):
- Pipeline scripted o declarative
- Usa Azure CLI o plugins de Azure

### Para CircleCI (.circleci/config.yml):
- Usa orbs de Azure (`circleci/azure-orb`)

## Formato de Respuesta (JSON)
{{"file_path": ".github/workflows/deploy.yml", "content": "...pipeline yaml...", "metadata": {{}}}}

Retorna SOLO el JSON, sin explicaciones adicionales.
"""
        return prompt
    
    def _get_cicd_info(self, cicd_provider: str) -> Dict[str, Any]:
        """Obtiene información del proveedor CI/CD"""
        cicd_map = {
            'github_actions': {
                'name': 'GitHub Actions',
                'file': '.github/workflows/deploy.yml',
                'workflow_dispatch': True
            },
            'azure_devops': {
                'name': 'Azure DevOps',
                'file': 'azure-pipelines.yml',
                'trigger': True
            },
            'gitlab_ci': {
                'name': 'GitLab CI',
                'file': '.gitlab-ci.yml',
                'stages': ['build', 'test', 'deploy']
            },
            'jenkins': {
                'name': 'Jenkins',
                'file': 'Jenkinsfile',
                'type': 'declarative'
            },
            'circleci': {
                'name': 'CircleCI',
                'file': '.circleci/config.yml',
                'orbs': ['azure']
            }
        }
        return cicd_map.get(cicd_provider, cicd_map['github_actions'])
    
    def _parse_cicd_response(self, response: str, cicd_provider: str) -> Dict[str, Any]:
        """
        Parsea la respuesta de la IA para el pipeline CI/CD
        """
        try:
            # Limpiar respuesta si tiene markdown
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            parsed = json.loads(response.strip())
            
            # Validar que tiene los campos necesarios
            if 'content' not in parsed:
                # Si no hay campo content, intentar obtener el contenido de otra forma
                parsed = {'content': response, 'file_path': '.github/workflows/deploy.yml', 'metadata': {}}
            
            return parsed
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando respuesta de CI/CD: {e}")
            logger.error(f"Respuesta: {response}")
            
            # Retornar respuesta genérica
            return {
                'content': response,
                'file_path': self._get_cicd_info(cicd_provider).get('file', '.github/workflows/deploy.yml'),
                'metadata': {'error': str(e)}
            }


# Singleton global
ai_orchestrator = AIOrchestrator()
