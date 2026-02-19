"""
ARM Template for creating an App Service with App Service Plan
"""

APP_SERVICE_ARM_TEMPLATE = {
    "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
    "contentVersion": "1.0.0.0",
    "parameters": {
        "location": {
            "type": "string",
            "defaultValue": "eastus",
            "metadata": {
                "description": "Location for the resources"
            }
        },
        "appServicePlanName": {
            "type": "string",
            "metadata": {
                "description": "Name of the App Service Plan"
            }
        },
        "webAppName": {
            "type": "string",
            "metadata": {
                "description": "Name of the Web App"
            }
        },
        "linuxFxVersion": {
            "type": "string",
            "defaultValue": "PYTHON|3.11",
            "metadata": {
                "description": "Linux FX Version (runtime stack)"
            }
        }
    },
    "resources": [
        {
            "type": "Microsoft.Web/serverFarms",
            "apiVersion": "2022-09-01",
            "name": "[parameters('appServicePlanName')]",
            "location": "[parameters('location')]",
            "sku": {
                "name": "F1",
                "tier": "Free",
                "capacity": 1
            },
            "kind": "linux",
            "properties": {
                "reserved": True
            }
        },
        {
            "type": "Microsoft.Web/sites",
            "apiVersion": "2022-09-01",
            "name": "[parameters('webAppName')]",
            "location": "[parameters('location')]",
            "kind": "app,linux",
            "dependsOn": [
                "[resourceId('Microsoft.Web/serverFarms', parameters('appServicePlanName'))]"
            ],
            "properties": {
                "serverFarmId": "[resourceId('Microsoft.Web/serverFarms', parameters('appServicePlanName'))]",
                "siteConfig": {
                    "linuxFxVersion": "[parameters('linuxFxVersion')]",
                    "alwaysOn": False,
                    "http20Enabled": True
                }
            }
        }
    ]
}

# Bicep template for App Service
APP_SERVICE_BICEP = """
param location string = 'eastus'
param appServicePlanName string = 'asp-peribank'
param webAppName string = 'peribank-mobile'
param linuxFxVersion string = 'PYTHON|3.11'

// App Service Plan
resource appServicePlan 'Microsoft.Web/serverFarms@2022-09-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: 'F1'
    tier: 'Free'
    capacity: 1
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

// App Service (Web App)
resource webApp 'Microsoft.Web/sites@2022-09-01' = {
  name: webAppName
  location: location
  kind: 'app,linux'
  dependsOn: [appServicePlan]
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      linuxFxVersion: linuxFxVersion
      alwaysOn: false
      http20Enabled: true
    }
  }
}

output webAppUrl string = 'https://${webApp.properties.defaultHostName}'
"""
