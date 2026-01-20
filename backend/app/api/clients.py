"""
API endpoints para gestión de clientes
"""
from fastapi import APIRouter, HTTPException, status
from typing import List
from app.models.schemas import Client, ClientCreate, ClientUpdate
from app.orchestrators.iaops_orchestrator import orchestrator
from app.core.logging import logger
import uuid

router = APIRouter()

# Storage temporal (en producción usar base de datos)
clients_db: dict = {}


@router.post("/", response_model=Client, status_code=status.HTTP_201_CREATED)
async def create_client(client_data: ClientCreate):
    """
    Crea un nuevo cliente con su perfil tecnológico
    """
    try:
        from datetime import datetime
        
        client_id = str(uuid.uuid4())
        
        client = Client(
            id=client_id,
            **client_data.model_dump(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Guardar en storage
        clients_db[client_id] = client
        
        logger.info(f"Cliente creado: {client_id} - {client.name}")
        
        return client
        
    except Exception as e:
        logger.error(f"Error creando cliente: {e}")
        logger.exception("Stack trace:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/", response_model=List[Client])
async def list_clients():
    """
    Lista todos los clientes
    """
    return list(clients_db.values())


@router.get("/{client_id}", response_model=Client)
async def get_client(client_id: str):
    """
    Obtiene un cliente por ID
    """
    if client_id not in clients_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {client_id} no encontrado"
        )
    
    return clients_db[client_id]


@router.put("/{client_id}", response_model=Client)
async def update_client(client_id: str, client_update: ClientUpdate):
    """
    Actualiza un cliente
    """
    if client_id not in clients_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {client_id} no encontrado"
        )
    
    client = clients_db[client_id]
    
    # Actualizar campos
    update_data = client_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)
    
    logger.info(f"Cliente actualizado: {client_id}")
    
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(client_id: str):
    """
    Elimina un cliente
    """
    if client_id not in clients_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {client_id} no encontrado"
        )
    
    del clients_db[client_id]
    logger.info(f"Cliente eliminado: {client_id}")


@router.post("/{client_id}/validate")
async def validate_client_profile(client_id: str):
    """
    Valida el perfil tecnológico del cliente
    
    Verifica que las credenciales de clouds y repositorios sean válidas
    """
    if client_id not in clients_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {client_id} no encontrado"
        )
    
    client = clients_db[client_id]
    
    try:
        validation_report = await orchestrator.validate_tech_profile(client)
        return validation_report
        
    except Exception as e:
        logger.error(f"Error validando perfil: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
