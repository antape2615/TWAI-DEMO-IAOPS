import asyncio
import sys
import os
import json
from unittest.mock import MagicMock

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.orchestrators.ai_orchestrator import ai_orchestrator
from app.models.schemas import Client, TechProfile, TechStandards, ArchitectureRequest, CloudProvider, RepositoryProvider, InfrastructureStandard, CICDStandard

# Mock _call_ai
original_call_ai = ai_orchestrator._call_ai

async def mock_call_ai(prompt: str) -> str:
    print(f"DEBUG: _call_ai called with prompt containing: {prompt[:100]}...")
    if "Genera código de infraestructura usando bicep" in prompt:
        return """
param location string = resourceGroup().location

resource vnet 'Microsoft.Network/virtualNetworks@2021-02-01' = {
  name = 'vnet-1'
  location = location
}
"""
    elif "Genera código de infraestructura usando terraform" in prompt:
        return """
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}
"""
    elif "Diseña una arquitectura" in prompt:
        return json.dumps({
            "architecture_overview": "Mocked Architecture",
            "components": [],
            "infrastructure_code": "Mocked Code", # This will be overwritten by the second call
            "estimated_cost": {"monthly_estimate": 100},
            "recommendations": []
        })
    return "{}"

ai_orchestrator._call_ai = mock_call_ai

async def test_generation():
    print("--- Starting Test ---")

    # 1. Test Azure + Bicep
    print("\n--- Testing Azure + Bicep ---")
    azure_client = Client(
        id="test-client-azure",
        name="Test Client Azure",
        tech_profile=TechProfile(
            clouds=[CloudProvider.AZURE],
            repositories=[RepositoryProvider.GITHUB],
            standards=TechStandards(
                infrastructure=InfrastructureStandard.BICEP,
                cicd=CICDStandard.GITHUB_ACTIONS
            )
        )
    )

    request_azure = ArchitectureRequest(
        client_id="test-client-azure",
        description="I need a virtual machine with 2 disks, 1 network, and 2 subnets.",
        requirements={"scalability": "medium"}
    )

    try:
        result_azure = await ai_orchestrator.generate_architecture(azure_client, request_azure)
        print("Architecture Overview:", result_azure['architecture'].get('architecture_overview'))
        print("Infrastructure Code Snippet:")
        print(result_azure['infrastructure_code'])
        
        if "param" in result_azure['infrastructure_code'] and "resource" in result_azure['infrastructure_code']:
             print("SUCCESS: Code looks like Bicep.")
        else:
             print("WARNING: Code might not be Bicep.")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

    # 2. Test AWS + Terraform
    print("\n--- Testing AWS + Terraform ---")
    aws_client = Client(
        id="test-client-aws",
        name="Test Client AWS",
        tech_profile=TechProfile(
            clouds=[CloudProvider.AWS],
            repositories=[RepositoryProvider.GITHUB],
            standards=TechStandards(
                infrastructure=InfrastructureStandard.TERRAFORM,
                cicd=CICDStandard.GITHUB_ACTIONS
            )
        )
    )

    request_aws = ArchitectureRequest(
        client_id="test-client-aws",
        description="I need a virtual machine with 2 disks, 1 network, and 2 subnets.",
        requirements={"scalability": "medium"}
    )

    try:
        result_aws = await ai_orchestrator.generate_architecture(aws_client, request_aws)
        print("Architecture Overview:", result_aws['architecture'].get('architecture_overview'))
        print("Infrastructure Code Snippet:")
        print(result_aws['infrastructure_code'])

        if "resource" in result_aws['infrastructure_code'] and "aws_" in result_aws['infrastructure_code']:
             print("SUCCESS: Code looks like Terraform.")
        else:
             print("WARNING: Code might not be Terraform.")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_generation())
