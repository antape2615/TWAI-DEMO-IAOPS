"""
Orquestador de IA para generación de soluciones y arquitecturas
"""
from typing import Dict, Any, List, Optional
import json
from app.core.logging import logger
from app.core.config import settings
from app.models.schemas import Client, ArchitectureRequest, CloudProvider


class AIOrchestrator:
    """
    Orquestador de IA para IAOPS
    
    Responsable de:
    - Generar arquitecturas respetando el tech profile del cliente
    - Generar código de infraestructura (Terraform, CloudFormation, ARM)
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
    ) -> Dict[str, Any]:
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
            architecture
        )
        
        # Estimar costos (placeholder)
        estimated_cost = await self._estimate_costs(client, architecture)
        
        # Generar recomendaciones
        recommendations = await self._generate_recommendations(client, architecture)
        
        return {
            'client_id': client.id,
            'architecture': architecture,
            'infrastructure_code': infrastructure_code,
            'estimated_cost': estimated_cost,
            'recommendations': recommendations
        }
    
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
Eres un arquitecto de soluciones experto en cloud. Tu tarea es diseñar una arquitectura completa 
RESPETANDO ESTRICTAMENTE el perfil tecnológico del cliente.

{client_context}

## Requerimiento del Cliente
{description}

## Requerimientos Técnicos
{json.dumps(requirements, indent=2)}

## Tu Tarea
Diseña una arquitectura que:
1. Use SOLO las nubes permitidas por el cliente ({client_context})
2. Use SOLO los servicios permitidos (si están especificados)
3. Respete los estándares de infraestructura del cliente
4. Sea escalable, segura y eficiente en costos
5. Siga las mejores prácticas de cada cloud provider

## Formato de Respuesta (JSON)
{{
    "architecture_overview": "Descripción general de la arquitectura",
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
        architecture: Dict[str, Any]
    ) -> str:
        """
        Genera código de infraestructura basado en la arquitectura
        """
        infrastructure_standard = client.tech_profile.standards.infrastructure
        
        prompt = f"""
Genera código de infraestructura usando {infrastructure_standard} para la siguiente arquitectura:

{json.dumps(architecture, indent=2)}

Clouds a usar: {', '.join(client.tech_profile.clouds)}

Genera código {infrastructure_standard} completo y funcional.
Incluye:
- Variables
- Recursos principales
- Outputs
- Mejores prácticas de seguridad

Retorna SOLO el código, sin explicaciones.
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


# Singleton global
ai_orchestrator = AIOrchestrator()
