from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.database import CloudCredentialsModel, RepositoryCredentialsModel, CICDCredentialsModel
from app.core.config import settings
from typing import Any, Dict, Optional

class ConfigResolver:
    """
    Resuelve configuraciones dinámicamente, priorizando la BD sobre .env
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_cloud_credentials(self, client_id: str, provider: str) -> Dict[str, Any]:
        """Obtiene credenciales de nube para un cliente"""
        result = await self.db.execute(
            select(CloudCredentialsModel)
            .where(CloudCredentialsModel.client_id == client_id, CloudCredentialsModel.provider == provider)
        )
        creds = result.scalar_one_or_none()
        
        if creds:
            return creds.credentials
            
        # Fallback a variables de entorno si no hay en BD
        if provider == "azure":
            return {
                "client_id": settings.AZURE_CLIENT_ID,
                "client_secret": settings.AZURE_CLIENT_SECRET,
                "tenant_id": settings.AZURE_TENANT_ID,
                "subscription_id": settings.AZURE_SUBSCRIPTION_ID
            }
        elif provider == "aws":
            return {
                "access_key_id": settings.AWS_ACCESS_KEY_ID,
                "secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
                "session_token": settings.AWS_SESSION_TOKEN or None,
                "region": settings.AWS_DEFAULT_REGION
            }
        return {}

    async def get_repository_config(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene configuración completa del repositorio (URL + token)"""
        result = await self.db.execute(
            select(RepositoryCredentialsModel)
            .where(RepositoryCredentialsModel.client_id == client_id)
        )
        creds = result.scalar_one_or_none()
        
        if creds and creds.credentials:
            return {
                "provider": creds.provider,
                "url": creds.credentials.get("url") or creds.credentials.get("repository_url"),
                "token": creds.credentials.get("token"),
                "organization": creds.credentials.get("organization")
            }
        
        # Fallback a variables de entorno
        return {
            "provider": "github",
            "url": settings.GITHUB_REPO_URL if hasattr(settings, 'GITHUB_REPO_URL') else None,
            "token": settings.GITHUB_TOKEN if hasattr(settings, 'GITHUB_TOKEN') else None
        }

    async def get_repository_token(self, client_id: str, provider: str) -> Optional[str]:
        """Obtiene token de repositorio (GitHub/GitLab)"""
        result = await self.db.execute(
            select(RepositoryCredentialsModel)
            .where(RepositoryCredentialsModel.client_id == client_id, RepositoryCredentialsModel.provider == provider)
        )
        creds = result.scalar_one_or_none()
        
        if creds and "token" in creds.credentials:
            return creds.credentials["token"]
            
        # Fallback
        if provider == "github": return settings.GITHUB_TOKEN if hasattr(settings, 'GITHUB_TOKEN') else None
        if provider == "gitlab": return settings.GITLAB_TOKEN if hasattr(settings, 'GITLAB_TOKEN') else None
        return None
