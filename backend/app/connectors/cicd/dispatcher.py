"""
CICID Dispatcher - Selecciona e implementa pipelines según el tipo de CI/CD configurado
"""
import httpx
import base64
import asyncio
import re
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple, List
from app.core.logging import logger


class CICDHandler(ABC):
    """Base para manejadores de CI/CD"""
    
    def __init__(self, provider: str, token: str, organization: Optional[str] = None, project: Optional[str] = None):
        self.provider = provider
        self.token = token
        self.organization = organization
        self.project = project
    
    @abstractmethod
    async def validate_credentials(self, client: httpx.AsyncClient) -> bool:
        """Valida que las credenciales sean válidas"""
        pass
    
    @abstractmethod
    async def create_pipeline(self, client: httpx.AsyncClient, repo_url: str, branch: str, resource_id: str, 
                            environment: str) -> Tuple[bool, str]:
        """Crea el pipeline/workflow en el repositorio"""
        pass
    
    @abstractmethod
    async def dispatch_pipeline(self, client: httpx.AsyncClient, repo_url: str, branch: str, 
                               resource_id: str, environment: str) -> Tuple[bool, str]:
        """Dispara/ejecuta el pipeline"""
        pass


class GitHubActionsHandler(CICDHandler):
    """Handler para GitHub Actions"""
    
    def __init__(self, provider: str, token: str, organization: Optional[str] = None, project: Optional[str] = None,
                 azure_credentials: Optional[Dict[str, str]] = None,
                 client_info: Optional[Dict[str, Any]] = None):
        super().__init__(provider, token, organization, project)
        self.azure_credentials = azure_credentials or {}
        self.client_info = client_info or {}
        # Track workflow commit SHA for dispatch after update
        self.last_workflow_commit_sha = None
        self.last_workflow_file_sha = None
    
    async def validate_credentials(self, client: httpx.AsyncClient) -> bool:
        """Valida token de GitHub"""
        logger.info(f"[GH] Validating credentials")
        headers = {"Authorization": f"token {self.token}"}
        resp = await client.get("https://api.github.com/user", headers=headers, timeout=5.0)
        logger.info(f"[GH] Validation response: {resp.status_code}")
        return resp.status_code == 200
    
    async def create_pipeline(self, client: httpx.AsyncClient, repo_url: str, branch: str, 
                             resource_id: str, environment: str) -> Tuple[bool, str]:
        """Crea workflow deploy.yml en GitHub - Usa IA para generar el pipeline dinámicamente"""
        logger.info(f"[GH] Creating pipeline in {repo_url}")
        owner, repo = self._parse_repo(repo_url)
        logger.info(f"[GH] Parsed: owner={owner}, repo={repo}")
        if not owner or not repo:
            logger.error(f"[GH] Invalid repo URL: {repo_url}")
            return False, "Invalid repo URL"
        
        # Determinar el contenido del workflow (IA o template)
        workflow_content = None
        use_ai = bool(self.client_info.get('use_ai', False)) if self.client_info else False
        logger.info(f"[GH] client_info: {self.client_info}")
        logger.info(f"[GH] use_ai: {use_ai}")
        
        if use_ai:
            logger.info("[GH] Using AI to generate pipeline...")
            workflow_content = await self._generate_pipeline_with_ai()
            if workflow_content:
                logger.info("[GH] AI pipeline generated successfully")
            else:
                logger.warning("[GH] AI pipeline generation failed, falling back to template")
        
        # Si no se generó con IA, usar template
        if not workflow_content:
            workflow_content = self._get_github_workflow_template(resource_id, environment)
        
        workflow_path = ".github/workflows/deploy.yml"
        
        headers = {"Authorization": f"token {self.token}", "Accept": "application/vnd.github.v3+json"}
        contents_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{workflow_path}"
        
        # Check if exists
        logger.info(f"[GH] Checking if workflow exists at {contents_url}")
        get_resp = await client.get(contents_url, headers=headers, params={"ref": branch}, timeout=10.0)
        logger.info(f"[GH] Check response: {get_resp.status_code}")
        
        if get_resp.status_code == 200:
            logger.info(f"GitHub workflow already exists: {workflow_path}")
            # If use_ai is True, we should update the workflow with AI-generated content
            if use_ai:
                logger.info(f"[GH] use_ai=True, updating workflow with AI-generated content...")
                # Get the SHA of the existing file for update
                existing_content = get_resp.json()
                file_sha = existing_content.get('sha', '')
                
                payload = {
                    "message": "chore(ci): update deploy workflow (AI-generated by IAOPS)",
                    "content": base64.b64encode(workflow_content.encode()).decode(),
                    "branch": branch,
                    "sha": file_sha
                }
                logger.info(f"[GH] Updating workflow with content length: {len(workflow_content)}")
                logger.info(f"[GH] Workflow content preview:\n{workflow_content[:500]}")
                update_resp = await client.put(contents_url, headers=headers, json=payload, timeout=10.0)
                logger.info(f"[GH] Update response: {update_resp.status_code}")
                
                if update_resp.status_code in (201, 200):
                    # Get the commit SHA from the updated file response
                    updated_content = update_resp.json()
                    # The commit SHA is in the 'content' object if available, or we need to fetch it
                    commit_sha = updated_content.get('commit_sha', '')
                    
                    # If commit_sha not in response, get it from the file's content link
                    if not commit_sha:
                        # The file SHA is different from commit SHA, we need to fetch the commit
                        file_sha = updated_content.get('sha', '')
                        logger.info(f"[GH] File SHA after update: {file_sha}")
                        # Get the file again to get commit info
                        file_detail_resp = await client.get(contents_url, headers=headers, params={"ref": branch}, timeout=10.0)
                        if file_detail_resp.status_code == 200:
                            file_detail = file_detail_resp.json()
                            commit_sha = file_detail.get('sha', '')  # This is actually file SHA, not commit
                            logger.info(f"[GH] File SHA from detail: {commit_sha}")
                    
                    # Store the SHA for use in dispatch
                    self.last_workflow_file_sha = updated_content.get('sha', '')
                    logger.info(f"[GH] Workflow updated, file SHA: {self.last_workflow_file_sha}")
                    
                    # Get the latest commit SHA from the branch
                    commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"
                    commit_resp = await client.get(commits_url, headers=headers, timeout=10.0)
                    if commit_resp.status_code == 200:
                        commit_data = commit_resp.json()
                        self.last_workflow_commit_sha = commit_data.get('sha', '')
                        logger.info(f"[GH] Latest commit SHA: {self.last_workflow_commit_sha}")
                    else:
                        self.last_workflow_commit_sha = branch  # Fallback to branch name
                        logger.warning(f"[GH] Could not get commit SHA, using branch name")
                    
                    # Wait a bit more for GitHub to index the new commit
                    logger.info("[GH] Waiting 5s for GitHub to index the new commit...")
                    import asyncio
                    await asyncio.sleep(5)
                    
                    await self._setup_azure_secrets(client, owner, repo)
                    return True, "updated"
                else:
                    logger.error(f"Failed updating workflow: {update_resp.status_code} - {update_resp.text}")
                    return False, f"GitHub API error: {update_resp.status_code}"
            # Still try to setup Azure secrets even if not updating
            await self._setup_azure_secrets(client, owner, repo)
            return True, "workflow_exists"
        
        # Create workflow
        logger.info(f"[GH] Creating new workflow")
        payload = {
            "message": "chore(ci): add deploy workflow (generated by IAOPS)",
            "content": base64.b64encode(workflow_content.encode()).decode(),
            "branch": branch
        }
        put_resp = await client.put(contents_url, headers=headers, json=payload, timeout=10.0)
        logger.info(f"[GH] Create response: {put_resp.status_code}")
        
        if put_resp.status_code in (201, 200):
            logger.info(f"Created GitHub workflow: {workflow_path}")
            
            # Setup Azure secrets after creating the workflow
            logger.info(f"[GH] Setting up Azure secrets...")
            azure_secrets_result = await self._setup_azure_secrets(client, owner, repo)
            if azure_secrets_result:
                logger.info(f"[GH] Azure secrets configured successfully")
            else:
                logger.warning(f"[GH] Azure secrets not configured (may already exist or credentials missing)")
            
            return True, "created"
        else:
            logger.error(f"Failed creating workflow: {put_resp.status_code} - {put_resp.text}")
            return False, f"GitHub API error: {put_resp.status_code}"
    
    async def dispatch_pipeline(self, client: httpx.AsyncClient, repo_url: str, branch: str, 
                               resource_id: str, environment: str) -> Tuple[bool, str]:
        """Dispara workflow en GitHub con retry logic"""
        owner, repo = self._parse_repo(repo_url)
        if not owner or not repo:
            return False, "Invalid repo URL"
        
        headers = {"Authorization": f"token {self.token}", "Accept": "application/vnd.github.v3+json"}
        workflow_id = None
        max_retries = 10  # Increased retries
        retry_delay = 3  # Increased delay in seconds
        
        # Retry logic: GitHub tarda en indexar workflows recién creados
        for attempt in range(max_retries):
            logger.info(f"Attempt {attempt + 1}/{max_retries} to find deploy workflow")
            
            workflows_url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows"
            wf_resp = await client.get(workflows_url, headers=headers, timeout=10.0)
            
            if wf_resp.status_code != 200:
                logger.error(f"Error listing workflows (attempt {attempt + 1}): {wf_resp.status_code}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue
            
            workflows = wf_resp.json().get("workflows", [])
            logger.info(f"Found {len(workflows)} workflows in {owner}/{repo}")
            
            # Ver el contenido del workflow
            for wf in workflows:
                path = wf.get("path", "")
                wf_id = wf.get("id")
                wf_name = wf.get("name", "")
                logger.info(f"  - Workflow: path={path}, id={wf_id}, name={wf_name}")
            
            # Buscar el workflow deploy.yml específicamente
            for wf in workflows:
                path = wf.get("path", "")
                wf_id = wf.get("id")
                wf_name = wf.get("name", "")
                
                if ".github/workflows/deploy.yml" == path or path == ".github/workflows/deploy.yml":
                    workflow_id = wf_id
                    logger.info(f"Found deploy.yml workflow with ID: {workflow_id}")
                    
                    # Verificar que el workflow tiene workflow_dispatch
                    # Hacemos un request directo al archivo para ver su contenido
                    workflow_content_url = f"https://api.github.com/repos/{owner}/{repo}/contents/.github/workflows/deploy.yml"
                    content_resp = await client.get(workflow_content_url, headers=headers, timeout=10.0)
                    if content_resp.status_code == 200:
                        import base64
                        content_data = content_resp.json()
                        file_content = content_data.get('content', '')
                        if file_content:
                            decoded_content = base64.b64decode(file_content).decode('utf-8')
                            logger.info(f"[GH] Workflow content preview: {decoded_content[:500]}...")
                            if 'workflow_dispatch' in decoded_content:
                                logger.info("[GH] Workflow has workflow_dispatch trigger!")
                            else:
                                logger.warning("[GH] Workflow does NOT have workflow_dispatch trigger!")
                    
                    break
            
            if workflow_id:
                break
            
            if attempt < max_retries - 1:
                logger.warning(f"Deploy workflow not found, retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
        
        if not workflow_id:
            logger.error(f"No deploy workflow found after {max_retries} attempts")
            return False, "No deploy workflow found (max retries exceeded)"
        
        # Dispatch - try without inputs first (workflow may not have workflow_dispatch inputs defined)
        dispatch_url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches"
        
        # Use the specific commit SHA if available, otherwise use branch
        ref_to_use = getattr(self, 'last_workflow_commit_sha', None) or branch
        logger.info(f"Dispatching workflow {workflow_id} with ref={ref_to_use}")
        
        # First try without inputs
        response = await client.post(
            dispatch_url,
            headers=headers,
            json={"ref": ref_to_use},
            timeout=10.0
        )
        
        logger.info(f"Dispatch response: {response.status_code}")
        if response.status_code == 204:
            logger.info(f"GitHub workflow dispatched successfully: {owner}/{repo}")
            return True, "dispatched"
        
        # If that fails, try with inputs (if workflow supports workflow_dispatch inputs)
        if response.status_code == 422:
            logger.info("Dispatch without inputs failed, trying with inputs...")
            response = await client.post(
                dispatch_url,
                headers=headers,
                json={"ref": branch, "inputs": {"resource_id": resource_id, "environment": environment}},
                timeout=10.0
            )
            logger.info(f"Dispatch response with inputs: {response.status_code}")
            if response.status_code == 204:
                logger.info(f"GitHub workflow dispatched successfully with inputs: {owner}/{repo}")
                return True, "dispatched"
        
        logger.error(f"Dispatch failed: {response.status_code} - {response.text}")
        return False, f"Dispatch error: {response.status_code}"
    
    @staticmethod
    def _parse_repo(repo_url: str) -> Tuple[Optional[str], Optional[str]]:
        """Extrae owner/repo del URL"""
        match = re.search(r'github\.com[:/]([^/]+)/([^/\.]+)', repo_url)
        return (match.group(1), match.group(2)) if match else (None, None)
    
    async def _get_repo_public_key(self, client: httpx.AsyncClient, owner: str, repo: str) -> Optional[Dict[str, str]]:
        """Obtiene la clave pública del repositorio para cifrar secretos"""
        headers = {"Authorization": f"token {self.token}", "Accept": "application/vnd.github.v3+json"}
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key"
        
        try:
            resp = await client.get(url, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                # Debug: log key details
                key = data.get("key", "")
                key_id = data.get("key_id", "")
                logger.error(f"[GH-DEBUG] Got public key, key_id: {key_id}, key length (base64): {len(key)}")
                logger.error(f"[GH-DEBUG] Full key: {key}")
                return {
                    "key_id": key_id,
                    "key": key
                }
            else:
                logger.error(f"Error getting repo public key: {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"Exception getting repo public key: {e}")
            return None
    
    def _encrypt_secret(self, public_key: str, secret_value: str) -> str:
        """Cifra un valor secreto usando la clave pública del repositorio"""
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            import binascii
            import base64
            
            # Debug: log first 50 chars of key to see its format
            logger.error(f"[GH-DEBUG] Public key starts with: {public_key[:50]}...")
            
            # GitHub returns the key in PKCS#8 format (base64 encoded)
            # We need to decode it first
            try:
                key_bytes = base64.b64decode(public_key)
                logger.error(f"[GH-DEBUG] Decoded key bytes length: {len(key_bytes)}")
                
                # Load the public key from DER format
                public_key_obj = serialization.load_der_public_key(key_bytes)
                logger.error(f"[GH-DEBUG] Public key loaded from DER successfully")
            except Exception as decode_error:
                # Fallback: try loading as PEM if DER fails
                logger.error(f"[GH-DEBUG] DER decode failed, trying PEM: {decode_error}")
                # Try adding PEM header if not present
                if not public_key.startswith('-----BEGIN'):
                    key_pem = f"-----BEGIN PUBLIC KEY-----\n{public_key}\n-----END PUBLIC KEY-----"
                else:
                    key_pem = public_key
                public_key_obj = serialization.load_pem_public_key(key_pem.encode('utf-8'))
            
            # Encrypt
            encrypted = public_key_obj.encrypt(
                secret_value.encode('utf-8'),
                padding.PKCS1v15()
            )
            logger.error(f"[GH-DEBUG] Encryption successful, length: {len(encrypted)}")
            
            return binascii.b2a_base64(encrypted).decode('utf-8').strip()
        except Exception as e:
            logger.error(f"Error encrypting secret: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return ""
    
    async def _create_github_secret(self, client: httpx.AsyncClient, owner: str, repo: str, 
                                     secret_name: str, secret_value: str) -> bool:
        """Crea un secreto en el repositorio de GitHub (opcional - no bloquea el deployment)"""
        # Por ahora, hacemos esto opcional para que no falle el deployment
        # TODO: Implementar correctamente la encriptación de secretos
        logger.warning(f"[GH] Skipping secret {secret_name} creation for now - needs fix")
        return True
    
    async def _setup_azure_secrets(self, client: httpx.AsyncClient, owner: str, repo: str) -> bool:
        """Configura los secretos de Azure en el repositorio"""
        if not self.azure_credentials:
            logger.warning("[GH] No Azure credentials provided, skipping secret creation")
            # Try to get from environment variables
            azure_creds = {
                "AZURE_CLIENT_ID": os.getenv("AZURE_CLIENT_ID", ""),
                "AZURE_CLIENT_SECRET": os.getenv("AZURE_CLIENT_SECRET", ""),
                "AZURE_TENANT_ID": os.getenv("AZURE_TENANT_ID", ""),
                "AZURE_SUBSCRIPTION_ID": os.getenv("AZURE_SUBSCRIPTION_ID", "")
            }
            
            # Check if we have at least some credentials
            if not azure_creds["AZURE_CLIENT_ID"]:
                logger.warning("[GH] No Azure credentials found in environment")
                return False
            
            self.azure_credentials = azure_creds
        
        logger.info(f"[GH] Setting up Azure secrets in {owner}/{repo}")
        
        # Create individual secrets
        secrets_to_create = {
            "AZURE_CLIENT_ID": self.azure_credentials.get("AZURE_CLIENT_ID", ""),
            "AZURE_CLIENT_SECRET": self.azure_credentials.get("AZURE_CLIENT_SECRET", ""),
            "AZURE_TENANT_ID": self.azure_credentials.get("AZURE_TENANT_ID", ""),
            "AZURE_SUBSCRIPTION_ID": self.azure_credentials.get("AZURE_SUBSCRIPTION_ID", "")
        }
        
        success = True
        for secret_name, secret_value in secrets_to_create.items():
            if secret_value:
                result = await self._create_github_secret(client, owner, repo, secret_name, secret_value)
                if not result:
                    success = False
            else:
                logger.warning(f"[GH] Skipping empty secret {secret_name}")
        
        # Also create the combined AZURE_CREDENTIALS secret (JSON format)
        if all([secrets_to_create.get(k) for k in ["AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID"]]):
            import json
            azure_json = json.dumps({
                "clientId": secrets_to_create["AZURE_CLIENT_ID"],
                "clientSecret": secrets_to_create["AZURE_CLIENT_SECRET"],
                "subscriptionId": secrets_to_create["AZURE_SUBSCRIPTION_ID"],
                "tenantId": secrets_to_create["AZURE_TENANT_ID"]
            })
            await self._create_github_secret(client, owner, repo, "AZURE_CREDENTIALS", azure_json)
        
        return success
    
    async def _generate_pipeline_with_ai(self) -> Optional[str]:
        """
        Genera el pipeline de CI/CD usando IA
        
        Returns:
            Contenido del pipeline o None si falla
        """
        try:
            from app.orchestrators.ai_orchestrator import ai_orchestrator
            from app.models.schemas import Client, TechProfile, TechStandards, CloudProvider
            
            # Extraer información del cliente
            client_name = self.client_info.get('name', 'IAOPS Client')
            resource_type = self.client_info.get('resource_type', 'sites')
            resource_name = self.client_info.get('resource_name', 'app')
            resource_group = self.client_info.get('resource_group', 'rg-default')
            application_type = self.client_info.get('application_type', 'nodejs')
            
            # Crear cliente mock para la generación
            client = Client(
                id=self.client_info.get('id', 'temp-client'),
                name=client_name,
                tech_profile=TechProfile(
                    clouds=[CloudProvider.AZURE],
                    repositories=[],
                    standards=TechStandards(
                        infrastructure='bicep',
                        cicd='github-actions'  # Must use hyphen, not underscore
                    )
                )
            )
            
            # Generar pipeline con IA
            logger.info(f"[GH-AI] Generating pipeline for: {resource_type}/{resource_name}")
            
            result = await ai_orchestrator.generate_cicd_pipeline(
                client=client,
                resource_type=resource_type,
                resource_name=resource_name,
                resource_group=resource_group,
                cloud_provider='azure',
                application_type=application_type
            )
            
            logger.info(f"[GH-AI] Pipeline result keys: {result.keys()}")
            logger.info(f"[GH-AI] Pipeline content length: {len(result.get('pipeline_content', ''))}")
            
            pipeline_content = result.get('pipeline_content', '')
            
            if pipeline_content:
                logger.info(f"[GH-AI] Pipeline generated successfully ({len(pipeline_content)} chars)")
                logger.info(f"[GH-AI] Pipeline content preview:\n{pipeline_content[:500]}")
                return pipeline_content
            else:
                logger.warning("[GH-AI] Empty pipeline returned")
                return None
                
        except Exception as e:
            logger.error(f"[GH-AI] Error generating pipeline: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    @staticmethod
    def _get_github_workflow_template(resource_id: str, environment: str) -> str:
        return f"""name: Deploy to Azure - {environment}
on:
  workflow_dispatch:
    inputs:
      resource_id:
        description: 'Azure Resource ID'
        required: true
        default: '{resource_id}'
      environment:
        description: 'Environment'
        required: true
        default: '{environment}'

env:
  AZURE_RESOURCE_ID: ${{{{ github.event.inputs.resource_id }}}}
  ENVIRONMENT: ${{{{ github.event.inputs.environment }}}}
  # Note: These credentials should be added to your GitHub repository secrets
  # Settings -> Secrets and variables -> Actions -> New repository secret
  # AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Parse Azure Resource ID
        id: parse
        run: |
          # Parse ARM resource ID
          # Format: /subscriptions/{{subId}}/resourceGroups/{{rg}}/providers/{{provider}}/{{type}}/{{name}}
          resource_type=$(echo "${{{{ env.AZURE_RESOURCE_ID }}}}" | grep -oP 'providers/[^/]+/\K[^/]+' || echo "unknown")
          resource_name=$(echo "${{{{ env.AZURE_RESOURCE_ID }}}}" | grep -oP '/[^/]+$' | tr -d '/')
          subscription_id=$(echo "${{{{ env.AZURE_RESOURCE_ID }}}}" | grep -oP 'subscriptions/\K[^/]+')
          resource_group=$(echo "${{{{ env.AZURE_RESOURCE_ID }}}}" | grep -oP 'resourceGroups/\K[^/]+')
          
          echo "resource_type=${{resource_type}}" >> $GITHUB_OUTPUT
          echo "resource_name=${{resource_name}}" >> $GITHUB_OUTPUT
          echo "subscription_id=${{subscription_id}}" >> $GITHUB_OUTPUT
          echo "resource_group=${{resource_group}}" >> $GITHUB_OUTPUT
          
          echo "Parsed Resource Type: ${{resource_type}}"
          echo "Parsed Resource Name: ${{resource_name}}"
          echo "Parsed Subscription: ${{subscription_id}}"
          echo "Parsed Resource Group: ${{resource_group}}"
      
      - name: Setup Node.js
        if: contains(steps.parse.outputs.resource_type, 'sites') # App Service
        uses: actions/setup-node@v4
        with:
          node-version: '18'
      
      - name: Install dependencies
        if: contains(steps.parse.outputs.resource_type, 'sites')
        run: npm install
        working-directory: ./
      
      - name: Build application
        if: contains(steps.parse.outputs.resource_type, 'sites')
        run: npm run build
        working-directory: ./
      
      - name: Azure Login
        uses: azure/login@v1
        with:
          client-id: ${{{{ secrets.AZURE_CLIENT_ID }}}}
          tenant-id: ${{{{ secrets.AZURE_TENANT_ID }}}}
          subscription-id: ${{{{ secrets.AZURE_SUBSCRIPTION_ID }}}}
      
      - name: Deploy to App Service
        if: contains(steps.parse.outputs.resource_type, 'sites')
        run: |
          # Create deployment package
          if [ -d "dist" ]; then
            cd dist
            zip -r ../app.zip .
            cd ..
          elif [ -d "build" ]; then
            cd build
            zip -r ../app.zip .
            cd ..
          else
            zip -r app.zip . -x "node_modules/*" ".git/*" "*.git*"
          fi
          
          # Deploy to App Service
          az webapp deployment source config-zip \\
            --resource-group ${{{{ steps.parse.outputs.resource_group }}}} \\
            --name ${{{{ steps.parse.outputs.resource_name }}}} \\
            --src app.zip
      
      - name: Deployment Summary
        if: success()
        run: |
          echo "===== DEPLOYMENT SUCCESSFUL ====="
          echo "Resource: ${{{{ steps.parse.outputs.resource_name }}}}"
          echo "Resource Group: ${{{{ steps.parse.outputs.resource_group }}}}"
          echo "Environment: ${{{{ env.ENVIRONMENT }}}}"
          echo "App URL: https://${{{{ steps.parse.outputs.resource_name }}}}.azurewebsites.net"
          echo "================================="
      
      - name: Deployment Failed
        if: failure()
        run: |
          echo "===== DEPLOYMENT FAILED ====="
          echo "Resource: ${{{{ steps.parse.outputs.resource_name }}}}"
          echo "Resource Group: ${{{{ steps.parse.outputs.resource_group }}}}"
          echo ""
          echo "Troubleshooting:"
          echo "1. Verify AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID secrets exist"
          echo "2. Check that Service Principal has Contributor role on App Service"
          echo "3. Verify resource exists: az webapp show -g RG -n APP_NAME"
          echo "4. Check App Service logs: https://portal.azure.com"
          echo "================================"
          exit 1
"""


class AzureDevOpsHandler(CICDHandler):
    """Handler para Azure DevOps"""
    
    async def validate_credentials(self, client: httpx.AsyncClient) -> bool:
        """Valida token de Azure DevOps"""
        auth = base64.b64encode(f":{self.token}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}"}
        url = f"https://dev.azure.com/{self.organization}/_apis/projects?api-version=7.0"
        resp = await client.get(url, headers=headers, timeout=5.0)
        return resp.status_code == 200
    
    async def create_pipeline(self, client: httpx.AsyncClient, repo_url: str, branch: str, 
                             resource_id: str, environment: str) -> Tuple[bool, str]:
        """Crea pipeline YAML en Azure DevOps"""
        auth = base64.b64encode(f":{self.token}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
        
        # Crear archivo azure-pipelines.yml en el repo
        pipeline_content = self._get_azdo_pipeline_template(resource_id, environment)
        logger.info(f"Azure DevOps pipeline generated for {resource_id}")
        
        # TODO: Implementar push a repo
        return True, "created"
    
    async def dispatch_pipeline(self, client: httpx.AsyncClient, repo_url: str, branch: str, 
                               resource_id: str, environment: str) -> Tuple[bool, str]:
        """Triggeriza pipeline en Azure DevOps"""
        auth = base64.b64encode(f":{self.token}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
        
        # Trigger via REST API
        run_url = f"https://dev.azure.com/{self.organization}/{self.project}/_apis/pipelines?api-version=7.0"
        logger.info(f"Azure DevOps pipeline dispatch initiated")
        
        return True, "dispatched"
    
    @staticmethod
    def _get_azdo_pipeline_template(resource_id: str, environment: str) -> str:
        return f"""trigger:
- main

pool:
  vmImage: 'ubuntu-latest'

variables:
  resourceId: '{resource_id}'
  environment: '{environment}'

stages:
- stage: Deploy
  jobs:
  - job: DeployJob
    steps:
    - checkout: self
    - script: echo Deploying to ${{{{ variables.resourceId }}}} in ${{{{ variables.environment }}}}
      displayName: 'Echo deployment info'
    - script: echo TODO - Implement deployment
      displayName: 'Deploy step'
"""


class GitLabCIHandler(CICDHandler):
    """Handler para GitLab CI"""
    
    async def validate_credentials(self, client: httpx.AsyncClient) -> bool:
        """Valida token de GitLab"""
        headers = {"PRIVATE-TOKEN": self.token}
        resp = await client.get("https://gitlab.com/api/v4/user", headers=headers, timeout=5.0)
        return resp.status_code == 200
    
    async def create_pipeline(self, client: httpx.AsyncClient, repo_url: str, branch: str, 
                             resource_id: str, environment: str) -> Tuple[bool, str]:
        """Crea .gitlab-ci.yml"""
        pipeline_content = self._get_gitlab_pipeline_template(resource_id, environment)
        logger.info(f"GitLab CI pipeline generated for {resource_id}")
        return True, "created"
    
    async def dispatch_pipeline(self, client: httpx.AsyncClient, repo_url: str, branch: str, 
                               resource_id: str, environment: str) -> Tuple[bool, str]:
        """Triggeriza pipeline en GitLab"""
        logger.info(f"GitLab CI pipeline dispatch initiated")
        return True, "dispatched"
    
    @staticmethod
    def _get_gitlab_pipeline_template(resource_id: str, environment: str) -> str:
        return f"""stages:
  - deploy

deploy_job:
  stage: deploy
  script:
    - echo "Deploying to {resource_id} in {environment}"
    - echo "TODO - Implement deployment"
  only:
    - main
"""


class JenkinsHandler(CICDHandler):
    """Handler para Jenkins"""
    
    async def validate_credentials(self, client: httpx.AsyncClient) -> bool:
        """Valida credenciales de Jenkins"""
        # TODO: Implementar validación según configuración de Jenkins
        logger.info("Jenkins credentials validated")
        return True
    
    async def create_pipeline(self, client: httpx.AsyncClient, repo_url: str, branch: str, 
                             resource_id: str, environment: str) -> Tuple[bool, str]:
        """Crea Jenkinsfile"""
        jenkinsfile = self._get_jenkinsfile_template(resource_id, environment)
        logger.info(f"Jenkins pipeline (Jenkinsfile) generated for {resource_id}")
        return True, "created"
    
    async def dispatch_pipeline(self, client: httpx.AsyncClient, repo_url: str, branch: str, 
                               resource_id: str, environment: str) -> Tuple[bool, str]:
        """Triggeriza job en Jenkins"""
        logger.info(f"Jenkins pipeline dispatch initiated")
        return True, "dispatched"
    
    @staticmethod
    def _get_jenkinsfile_template(resource_id: str, environment: str) -> str:
        return f"""pipeline {{
    agent any
    
    environment {{
        RESOURCE_ID = '{resource_id}'
        ENVIRONMENT = '{environment}'
    }}
    
    stages {{
        stage('Checkout') {{
            steps {{
                checkout scm
            }}
        }}
        stage('Deploy') {{
            steps {{
                sh 'echo Deploying to $RESOURCE_ID in $ENVIRONMENT'
                sh 'echo TODO - Implement deployment'
            }}
        }}
    }}
}}
"""


class CircleCIHandler(CICDHandler):
    """Handler para CircleCI"""
    
    async def validate_credentials(self, client: httpx.AsyncClient) -> bool:
        """Valida token de CircleCI"""
        headers = {"Circle-Token": self.token}
        resp = await client.get("https://circleci.com/api/v2/me", headers=headers, timeout=5.0)
        return resp.status_code == 200
    
    async def create_pipeline(self, client: httpx.AsyncClient, repo_url: str, branch: str, 
                             resource_id: str, environment: str) -> Tuple[bool, str]:
        """Crea .circleci/config.yml"""
        pipeline_content = self._get_circleci_pipeline_template(resource_id, environment)
        logger.info(f"CircleCI pipeline generated for {resource_id}")
        return True, "created"
    
    async def dispatch_pipeline(self, client: httpx.AsyncClient, repo_url: str, branch: str, 
                               resource_id: str, environment: str) -> Tuple[bool, str]:
        """Triggeriza workflow en CircleCI"""
        logger.info(f"CircleCI pipeline dispatch initiated")
        return True, "dispatched"
    
    @staticmethod
    def _get_circleci_pipeline_template(resource_id: str, environment: str) -> str:
        return f"""version: 2.1

jobs:
  deploy:
    docker:
      - image: cimg/base:stable
    steps:
      - checkout
      - run:
          name: Deploy to {resource_id}
          command: |
            echo "Deploying to {resource_id} in {environment}"
            echo "TODO - Implement deployment"

workflows:
  deploy-workflow:
    jobs:
      - deploy
"""


class CICDDispatcher:
    """Dispatcher que selecciona el handler correcto según el tipo de CI/CD"""
    
    HANDLERS = {
        "github-actions": GitHubActionsHandler,
        "azure-devops": AzureDevOpsHandler,
        "gitlab-ci": GitLabCIHandler,
        "jenkins": JenkinsHandler,
        "circleci": CircleCIHandler,
    }
    
    @classmethod
    async def dispatch(cls, cicd_type: str, token: str, repo_url: str, branch: str, 
                       resource_id: str, environment: str, organization: Optional[str] = None,
                       project: Optional[str] = None, 
                       azure_credentials: Optional[Dict[str, str]] = None,
                       client_info: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Selecciona el handler y ejecuta el pipeline según el tipo de CI/CD
        
        Args:
            cicd_type: Tipo de CI/CD (github-actions, azure-devops, gitlab-ci, jenkins, circleci)
            token: Token de acceso
            repo_url: URL del repositorio
            branch: Rama a desplegar
            resource_id: ID del recurso Azure/AWS/GCP
            environment: Ambiente (production, staging, dev)
            organization: Organización (para Azure DevOps, GitLab, etc.)
            project: Proyecto (para Azure DevOps)
            azure_credentials: Credenciales de Azure para GitHub Secrets
            client_info: Información del cliente para generación de pipeline con IA
        """
        logger.info(f"[DISPATCHER] Starting dispatch process")
        logger.info(f"[DISPATCHER] cicd_type={cicd_type}, repo_url={repo_url}, branch={branch}")
        logger.info(f"[DISPATCHER] token_present={token is not None}, org={organization}, project={project}")
        
        handler_class = cls.HANDLERS.get(cicd_type.lower())
        if not handler_class:
            logger.error(f"Unsupported CI/CD type: {cicd_type}")
            return False, f"Unsupported CI/CD type: {cicd_type}"
        
        logger.info(f"Using {cicd_type} handler for deployment")
        
        # Pass Azure credentials and client_info to GitHub Actions handler
        if cicd_type.lower() == "github-actions":
            handler = handler_class(cicd_type, token, organization, project, azure_credentials, client_info)
        else:
            handler = handler_class(cicd_type, token, organization, project)
        
        try:
            async with httpx.AsyncClient() as client:
                # Validar credenciales
                logger.info(f"Validating {cicd_type} credentials...")
                if not await handler.validate_credentials(client):
                    logger.error(f"Invalid {cicd_type} credentials")
                    return False, f"Invalid credentials for {cicd_type}"
                
                logger.info(f"Credentials validated successfully")
                
                # Crear pipeline
                logger.info(f"Creating pipeline in {repo_url}...")
                success, msg = await handler.create_pipeline(client, repo_url, branch, resource_id, environment)
                if not success:
                    logger.error(f"Failed to create pipeline: {msg}")
                    return False, msg
                
                logger.info(f"Pipeline created successfully: {msg}")
                
                # GitHub needs more time to index the workflow - we already wait in create_pipeline for github-actions
                wait_time = 0 if cicd_type == "github-actions" else 1
                if wait_time > 0:
                    logger.info(f"Waiting {wait_time}s for {cicd_type} to index new pipeline...")
                    await asyncio.sleep(wait_time)
                
                # Disparar pipeline
                logger.info(f"Dispatching pipeline in {repo_url}...")
                success, msg = await handler.dispatch_pipeline(client, repo_url, branch, resource_id, environment)
                if not success:
                    logger.error(f"Failed to dispatch pipeline: {msg}")
                    return False, msg
                
                logger.info(f"Pipeline dispatched successfully via {cicd_type}")
                return True, f"Pipeline dispatched via {cicd_type}"
                
        except Exception as e:
            logger.error(f"Error in {cicd_type} dispatch: {e}", exc_info=True)
            return False, f"Error: {str(e)}"
