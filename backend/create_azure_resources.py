#!/usr/bin/env python3
"""
Script to create Azure resource group and App Service
"""
import os
import sys
from azure.identity import ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.web import WebSiteManagementClient

# Azure credentials from environment
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "e1bdfea1-5fcd-44c1-8196-dfa7afddd8c5")
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "b1796cf0-a7f8-4fd9-939d-b462b4cfe48f")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "UQv8Q~CWQf6o1RX7~lbOLnBJaITLuRul4TwGjcmr")
AZURE_SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID", "ba8381f0-1448-45c2-82b2-a24f42014369")

# Resource configuration
RESOURCE_GROUP_NAME = "rg_iop"
LOCATION = "eastus"
APP_SERVICE_NAME = "peribank_mobile"
APP_SERVICE_PLAN_NAME = "asp-peribank-mobile"


def create_resources():
    print(f"Creating Azure resources...")
    print(f"Resource Group: {RESOURCE_GROUP_NAME}")
    print(f"App Service: {APP_SERVICE_NAME}")
    print(f"Location: {LOCATION}")
    
    # Authenticate
    credential = ClientSecretCredential(
        tenant_id=AZURE_TENANT_ID,
        client_id=AZURE_CLIENT_ID,
        client_secret=AZURE_CLIENT_SECRET
    )
    
    resource_client = ResourceManagementClient(
        credential=credential,
        subscription_id=AZURE_SUBSCRIPTION_ID
    )
    
    web_client = WebSiteManagementClient(
        credential=credential,
        subscription_id=AZURE_SUBSCRIPTION_ID
    )
    
    # Create resource group
    print("\n--- Creating Resource Group ---")
    try:
        rg_poller = resource_client.resource_groups.begin_create_or_update(
            RESOURCE_GROUP_NAME,
            {
                "location": LOCATION,
                "tags": {
                    "environment": "development",
                    "project": "peribank"
                }
            }
        )
        rg_result = rg_poller.result()
        print(f"Resource Group created: {rg_result.id}")
    except Exception as e:
        print(f"Error creating resource group: {e}")
    
    # Create App Service Plan
    print("\n--- Creating App Service Plan ---")
    try:
        asp_poller = web_client.app_service_plans.begin_create_or_update(
            RESOURCE_GROUP_NAME,
            APP_SERVICE_PLAN_NAME,
            {
                "location": LOCATION,
                "sku": {
                    "name": "F1",
                    "tier": "Free",
                    "capacity": 1
                },
                "kind": "linux",
                "reserved": True
            }
        )
        asp_result = asp_poller.result()
        print(f"App Service Plan created: {asp_result.id}")
    except Exception as e:
        print(f"Error creating App Service Plan: {e}")
    
    # Create App Service (Web App)
    print("\n--- Creating App Service ---")
    try:
        web_poller = web_client.web_apps.begin_create_or_update(
            RESOURCE_GROUP_NAME,
            APP_SERVICE_NAME,
            {
                "location": LOCATION,
                "server_farm_id": f"/subscriptions/{AZURE_SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP_NAME}/providers/Microsoft.Web/serverFarms/{APP_SERVICE_PLAN_NAME}",
                "kind": "app,linux",
                "reserved": True,
                "site_config": {
                    "linux_fx_version": "PYTHON|3.11",
                    "python_version": "3.11"
                },
                "tags": {
                    "environment": "development",
                    "project": "peribank"
                }
            }
        )
        web_result = web_poller.result()
        print(f"App Service created: {web_result.id}")
        print(f"App Service URL: https://{web_result.default_host_name}")
    except Exception as e:
        print(f"Error creating App Service: {e}")
    
    print("\n--- Resources Created Successfully ---")


if __name__ == "__main__":
    create_resources()
