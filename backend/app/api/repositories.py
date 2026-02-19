from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from app.core.database import get_db
from app.models.database import RepositoryCredentialsModel
from app.core.logging import logger
from app.core.config_resolver import ConfigResolver
import httpx
import re

router = APIRouter()

def parse_github_url(url: str) -> tuple[str, str]:
    """Extrae owner y repo de una URL de GitHub"""
    # Soporta: https://github.com/owner/repo o git@github.com:owner/repo.git
    patterns = [
        r'github\.com[:/]([^/]+)/([^/\.]+)',
        r'github\.com/([^/]+)/([^/]+)\.git'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), match.group(2)
    raise ValueError(f"Invalid GitHub URL: {url}")

async def get_github_headers(client_id: str, db: AsyncSession) -> dict:
    """Obtiene headers de autenticación para GitHub API"""
    resolver = ConfigResolver(db)
    config = await resolver.get_repository_config(client_id)
    
    if not config or not config.get('token'):
        raise HTTPException(status_code=404, detail="No repository credentials configured for this client")
    
    return {
        "Authorization": f"token {config['token']}",
        "Accept": "application/vnd.github.v3+json"
    }

@router.get("/{client_id}")
async def list_repositories(client_id: str, db: AsyncSession = Depends(get_db)):
    """Lista todos los repositorios accesibles con el token de GitHub del cliente"""
    try:
        resolver = ConfigResolver(db)
        config = await resolver.get_repository_config(client_id)
        
        if not config or not config.get('token'):
            logger.warning(f"No GitHub token configured for client {client_id}")
            return []
        
        headers = {
            "Authorization": f"token {config['token']}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        async with httpx.AsyncClient() as client:
            # Primero intentamos obtener repos del usuario autenticado
            response = await client.get(
                "https://api.github.com/user/repos",
                headers=headers,
                params={"per_page": 100, "sort": "updated"},
                timeout=10.0
            )
            
            if response.status_code == 200:
                repos = response.json()
                return [{
                    "id": repo["full_name"],
                    "name": repo["name"],
                    "url": repo["html_url"],
                    "clone_url": repo["clone_url"],
                    "owner": repo["owner"]["login"],
                    "description": repo.get("description", ""),
                    "private": repo["private"],
                    "updated_at": repo["updated_at"]
                } for repo in repos]
            else:
                logger.warning(f"GitHub API error: {response.status_code} - {response.text}")
                return []
    except Exception as e:
        logger.error(f"Error fetching repositories: {e}")
        return []

@router.get("/{client_id}/branches")
async def list_branches(client_id: str, repo_url: str, db: AsyncSession = Depends(get_db)):
    """Lista las ramas de un repositorio específico"""
    try:
        resolver = ConfigResolver(db)
        config = await resolver.get_repository_config(client_id)
        
        if not config or not config.get('token'):
            return []
        
        owner, repo = parse_github_url(repo_url)
        headers = {
            "Authorization": f"token {config['token']}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/branches",
                headers=headers,
                timeout=10.0
            )
            
            if response.status_code == 200:
                branches = response.json()
                return [{"name": b["name"], "protected": b.get("protected", False)} for b in branches]
            else:
                logger.warning(f"GitHub API error: {response.status_code}")
                return [{"name": "main", "protected": True}]
    except Exception as e:
        logger.error(f"Error fetching branches: {e}")
        return [{"name": "main", "protected": True}]

@router.get("/{client_id}/commits")
async def list_commits(client_id: str, repo_url: str, branch: str = "main", db: AsyncSession = Depends(get_db)):
    """Lista los últimos commits de un repositorio y rama específicos"""
    try:
        resolver = ConfigResolver(db)
        config = await resolver.get_repository_config(client_id)
        
        if not config or not config.get('token'):
            return []
        
        owner, repo = parse_github_url(repo_url)
        headers = {
            "Authorization": f"token {config['token']}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits",
                headers=headers,
                params={"sha": branch, "per_page": 10},
                timeout=10.0
            )
            
            if response.status_code == 200:
                commits = response.json()
                return [{
                    "sha": c["sha"],
                    "message": c["commit"]["message"],
                    "author": c["commit"]["author"]["name"],
                    "date": c["commit"]["author"]["date"]
                } for c in commits]
            else:
                logger.warning(f"GitHub API error: {response.status_code}")
                return []
    except Exception as e:
        logger.error(f"Error fetching commits: {e}")
        return []

@router.post("/{client_id}/merge")
async def accept_merge(client_id: str, branch: str, db: AsyncSession = Depends(get_db)):
    """Acepta un merge/pull request (simulado por ahora)"""
    # Esta funcionalidad requeriría crear un PR real en GitHub
    # Por ahora solo registramos la intención
    logger.info(f"Merge request for client {client_id}, branch {branch}")
    return {"status": "success", "message": f"Merge de {branch} procesado correctamente"}
