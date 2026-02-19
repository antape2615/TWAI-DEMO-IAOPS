from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.models.schemas import Client, ClientCreate, ClientUpdate
from app.models.database import ClientModel
from app.core.database import get_db
from app.core.logging import logger
import uuid

router = APIRouter()

@router.post("/", response_model=Client, status_code=status.HTTP_201_CREATED)
async def create_client(client_data: ClientCreate, db: AsyncSession = Depends(get_db)):
    """
    Crea un nuevo cliente con su perfil tecnológico en PostgreSQL
    """
    try:
        new_client = ClientModel(
            id=str(uuid.uuid4()),
            name=client_data.name,
            description=client_data.description,
            tech_profile=client_data.tech_profile.model_dump(),
            is_active=True
        )
        
        db.add(new_client)
        await db.commit()
        await db.refresh(new_client)
        
        logger.info(f"Cliente creado en DB: {new_client.id} - {new_client.name}")
        
        return Client(
            id=new_client.id,
            name=new_client.name,
            description=new_client.description,
            tech_profile=new_client.tech_profile,
            is_active=new_client.is_active,
            created_at=new_client.created_at,
            updated_at=new_client.updated_at
        )
        
    except Exception as e:
        logger.error(f"Error creando cliente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/", response_model=List[Client])
async def list_clients(db: AsyncSession = Depends(get_db)):
    """
    Lista todos los clientes desde PostgreSQL
    """
    result = await db.execute(select(ClientModel).order_by(ClientModel.created_at.desc()))
    clients = result.scalars().all()
    return [
        Client(
            id=c.id,
            name=c.name,
            description=c.description,
            tech_profile=c.tech_profile,
            is_active=c.is_active,
            created_at=c.created_at,
            updated_at=c.updated_at
        ) for c in clients
    ]

@router.get("/{client_id}", response_model=Client)
async def get_client(client_id: str, db: AsyncSession = Depends(get_db)):
    """
    Obtiene un cliente por ID desde PostgreSQL
    """
    result = await db.execute(select(ClientModel).where(ClientModel.id == client_id))
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {client_id} no encontrado"
        )
    
    return Client(
        id=client.id,
        name=client.name,
        description=client.description,
        tech_profile=client.tech_profile,
        is_active=client.is_active,
        created_at=client.created_at,
        updated_at=client.updated_at
    )

@router.put("/{client_id}", response_model=Client)
async def update_client(client_id: str, client_update: ClientUpdate, db: AsyncSession = Depends(get_db)):
    """
    Actualiza un cliente en PostgreSQL
    """
    result = await db.execute(select(ClientModel).where(ClientModel.id == client_id))
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {client_id} no encontrado"
        )
    
    update_data = client_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == 'tech_profile':
            setattr(client, field, value.model_dump() if hasattr(value, 'model_dump') else value)
        else:
            setattr(client, field, value)
    
    logger.info(f"Cliente actualizado en DB: {client_id}")
    
    return Client(
        id=client.id,
        name=client.name,
        description=client.description,
        tech_profile=client.tech_profile,
        is_active=client.is_active,
        created_at=client.created_at,
        updated_at=client.updated_at
    )

@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(client_id: str, db: AsyncSession = Depends(get_db)):
    """
    Elimina un cliente de PostgreSQL
    """
    result = await db.execute(delete(ClientModel).where(ClientModel.id == client_id))
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {client_id} no encontrado"
        )
    
    await db.commit()
    logger.info(f"Cliente eliminado de DB: {client_id}")
    return None

@router.post("/{client_id}/validate")
async def validate_client_profile(client_id: str, db: AsyncSession = Depends(get_db)):
    """
    Valida el perfil tecnológico del cliente desde PostgreSQL
    """
    from app.orchestrators.iaops_orchestrator import orchestrator
    
    result = await db.execute(select(ClientModel).where(ClientModel.id == client_id))
    client_model = result.scalar_one_or_none()
    
    if not client_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {client_id} no encontrado"
        )
    
    # Convertir a esquema Pydantic para el orquestador
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
        validation_report = await orchestrator.validate_tech_profile(client)
        return validation_report
        
    except Exception as e:
        logger.error(f"Error validando perfil: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
