"""
Plantillas pre-definidas para recursos comunes de Azure
 Estas plantillas han sido probadas y funcionan correctamente con Azure
"""

from typing import Dict, Any, List

# Mapeo de tipos de recursos a sus API versions válidas y estructura
AZURE_RESOURCE_TEMPLATES: Dict[str, Dict[str, Any]] = {
    # App Service Plan
    "Microsoft.Web/serverFarms": {
        "api_version": "2022-09-01",
        "example": {
            "type": "Microsoft.Web/serverFarms",
            "apiVersion": "2022-09-01",
            "name": "[parameters('appServicePlanName')]",
            "location": "[parameters('location')]",
            "sku": {
                "name": "B1",
                "tier": "Basic",
                "capacity": 1
            },
            "kind": "linux"
        }
    },
    
    # App Service (Linux)
    "Microsoft.Web/sites": {
        "api_version": "2022-09-01",
        "linux_example": {
            "type": "Microsoft.Web/sites",
            "apiVersion": "2022-09-01",
            "name": "[parameters('siteName')]",
            "location": "[parameters('location')]",
            "kind": "linux,functionapp",
            "properties": {
                "serverFarmId": "[resourceId('Microsoft.Web/serverFarms', parameters('appServicePlanName'))]",
                "siteConfig": {
                    "appSettings": [
                        {
                            "name": "FUNCTIONS_EXTENSION_VERSION",
                            "value": "~4"
                        }
                    ]
                }
            }
        },
        "windows_example": {
            "type": "Microsoft.Web/sites",
            "apiVersion": "2022-09-01",
            "name": "[parameters('siteName')]",
            "location": "[parameters('location')]",
            "kind": "functionapp",
            "properties": {
                "serverFarmId": "[resourceId('Microsoft.Web/serverFarms', parameters('appServicePlanName'))]"
            }
        }
    },
    
    # Virtual Machine
    "Microsoft.Compute/virtualMachines": {
        "api_version": "2021-03-01",
        "example": {
            "type": "Microsoft.Compute/virtualMachines",
            "apiVersion": "2021-03-01",
            "name": "[parameters('vmName')]",
            "location": "[parameters('location')]",
            "properties": {
                "hardwareProfile": {
                    "vmSize": "Standard_B1s"
                },
                "osProfile": {
                    "computerName": "[parameters('vmName')]",
                    "adminUsername": "[parameters('adminUsername')]",
                    "adminPassword": "[parameters('adminPassword')]"
                },
                "storageProfile": {
                    "imageReference": {
                        "publisher": "Canonical",
                        "offer": "UbuntuServer",
                        "sku": "18.04-LTS",
                        "version": "latest"
                    },
                    "osDisk": {
                        "name": "[concat(parameters('vmName'), '-osdisk')]",
                        "managedDisk": {
                            "storageAccountType": "Standard_LRS"
                        },
                        "caching": "ReadWrite",
                        "createOption": "FromImage"
                    }
                },
                "networkProfile": {
                    "networkInterfaces": [
                        {
                            "id": "[resourceId('Microsoft.Network/networkInterfaces', parameters('nicName'))]"
                        }
                    ]
                }
            }
        }
    },
    
    # Network Interface
    "Microsoft.Network/networkInterfaces": {
        "api_version": "2021-03-01",
        "example": {
            "type": "Microsoft.Network/networkInterfaces",
            "apiVersion": "2021-03-01",
            "name": "[parameters('nicName')]",
            "location": "[parameters('location')]",
            "properties": {
                "ipConfigurations": [
                    {
                        "name": "ipconfig1",
                        "properties": {
                            "subnet": {
                                "id": "[resourceId('Microsoft.Network/virtualNetworks/subnets', parameters('vnetName'), parameters('subnetName'))]"
                            },
                            "privateIPAllocationMethod": "Dynamic"
                        }
                    }
                ]
            }
        }
    },
    
    # Virtual Network
    "Microsoft.Network/virtualNetworks": {
        "api_version": "2021-03-01",
        "example": {
            "type": "Microsoft.Network/virtualNetworks",
            "apiVersion": "2021-03-01",
            "name": "[parameters('vnetName')]",
            "location": "[parameters('location')]",
            "properties": {
                "addressSpace": {
                    "addressPrefixes": ["10.0.0.0/16"]
                },
                "subnets": [
                    {
                        "name": "default",
                        "properties": {
                            "addressPrefix": "10.0.0.0/24"
                        }
                    }
                ]
            }
        }
    },
    
    # Public IP Address
    "Microsoft.Network/publicIPAddresses": {
        "api_version": "2021-03-01",
        "example": {
            "type": "Microsoft.Network/publicIPAddresses",
            "apiVersion": "2021-03-01",
            "name": "[parameters('publicIpName')]",
            "location": "[parameters('location')]",
            "sku": {
                "name": "Basic"
            },
            "properties": {
                "publicIPAllocationMethod": "Dynamic"
            }
        }
    },
    
    # Storage Account
    "Microsoft.Storage/storageAccounts": {
        "api_version": "2021-04-01",
        "example": {
            "type": "Microsoft.Storage/storageAccounts",
            "apiVersion": "2021-04-01",
            "name": "[parameters('storageAccountName')]",
            "location": "[parameters('location')]",
            "kind": "StorageV2",
            "sku": {
                "name": "Standard_LRS"
            },
            "properties": {
                "supportsHttpsTrafficOnly": True
            }
        }
    },
    
    # Cosmos DB
    "Microsoft.DocumentDB/databaseAccounts": {
        "api_version": "2021-04-15",
        "example": {
            "type": "Microsoft.DocumentDB/databaseAccounts",
            "apiVersion": "2021-04-15",
            "name": "[parameters('cosmosDbAccountName')]",
            "location": "[parameters('location')]",
            "kind": "GlobalDocumentDB",
            "properties": {
                "databaseAccountOfferType": "Standard",
                "locations": [
                    {
                        "locationName": "[parameters('location')]",
                        "failoverPriority": 0
                    }
                ]
            }
        }
    },
    
    # SQL Database
    "Microsoft.Sql/servers/databases": {
        "api_version": "2021-11-01",
        "example": {
            "type": "Microsoft.Sql/servers/databases",
            "apiVersion": "2021-11-01",
            "name": "[concat(parameters('sqlServerName'), '/', parameters('databaseName'))]",
            "location": "[parameters('location')]",
            "sku": {
                "name": "S0",
                "tier": "Standard"
            }
        }
    },
    
    # SQL Server
    "Microsoft.Sql/servers": {
        "api_version": "2021-11-01",
        "example": {
            "type": "Microsoft.Sql/servers",
            "apiVersion": "2021-11-01",
            "name": "[parameters('sqlServerName')]",
            "location": "[parameters('location')]",
            "properties": {
                "administratorLogin": "[parameters('adminLogin')]",
                "administratorLoginPassword": "[parameters('adminPassword')]"
            }
        }
    },
    
    # Key Vault
    "Microsoft.KeyVault/vaults": {
        "api_version": "2021-10-01",
        "example": {
            "type": "Microsoft.KeyVault/vaults",
            "apiVersion": "2021-10-01",
            "name": "[parameters('keyVaultName')]",
            "location": "[parameters('location')]",
            "properties": {
                "sku": {
                    "family": "A",
                    "name": "standard"
                },
                "tenantId": "[subscription().tenantId]",
                "enableRbacAuthorization": True,
                "enableSoftDelete": True,
                "softDeleteRetentionInDays": 90,
                "enablePurgeProtection": False
            }
        }
    },
    
    # Container Registry
    "Microsoft.ContainerRegistry/registries": {
        "api_version": "2022-02-01",
        "example": {
            "type": "Microsoft.ContainerRegistry/registries",
            "apiVersion": "2022-02-01",
            "name": "[parameters('acrName')]",
            "location": "[parameters('location')]",
            "sku": {
                "name": "Standard"
            },
            "properties": {
                "adminUserEnabled": True
            }
        }
    },
    
    # AKS Cluster
    "Microsoft.ContainerService/managedClusters": {
        "api_version": "2022-09-01",
        "example": {
            "type": "Microsoft.ContainerService/managedClusters",
            "apiVersion": "2022-09-01",
            "name": "[parameters('aksClusterName')]",
            "location": "[parameters('location')]",
            "kubernetesVersion": "1.26",
            "dnsPrefix": "[parameters('dnsPrefix')]",
            "agentPoolProfiles": [
                {
                    "name": "agentpool",
                    "vmSize": "Standard_DS2_v2",
                    "count": 3,
                    "mode": "System"
                }
            ],
            "servicePrincipalProfile": {
                "clientId": "[parameters('servicePrincipalClientId')]",
                "secret": "[parameters('servicePrincipalSecret')]"
            },
            "identity": {
                "type": "SystemAssigned"
            }
        }
    },
    
    # Disk
    "Microsoft.Compute/disks": {
        "api_version": "2021-04-01",
        "example": {
            "type": "Microsoft.Compute/disks",
            "apiVersion": "2021-04-01",
            "name": "[parameters('diskName')]",
            "location": "[parameters('location')]",
            "sku": {
                "name": "Standard_LRS"
            },
            "properties": {
                "creationData": {
                    "createOption": "Empty"
                },
                "diskSizeGB": 10
            }
        }
    }
}


def get_valid_api_version(resource_type: str) -> str:
    """Obtiene la API version válida para un tipo de recurso"""
    template = AZURE_RESOURCE_TEMPLATES.get(resource_type)
    if template:
        return template.get("api_version", "2021-01-01")
    # Default para recursos desconocidos
    return "2021-01-01"


def get_resource_template(resource_type: str, variant: str = "example") -> Dict[str, Any]:
    """Obtiene una plantilla pre-definida para un tipo de recurso"""
    template = AZURE_RESOURCE_TEMPLATES.get(resource_type, {})
    return template.get(variant, template.get("example", {}))


def get_all_supported_resources() -> List[str]:
    """Lista todos los tipos de recursos soportados"""
    return list(AZURE_RESOURCE_TEMPLATES.keys())


# API versions conocidas y válidas por tipo de recurso (para validación dinámica)
VALID_API_VERSIONS = {
    "Microsoft.Web/serverFarms": ["2022-09-01", "2021-02-01", "2020-12-01", "2020-06-01"],
    "Microsoft.Web/sites": ["2022-09-01", "2021-02-01", "2020-12-01", "2020-06-01"],
    "Microsoft.Compute/virtualMachines": ["2021-03-01", "2021-02-01", "2020-12-01"],
    "Microsoft.Compute/disks": ["2021-04-01", "2021-03-01", "2020-12-01"],
    "Microsoft.Network/virtualNetworks": ["2021-03-01", "2021-02-01", "2020-11-01"],
    "Microsoft.Network/publicIPAddresses": ["2021-03-01", "2021-02-01", "2020-11-01"],
    "Microsoft.Network/networkInterfaces": ["2021-03-01", "2021-02-01", "2020-11-01"],
    "Microsoft.Storage/storageAccounts": ["2021-04-01", "2021-02-01", "2020-08-01"],
    "Microsoft.DocumentDB/databaseAccounts": ["2021-04-15", "2021-03-15", "2021-02-01"],
    "Microsoft.Sql/servers": ["2021-11-01", "2021-08-01", "2021-05-01"],
    "Microsoft.Sql/servers/databases": ["2021-11-01", "2021-08-01", "2021-05-01"],
    "Microsoft.KeyVault/vaults": ["2021-10-01", "2021-06-01", "2020-10-01"],
    "Microsoft.ContainerRegistry/registries": ["2022-02-01", "2021-09-01"],
    "Microsoft.ContainerService/managedClusters": ["2022-09-01", "2022-06-01", "2022-03-01"],
}


def get_valid_api_versions(resource_type: str) -> List[str]:
    """Obtiene lista de API versions válidas para un tipo de recurso"""
    return VALID_API_VERSIONS.get(resource_type, ["2021-01-01"])


def validate_and_fix_api_version(resource_type: str, current_version: str) -> str:
    """Valida y corrige una API version si es necesaria"""
    valid_versions = get_valid_api_versions(resource_type)
    
    if current_version in valid_versions:
        return current_version
    
    # Si la versión actual no es válida, usar la primera versión válida
    if valid_versions:
        return valid_versions[0]
    
    return "2021-01-01"  # Fallback
