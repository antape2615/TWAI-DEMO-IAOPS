"""
Conector para Azure OpenAI
"""
from typing import Dict, Any, Optional, List
from openai import AzureOpenAI
from app.connectors.ai.base import BaseAIConnector
from app.core.config import settings
from app.core.logging import logger


class AzureOpenAIConnector(BaseAIConnector):
    """
    Conector para Azure OpenAI
    
    Permite usar modelos GPT-4, GPT-3.5-turbo, etc. alojados en Azure
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        api_version: Optional[str] = None,
        deployment_name: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        Inicializa el conector de Azure OpenAI
        
        Args:
            api_key: API key de Azure OpenAI
            endpoint: Endpoint de Azure OpenAI (ej: https://your-resource.openai.azure.com/)
            api_version: Versión de la API (ej: 2024-02-15-preview)
            deployment_name: Nombre del deployment en Azure
            model: Modelo a usar (gpt-4, gpt-35-turbo, etc.)
        """
        self.api_key = api_key or settings.AZURE_OPENAI_API_KEY
        self.endpoint = endpoint or settings.AZURE_OPENAI_ENDPOINT
        self.api_version = api_version or settings.AZURE_OPENAI_API_VERSION
        self.deployment_name = deployment_name or settings.AZURE_OPENAI_DEPLOYMENT_NAME
        self.model = model or settings.AZURE_OPENAI_MODEL
        self.client: Optional[AzureOpenAI] = None
        
        logger.info(f"Azure OpenAI Connector inicializado para deployment: {self.deployment_name}")
    
    async def connect(self) -> bool:
        """
        Establece conexión con Azure OpenAI
        """
        try:
            if not self.api_key:
                raise ValueError("Azure OpenAI API key no configurada")
            
            if not self.endpoint:
                raise ValueError("Azure OpenAI endpoint no configurado")
            
            if not self.deployment_name:
                raise ValueError("Azure OpenAI deployment name no configurado")
            
            self.client = AzureOpenAI(
                api_key=self.api_key,
                api_version=self.api_version,
                azure_endpoint=self.endpoint
            )
            
            # Test de conexión
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            
            logger.info(f"✅ Conexión exitosa a Azure OpenAI: {self.deployment_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error conectando a Azure OpenAI: {e}")
            return False
    
    async def validate_credentials(self) -> Dict[str, Any]:
        """
        Valida las credenciales de Azure OpenAI
        """
        try:
            is_connected = await self.connect()
            
            return {
                "valid": is_connected,
                "provider": "azure_openai",
                "endpoint": self.endpoint,
                "deployment": self.deployment_name,
                "model": self.model,
                "api_version": self.api_version
            }
            
        except Exception as e:
            return {
                "valid": False,
                "provider": "azure_openai",
                "error": str(e)
            }
    
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """
        Genera una respuesta usando Azure OpenAI
        
        Args:
            prompt: Prompt del usuario
            system_prompt: Prompt del sistema (opcional)
            temperature: Temperatura para la generación (0-2)
            max_tokens: Número máximo de tokens
            **kwargs: Argumentos adicionales para la API
            
        Returns:
            Respuesta generada por el modelo
        """
        try:
            if not self.client:
                await self.connect()
            
            messages = []
            
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generando respuesta con Azure OpenAI: {e}")
            raise
    
    async def generate_architecture(
        self,
        description: str,
        tech_profile: Dict[str, Any],
        requirements: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Genera una arquitectura usando Azure OpenAI respetando el tech profile
        
        Args:
            description: Descripción de lo que se quiere construir
            tech_profile: Perfil tecnológico del cliente (clouds, repos, standards)
            requirements: Requerimientos adicionales
            
        Returns:
            Arquitectura generada con componentes, servicios, diagrama, etc.
        """
        try:
            # Construir el system prompt
            system_prompt = self._build_architecture_system_prompt(tech_profile)
            
            # Construir el user prompt
            user_prompt = self._build_architecture_user_prompt(
                description,
                tech_profile,
                requirements
            )
            
            # Generar respuesta
            response = await self.generate_completion(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=3000
            )
            
            # Parsear y estructurar la respuesta
            architecture = self._parse_architecture_response(response, tech_profile)
            
            return architecture
            
        except Exception as e:
            logger.error(f"Error generando arquitectura con Azure OpenAI: {e}")
            raise
    
    def _build_architecture_system_prompt(self, tech_profile: Dict[str, Any]) -> str:
        """
        Construye el system prompt para generación de arquitecturas
        """
        clouds = ", ".join(tech_profile.get("clouds", []))
        repos = ", ".join(tech_profile.get("repositories", []))
        standards = tech_profile.get("standards", {})
        iac = standards.get("infrastructure", "terraform")
        cicd = standards.get("cicd", "github-actions")
        
        return f"""Eres un arquitecto de soluciones cloud experto en diseño de arquitecturas escalables y seguras.

IMPORTANTE - RESTRICCIONES DEL CLIENTE:
- Clouds PERMITIDOS: {clouds}
- Repositorios PERMITIDOS: {repos}
- Estándar IaC: {iac}
- Estándar CI/CD: {cicd}
- Orquestación: {standards.get('container_orchestration', 'kubernetes')}

REGLAS:
1. SOLO usa los clouds permitidos ({clouds})
2. SOLO usa servicios reales que existen en esos clouds
3. NO inventes servicios o tecnologías
4. Respeta el estándar de IaC ({iac})
5. Respeta el estándar de CI/CD ({cicd})
6. Diseña para producción (alta disponibilidad, seguridad, escalabilidad)
7. Proporciona nombres reales de servicios (ej: Amazon EC2, Azure App Service, etc.)

Genera arquitecturas profesionales, realistas y alineadas al stack del cliente."""
    
    def _build_architecture_user_prompt(
        self,
        description: str,
        tech_profile: Dict[str, Any],
        requirements: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Construye el user prompt para generación de arquitecturas
        """
        req_text = ""
        if requirements:
            req_list = [f"- {k}: {v}" for k, v in requirements.items()]
            req_text = "\n".join(req_list)
        
        return f"""Diseña una arquitectura cloud para:

DESCRIPCIÓN:
{description}

REQUERIMIENTOS ADICIONALES:
{req_text if req_text else "No especificados"}

Por favor, proporciona:

1. COMPONENTES PRINCIPALES:
   - Lista los componentes/servicios principales
   - Especifica el cloud provider y servicio real (ej: AWS Lambda, Azure Functions)
   
2. ARQUITECTURA:
   - Describe cómo se conectan los componentes
   - Explica el flujo de datos
   
3. INFRAESTRUCTURA COMO CÓDIGO:
   - Proporciona un ejemplo básico en {tech_profile.get('standards', {}).get('infrastructure', 'terraform')}
   
4. CI/CD:
   - Proporciona un pipeline básico en {tech_profile.get('standards', {}).get('cicd', 'github-actions')}
   
5. ESTIMACIÓN DE COSTOS:
   - Proporciona una estimación mensual aproximada
   
6. RECOMENDACIONES:
   - Mejores prácticas
   - Consideraciones de seguridad
   - Optimizaciones

Responde en formato JSON estructurado."""
    
    def _parse_architecture_response(
        self,
        response: str,
        tech_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parsea la respuesta del LLM y la estructura
        """
        # Por ahora, retornamos una estructura básica
        # En producción, aquí parseariamos el JSON o extraeríamos información estructurada
        
        return {
            "components": self._extract_components(response),
            "architecture_description": response,
            "tech_profile": tech_profile,
            "infrastructure_code": self._extract_iac_code(response),
            "cicd_pipeline": self._extract_cicd(response),
            "estimated_cost": self._extract_cost(response),
            "recommendations": self._extract_recommendations(response),
            "raw_response": response
        }
    
    def _extract_components(self, response: str) -> List[Dict[str, Any]]:
        """Extrae componentes de la respuesta"""
        # Implementación simplificada
        return [
            {
                "name": "Component",
                "type": "service",
                "description": "Extracted from AI response"
            }
        ]
    
    def _extract_iac_code(self, response: str) -> Optional[str]:
        """Extrae código de infraestructura"""
        # Buscar bloques de código en la respuesta
        return None
    
    def _extract_cicd(self, response: str) -> Optional[str]:
        """Extrae pipeline de CI/CD"""
        return None
    
    def _extract_cost(self, response: str) -> Optional[Dict[str, Any]]:
        """Extrae estimación de costos"""
        return {
            "currency": "USD",
            "monthly_estimate": "TBD",
            "breakdown": []
        }
    
    def _extract_recommendations(self, response: str) -> List[str]:
        """Extrae recomendaciones"""
        return [
            "Review security configurations",
            "Implement monitoring and alerting",
            "Set up automated backups"
        ]
