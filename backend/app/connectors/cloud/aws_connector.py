"""
Conector para AWS (Amazon Web Services)
"""
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Dict, Any, List, Optional
from app.connectors.cloud.base import BaseCloudConnector
from app.core.logging import logger


class AWSConnector(BaseCloudConnector):
    """
    Conector para AWS
    
    Soporta: EC2, S3, Lambda, ECS, EKS, RDS, CloudFormation, etc.
    """
    
    def __init__(self, credentials: Dict[str, Any], region: Optional[str] = "us-east-1"):
        super().__init__(credentials, region)
        self.session = None
        
    async def connect(self) -> bool:
        """Establece conexión con AWS"""
        try:
            session_token = self.credentials.get("session_token") or None
            self.session = boto3.Session(
                aws_access_key_id=self.credentials.get("access_key_id"),
                aws_secret_access_key=self.credentials.get("secret_access_key"),
                aws_session_token=session_token,
                region_name=self.region
            )
            
            # Test connection
            sts = self.session.client('sts')
            identity = sts.get_caller_identity()
            
            logger.info(f"Conectado a AWS - Account: {identity['Account']}")
            return True
            
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"Error conectando a AWS: {e}")
            return False
    
    async def validate_credentials(self) -> bool:
        """Valida las credenciales de AWS"""
        try:
            if not self.session:
                await self.connect()
            
            sts = self.session.client('sts')
            sts.get_caller_identity()
            return True
            
        except Exception as e:
            logger.error(f"Credenciales AWS inválidas: {e}")
            return False
    
    async def list_resources(self, resource_type: str) -> List[Dict[str, Any]]:
        """
        Lista recursos de AWS
        
        Args:
            resource_type: ec2, s3, lambda, rds, ecs, eks, etc.
        """
        try:
            if resource_type == "ec2":
                return await self._list_ec2_instances()
            elif resource_type == "s3":
                return await self._list_s3_buckets()
            elif resource_type == "lambda":
                return await self._list_lambda_functions()
            elif resource_type == "rds":
                return await self._list_rds_instances()
            elif resource_type == "ecs":
                return await self._list_ecs_clusters()
            elif resource_type == "eks":
                return await self._list_eks_clusters()
            elif resource_type == "amplify":
                return await self._list_amplify_apps()
            else:
                logger.warning(f"Tipo de recurso no soportado: {resource_type}")
                return []
                
        except Exception as e:
            logger.error(f"Error listando recursos {resource_type}: {e}")
            return []
    
    async def _list_ec2_instances(self) -> List[Dict[str, Any]]:
        """Lista instancias EC2 con estado enriquecido"""
        ec2 = self.session.client('ec2')
        response = ec2.describe_instances()
        
        instances = []
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                state = instance['State']['Name']
                status = 'running' if state == 'running' else 'stopped' if state in ['stopped', 'terminated'] else 'pending'
                
                instances.append({
                    'id': instance['InstanceId'],
                    'name': next((tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] == 'Name'), instance['InstanceId']),
                    'type': 'ec2_instance',
                    'state': state,
                    'status': status,
                    'launch_time': str(instance['LaunchTime']),
                    'behavior': {
                        'instance_type': instance['InstanceType'],
                        'public_ip': instance.get('PublicIpAddress', 'None')
                    }
                })
        
        return instances
    
    async def _list_s3_buckets(self) -> List[Dict[str, Any]]:
        """Lista buckets S3"""
        s3 = self.session.client('s3')
        response = s3.list_buckets()
        
        return [
            {
                'id': bucket['Name'],
                'name': bucket['Name'],
                'type': 's3_bucket',
                'status': 'active',
                'creation_date': str(bucket['CreationDate'])
            }
            for bucket in response['Buckets']
        ]
    
    async def _list_lambda_functions(self) -> List[Dict[str, Any]]:
        """Lista funciones Lambda"""
        lambda_client = self.session.client('lambda')
        response = lambda_client.list_functions()
        
        return [
            {
                'name': func['FunctionName'],
                'runtime': func['Runtime'],
                'memory': func['MemorySize'],
                'last_modified': func['LastModified']
            }
            for func in response['Functions']
        ]
    
    async def _list_rds_instances(self) -> List[Dict[str, Any]]:
        """Lista instancias RDS"""
        rds = self.session.client('rds')
        response = rds.describe_db_instances()
        
        return [
            {
                'id': db['DBInstanceIdentifier'],
                'engine': db['Engine'],
                'status': db['DBInstanceStatus'],
                'endpoint': db.get('Endpoint', {}).get('Address')
            }
            for db in response['DBInstances']
        ]
    
    async def _list_ecs_clusters(self) -> List[Dict[str, Any]]:
        """Lista clusters ECS"""
        ecs = self.session.client('ecs')
        cluster_arns = ecs.list_clusters()['clusterArns']
        
        if not cluster_arns:
            return []
        
        clusters = ecs.describe_clusters(clusters=cluster_arns)['clusters']
        
        return [
            {
                'name': cluster['clusterName'],
                'status': cluster['status'],
                'running_tasks': cluster['runningTasksCount'],
                'pending_tasks': cluster['pendingTasksCount']
            }
            for cluster in clusters
        ]
    
    async def _list_eks_clusters(self) -> List[Dict[str, Any]]:
        """Lista clusters EKS"""
        eks = self.session.client('eks')
        cluster_names = eks.list_clusters()['clusters']
        
        clusters = []
        for name in cluster_names:
            cluster = eks.describe_cluster(name=name)['cluster']
            clusters.append({
                'name': cluster['name'],
                'status': cluster['status'],
                'version': cluster['version'],
                'endpoint': cluster['endpoint']
            })
        
        return clusters
    
    async def _list_amplify_apps(self) -> List[Dict[str, Any]]:
        """Lista aplicaciones de AWS Amplify"""
        amplify = self.session.client('amplify', region_name=self.region)
        response = amplify.list_apps(maxResults=100)

        apps = []
        for app in response.get('apps', []):
            # Estado de la app
            raw_status = app.get('productionBranch', {}).get('status', 'UNKNOWN')
            status = 'running' if raw_status in ['SUCCEED', 'DEPLOYED'] else \
                     'stopped' if raw_status in ['FAILED', 'CANCELLED'] else 'pending'

            apps.append({
                'id': app['appId'],
                'name': app.get('name', app['appId']),
                'type': 'amplify_app',
                'status': status,
                'platform': app.get('platform', 'WEB'),
                'repository': app.get('repository', '-'),
                'default_domain': app.get('defaultDomain', '-'),
                'create_time': str(app.get('createTime', '')),
                'behavior': {
                    'platform': app.get('platform', 'WEB'),
                    'repository': app.get('repository', '-'),
                    'default_domain': app.get('defaultDomain', '-'),
                    'framework': app.get('framework', '-'),
                    'branch_status': raw_status
                }
            })

        return apps

    async def create_resource(
        self,
        resource_type: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Crea un recurso en AWS"""
        try:
            if resource_type == "ec2":
                return await self._create_ec2_instance(config)
            elif resource_type == "s3":
                return await self._create_s3_bucket(config)
            elif resource_type == "lambda":
                return await self._create_lambda_function(config)
            else:
                raise ValueError(f"Tipo de recurso no soportado: {resource_type}")
                
        except Exception as e:
            logger.error(f"Error creando recurso {resource_type}: {e}")
            raise
    
    async def _create_ec2_instance(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Crea una instancia EC2"""
        ec2 = self.session.client('ec2')
        
        response = ec2.run_instances(
            ImageId=config.get('image_id', 'ami-0c55b159cbfafe1f0'),
            InstanceType=config.get('instance_type', 't2.micro'),
            MinCount=1,
            MaxCount=1,
            KeyName=config.get('key_name'),
            SecurityGroupIds=config.get('security_groups', []),
            SubnetId=config.get('subnet_id'),
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [{'Key': k, 'Value': v} for k, v in config.get('tags', {}).items()]
                }
            ]
        )
        
        instance = response['Instances'][0]
        return {
            'id': instance['InstanceId'],
            'state': instance['State']['Name']
        }
    
    async def _create_s3_bucket(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un bucket S3"""
        s3 = self.session.client('s3')
        
        bucket_name = config['bucket_name']
        
        if self.region == 'us-east-1':
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': self.region}
            )
        
        return {'bucket_name': bucket_name, 'region': self.region}
    
    async def _create_lambda_function(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Crea una función Lambda"""
        lambda_client = self.session.client('lambda')
        
        response = lambda_client.create_function(
            FunctionName=config['function_name'],
            Runtime=config.get('runtime', 'python3.11'),
            Role=config['role_arn'],
            Handler=config.get('handler', 'index.handler'),
            Code=config['code'],
            Timeout=config.get('timeout', 30),
            MemorySize=config.get('memory', 128)
        )
        
        return {
            'function_name': response['FunctionName'],
            'function_arn': response['FunctionArn']
        }
    
    async def delete_resource(
        self,
        resource_type: str,
        resource_id: str
    ) -> bool:
        """Elimina un recurso de AWS"""
        try:
            if resource_type == "ec2":
                ec2 = self.session.client('ec2')
                ec2.terminate_instances(InstanceIds=[resource_id])
            elif resource_type == "s3":
                s3 = self.session.client('s3')
                s3.delete_bucket(Bucket=resource_id)
            elif resource_type == "lambda":
                lambda_client = self.session.client('lambda')
                lambda_client.delete_function(FunctionName=resource_id)
            else:
                raise ValueError(f"Tipo de recurso no soportado: {resource_type}")
            
            logger.info(f"Recurso {resource_type}/{resource_id} eliminado")
            return True
            
        except Exception as e:
            logger.error(f"Error eliminando recurso: {e}")
            return False
    
    async def get_resource_status(
        self,
        resource_type: str,
        resource_id: str
    ) -> Dict[str, Any]:
        """Obtiene el estado de un recurso"""
        try:
            if resource_type == "ec2":
                ec2 = self.session.client('ec2')
                response = ec2.describe_instances(InstanceIds=[resource_id])
                instance = response['Reservations'][0]['Instances'][0]
                return {
                    'id': instance['InstanceId'],
                    'state': instance['State']['Name'],
                    'type': instance['InstanceType']
                }
            else:
                return {'status': 'unknown'}
                
        except Exception as e:
            logger.error(f"Error obteniendo estado: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def deploy_infrastructure(
        self,
        infrastructure_code: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Despliega infraestructura usando CloudFormation
        
        Args:
            infrastructure_code: Template de CloudFormation (JSON/YAML)
            parameters: Parámetros del stack
        """
        try:
            cfn = self.session.client('cloudformation')
            
            stack_name = parameters.get('stack_name', 'iaops-stack')
            
            response = cfn.create_stack(
                StackName=stack_name,
                TemplateBody=infrastructure_code,
                Parameters=[
                    {'ParameterKey': k, 'ParameterValue': str(v)}
                    for k, v in (parameters or {}).items()
                    if k != 'stack_name'
                ],
                Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM']
            )
            
            logger.info(f"Stack CloudFormation creado: {stack_name}")
            
            return {
                'stack_id': response['StackId'],
                'stack_name': stack_name,
                'status': 'CREATE_IN_PROGRESS'
            }
            
        except Exception as e:
            logger.error(f"Error desplegando infraestructura: {e}")
            raise
