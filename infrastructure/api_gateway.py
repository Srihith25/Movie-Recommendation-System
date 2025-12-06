# infrastructure/api_gateway.py
from aws_cdk import (
    Stack,
    Duration,
    aws_apigateway as apigateway,
    aws_lambda as lambda_,
)
from constructs import Construct


class ApiStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # Create Lambda functions
        recommendations_lambda = lambda_.Function(
            self, "RecommendationsLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            code=lambda_.Code.from_asset("lambdas/recommendations"),
            handler="handler.get_recommendations",
            timeout=Duration.seconds(30),
            memory_size=512,
            environment={
                'PYTHONPATH': '/opt/python'
            }
        )
        
        # Add Lambda layer for dependencies
        layer = lambda_.LayerVersion(
            self, "DependenciesLayer",
            code=lambda_.Code.from_asset("layers/python.zip"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_9]
        )
        recommendations_lambda.add_layers(layer)
        
        # Create API Gateway
        api = apigateway.RestApi(
            self, "MovieRecAPI",
            rest_api_name="Movie Recommendations API",
            description="API for movie recommendations with explanations"
        )
        
        # Add resources and methods
        users = api.root.add_resource("users")
        user = users.add_resource("{userId}")
        recommendations = user.add_resource("recommendations")
        
        # Add GET method
        recommendations.add_method(
            "GET",
            apigateway.LambdaIntegration(recommendations_lambda),
            authorization_type=apigateway.AuthorizationType.NONE
        )
        
        # Enable CORS
        recommendations.add_cors_preflight(
            allow_origins=["*"],
            allow_methods=["GET", "OPTIONS"]
        )
