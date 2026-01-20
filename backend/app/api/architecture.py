"""
API endpoints para generación de arquitecturas con IA
"""
from fastapi import APIRouter, HTTPException, status
from app.models.schemas import ArchitectureRequest, ArchitectureResponse
from app.orchestrators.ai_orchestrator import ai_orchestrator
from app.api.clients import clients_db
from app.core.logging import logger

router = APIRouter()


@router.post("/generate", response_model=ArchitectureResponse)
async def generate_architecture(request: ArchitectureRequest):
    """
    Genera una arquitectura usando IA respetando el tech profile del cliente
    
    La IA NO inventa tecnología, sino que:
    - Respeta el stack real del cliente
    - Diseña arquitecturas alineadas a las nubes que el cliente ya usa (AWS/Azure/GCP)
    - Usa solo servicios permitidos por el cliente
    - Genera código de infraestructura según los estándares del cliente
    """
    # Verificar que el cliente existe
    if request.client_id not in clients_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {request.client_id} no encontrado"
        )
    
    client = clients_db[request.client_id]
    
    try:
        logger.info(f"Generando arquitectura para cliente {client.name}")
        
        # Generar arquitectura con IA
        architecture_data = await ai_orchestrator.generate_architecture(
            client=client,
            request=request
        )
        
        # Construir respuesta estructurada
        response = ArchitectureResponse(
            client_id=request.client_id,
            architecture=architecture_data.get('architecture', {}),
            infrastructure_code=architecture_data.get('infrastructure_code'),
            diagram=architecture_data.get('diagram'),
            estimated_cost=architecture_data.get('estimated_cost'),
            recommendations=architecture_data.get('recommendations', [])
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error generando arquitectura: {e}")
        logger.exception("Stack trace:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando arquitectura: {str(e)}"
        )


@router.post("/estimate-cost")
async def estimate_cost(request: ArchitectureRequest):
    """
    Estima el costo de una arquitectura sin generarla completamente
    """
    if request.client_id not in clients_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {request.client_id} no encontrado"
        )
    
    client = clients_db[request.client_id]
    
    try:
        # Generar arquitectura básica para estimar
        architecture_response = await ai_orchestrator.generate_architecture(
            client=client,
            request=request
        )
        
        return {
            'client_id': request.client_id,
            'estimated_cost': architecture_response['estimated_cost']
        }
        
    except Exception as e:
        logger.error(f"Error estimando costo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
