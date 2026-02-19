# Configuración de Despliegue a Azure

## Descripción General

El sistema IAOPS ahora configura automáticamente las credenciales de Azure en GitHub Secrets cuando se crea el workflow de deployment. Esto elimina la necesidad de configuración manual.

## Flujo Automático

```
Frontend (click "Desplegar")
    ↓
Backend API (/api/v1/deployments/code)
    ↓
CICDDispatcher.dispatch()
    ↓
GitHubActionsHandler:
  1. Crea workflow en .github/workflows/deploy.yml (si no existe)
  2. Crea Azure secrets automáticamente en GitHub:
     - AZURE_CLIENT_ID
     - AZURE_CLIENT_SECRET
     - AZURE_TENANT_ID
     - AZURE_SUBSCRIPTION_ID
     - AZURE_CREDENTIALS (JSON combinado)
  3. Dispara el workflow en GitHub
    ↓
GitHub Actions Runner:
  1. Autentica con Azure (Azure Login)
  2. Parsea el Resource ID
  3. Construye el artifact (npm build, etc.)
  4. Despliega a Azure (az webapp deploy)
    ↓
Azure App Service:
  - Código actualizado
  - Aplicación redeployada
```

## Requisitos Previos

### 1. Credenciales de Azure en Variables de Entorno

El backend debe tener las credenciales de Azure configuradas en `.env.docker`:

```env
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
AZURE_TENANT_ID=
AZURE_SUBSCRIPTION_ID=
```

### 2. Permisos del Service Principal

El Service Principal de Azure debe tener:
- **Contributor** en el recurso de App Service
- **Reader** en el Resource Group (para listar recursos)

## Cómo Obtener Credenciales

### Opción A: Usar Azure CLI (Recomendado)

```bash
az ad sp create-for-rbac --name "iaops-deployment" \
  --role contributor \
  --scopes /subscriptions/{subscription-id} \
  --json-auth
```

Reemplaza `{subscription-id}` con tu subscription ID de Azure.

Esto retornará un objeto JSON como:
```json
{
  "clientId": "xxx",
  "clientSecret": "xxx",
  "subscriptionId": "xxx",
  "tenantId": "xxx"
}
```

### Opción B: Usar Azure Portal

1. Ve a Azure Portal → Microsoft Entra ID → App registrations
2. Create new registration
3. Ve a "Certificates & secrets"
4. Crea un nuevo client secret
5. Anota: clientId, clientSecret, tenantId, subscriptionId

## Configuración en Docker

Las credenciales se configuran automáticamente en el archivo `.env.docker` del backend:

```env
# Azure Configuration
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_TENANT_ID=your-tenant-id
AZURE_SUBSCRIPTION_ID=your-subscription-id
```

Al iniciar el contenedor Docker, estas credenciales se cargan automáticamente y se usan para:
1. Autenticar con Azure desde el backend
2. Crear los secrets en GitHub (cifrados con la clave pública del repositorio)

## Verificación

### 1. Verificar Secrets en GitHub

Después de un despliegue exitoso, puedes verificar que los secrets se crearon:

1. Ve a tu repositorio en GitHub
2. **Settings** → **Secrets and variables** → **Actions**
3. Deberías ver:
   - `AZURE_CLIENT_ID`
   - `AZURE_CLIENT_SECRET`
   - `AZURE_TENANT_ID`
   - `AZURE_SUBSCRIPTION_ID`
   - `AZURE_CREDENTIALS` (JSON combinado)

### 2. Verificar Workflow

El workflow se encuentra en `.github/workflows/deploy.yml` y usa:

```yaml
- name: Azure Login
  uses: azure/login@v1
  with:
    client-id: ${{ secrets.AZURE_CLIENT_ID }}
    tenant-id: ${{ secrets.AZURE_TENANT_ID }}
    subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
```

## Debugging

Si el workflow falla:

1. **Ve a GitHub Actions** en tu repositorio
2. Verifica el último workflow run
3. Expansiona cada step para ver logs detallados
4. Busca errores en:
   - `Azure Login` - check if AZURE credentials are correct
   - `Deploy to App Service` - check if resource exists and naming is correct

## Referencias

- [Azure Login Action](https://github.com/azure/login)
- [Azure App Service Deployment](https://learn.microsoft.com/en-us/azure/app-service/deploy-github-actions)
- [GitHub Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
