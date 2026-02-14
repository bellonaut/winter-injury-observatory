#!/bin/bash
set -e

echo "Starting deployment to AWS..."

# Check AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "Error: AWS CLI not configured. Run 'aws configure' first."
    exit 1
fi

# Variables
ENVIRONMENT=${1:-dev}
AWS_REGION=${AWS_REGION:-us-west-2}
ECR_REPOSITORY="winter-injury-observatory"

echo "Deploying to environment: $ENVIRONMENT"
echo "AWS Region: $AWS_REGION"

# Get ECR login
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin \
    $(aws sts get-caller-identity --query Account --output text).dkr.ecr.$AWS_REGION.amazonaws.com

# Build and push images
echo "Building Docker images..."
docker build -t $ECR_REPOSITORY-api:latest -f docker/Dockerfile.api .
docker build -t $ECR_REPOSITORY-dagster:latest -f docker/Dockerfile.dagster .

ECR_URI=$(aws sts get-caller-identity --query Account --output text).dkr.ecr.$AWS_REGION.amazonaws.com

docker tag $ECR_REPOSITORY-api:latest $ECR_URI/$ECR_REPOSITORY-api:latest
docker tag $ECR_REPOSITORY-dagster:latest $ECR_URI/$ECR_REPOSITORY-dagster:latest

echo "Pushing images to ECR..."
docker push $ECR_URI/$ECR_REPOSITORY-api:latest
docker push $ECR_URI/$ECR_REPOSITORY-dagster:latest

# Update ECS services
echo "Updating ECS services..."
aws ecs update-service \
    --cluster winter-injury-observatory-$ENVIRONMENT-cluster \
    --service winter-injury-observatory-$ENVIRONMENT-api \
    --force-new-deployment \
    --region $AWS_REGION

echo "Deployment initiated. Check AWS Console for status."
