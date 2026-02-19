from fastapi import APIRouter, HTTPException, status, Depends, Response
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.schemas import ArchitectureResponse, ArchitectureRequest, Client
from app.models.database import ClientModel, ArchitectureGenerationModel
from app.orchestrators.ai_orchestrator import AIOrchestrator
from app.core.database import get_db
from app.core.logging import logger

router = APIRouter()
ai_orchestrator = AIOrchestrator()

from pydantic import BaseModel
from datetime import datetime

class ArchitectureUpdate(BaseModel):
    name: str

@router.post("/generate", response_model=ArchitectureResponse)
async def generate_architecture(request: ArchitectureRequest, db: AsyncSession = Depends(get_db)):
    """
    Genera una arquitectura basada en requerimientos y la guarda en DB
    """
    # Verificar cliente en DB
    result = await db.execute(select(ClientModel).where(ClientModel.id == request.client_id))
    client_model = result.scalar_one_or_none()
    
    if not client_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {request.client_id} no encontrado"
        )
    
    # Convertir a esquema Pydantic
    client = Client(
        id=client_model.id,
        name=client_model.name,
        description=client_model.description,
        tech_profile=client_model.tech_profile,
        is_active=client_model.is_active,
        created_at=client_model.created_at,
        updated_at=client_model.updated_at
    )
    
    try:
        logger.info(f"Generando arquitectura para {client.name}")
        architecture_result = await ai_orchestrator.generate_architecture(client, request)
        
        # Guardar en DB
        arch_record = ArchitectureGenerationModel(
            client_id=client.id,
            name=f"Arquitectura {datetime.now().strftime('%Y%m%d_%H%M%S')}",
            description=request.description,
            requirements=request.requirements,
            architecture=architecture_result.architecture,
            infrastructure_code=architecture_result.infrastructure_code,
            estimated_cost=architecture_result.estimated_cost
        )
        db.add(arch_record)
        await db.commit()
        await db.refresh(arch_record)
        
        # Actualizar respuesta con ID de DB y nombre
        architecture_result.id = arch_record.id
        architecture_result.name = arch_record.name
        architecture_result.created_at = arch_record.created_at
        
        return architecture_result
        
    except Exception as e:
        logger.error(f"Error generando arquitectura: {e}")
        logger.exception("Stack trace:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/history/{client_id}", response_model=List[ArchitectureResponse])
async def get_architecture_history(client_id: str, db: AsyncSession = Depends(get_db)):
    """
    Obtiene el historial de arquitecturas de un cliente
    """
    result = await db.execute(
        select(ArchitectureGenerationModel)
        .where(ArchitectureGenerationModel.client_id == client_id)
        .order_by(ArchitectureGenerationModel.created_at.desc())
    )
    history = result.scalars().all()
    
    return [
        ArchitectureResponse(
            id=a.id,
            client_id=a.client_id,
            name=a.name,
            architecture=a.architecture,
            infrastructure_code=a.infrastructure_code,
            estimated_cost=a.estimated_cost,
            recommendations=[],
            created_at=a.created_at
        ) for a in history
    ]

@router.put("/{architecture_id}", response_model=ArchitectureResponse)
async def update_architecture(
    architecture_id: str, 
    update_data: ArchitectureUpdate, 
    db: AsyncSession = Depends(get_db)
):
    """
    Actualiza metadatos de una arquitectura (ej: nombre)
    """
    result = await db.execute(
        select(ArchitectureGenerationModel).where(ArchitectureGenerationModel.id == architecture_id)
    )
    arch = result.scalar_one_or_none()
    
    if not arch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquitectura no encontrada"
        )
    
    arch.name = update_data.name
    await db.commit()
    await db.refresh(arch)
    
    return ArchitectureResponse(
        id=arch.id,
        client_id=arch.client_id,
        name=arch.name,
        architecture=arch.architecture,
        infrastructure_code=arch.infrastructure_code,
        estimated_cost=arch.estimated_cost,
        recommendations=[],
        created_at=arch.created_at
    )


@router.delete("/{architecture_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_architecture(architecture_id: str, db: AsyncSession = Depends(get_db)):
    """
    Elimina una arquitectura guardada
    """
    result = await db.execute(
        select(ArchitectureGenerationModel).where(ArchitectureGenerationModel.id == architecture_id)
    )
    arch = result.scalar_one_or_none()

    if not arch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquitectura no encontrada"
        )

    await db.delete(arch)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post("/estimate-cost")
async def estimate_cost(request: ArchitectureRequest, db: AsyncSession = Depends(get_db)):
    """
    Estima el costo de una arquitectura sin generarla completamente
    """
    result = await db.execute(select(ClientModel).where(ClientModel.id == request.client_id))
    client_model = result.scalar_one_or_none()
    
    if not client_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {request.client_id} no encontrado"
        )
    
    client = Client(
        id=client_model.id,
        name=client_model.name,
        description=client_model.description,
        tech_profile=client_model.tech_profile,
        is_active=client_model.is_active,
        created_at=client_model.created_at,
        updated_at=client_model.updated_at
    )
    
    try:
        # Generar arquitectura básica para estimar
        architecture_response = await ai_orchestrator.generate_architecture(
            client=client,
            request=request
        )
        
        return {
            'client_id': request.client_id,
            'estimated_cost': architecture_response.estimated_cost
        }
        
    except Exception as e:
        logger.error(f"Error estimando costo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
