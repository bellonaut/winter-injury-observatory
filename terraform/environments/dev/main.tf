terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  backend "s3" {
    bucket         = "winter-injury-observatory-terraform-state"
    key            = "dev/terraform.tfstate"
    region         = "us-west-2"
    encrypt        = true
    dynamodb_table = "winter-injury-observatory-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Local Variables
locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# VPC Configuration
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-vpc"
    }
  )
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-igw"
    }
  )
}

# Public Subnets
resource "aws_subnet" "public" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone = var.availability_zones[count.index]

  map_public_ip_on_launch = true

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-public-${var.availability_zones[count.index]}"
      Type = "Public"
    }
  )
}

# Private Subnets
resource "aws_subnet" "private" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  availability_zone = var.availability_zones[count.index]

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-private-${var.availability_zones[count.index]}"
      Type = "Private"
    }
  )
}

# NAT Gateway
resource "aws_eip" "nat" {
  domain = "vpc"

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-nat-eip"
    }
  )
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-nat"
    }
  )

  depends_on = [aws_internet_gateway.main]
}

# Route Tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-public-rt"
    }
  )
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-private-rt"
    }
  )
}

# Route Table Associations
resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count          = length(aws_subnet.private)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# S3 Module
module "s3" {
  source = "../../modules/s3"

  project_name = var.project_name
  environment  = var.environment
  tags         = local.common_tags
}

# RDS Module
module "rds" {
  source = "../../modules/rds"

  project_name           = var.project_name
  environment            = var.environment
  vpc_id                 = aws_vpc.main.id
  private_subnet_ids     = aws_subnet.private[*].id
  database_name          = var.database_name
  instance_class         = var.rds_instance_class
  allocated_storage      = var.rds_allocated_storage
  backup_retention_period = var.rds_backup_retention_period
  allowed_security_groups = [module.ecs.ecs_task_security_group_id, module.lambda.lambda_security_group_id]
  tags                   = local.common_tags
}

# ECS Module
module "ecs" {
  source = "../../modules/ecs"

  project_name         = var.project_name
  environment          = var.environment
  vpc_id               = aws_vpc.main.id
  private_subnet_ids   = aws_subnet.private[*].id
  public_subnet_ids    = aws_subnet.public[*].id
  db_security_group_id = module.rds.db_security_group_id
  tags                 = local.common_tags
}

# Lambda Module
module "lambda" {
  source = "../../modules/lambda"

  project_name         = var.project_name
  environment          = var.environment
  vpc_id               = aws_vpc.main.id
  private_subnet_ids   = aws_subnet.private[*].id
  db_security_group_id = module.rds.db_security_group_id
  lambda_code_bucket   = module.s3.lambda_code_bucket_name
  tags                 = local.common_tags
}

# Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "database_endpoint" {
  description = "RDS database endpoint"
  value       = module.rds.db_instance_endpoint
  sensitive   = true
}

output "database_secret_arn" {
  description = "ARN of the secret containing DB credentials"
  value       = module.rds.db_password_secret_arn
}

output "api_url" {
  description = "URL for the API"
  value       = module.ecs.api_url
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = module.ecs.cluster_name
}

output "raw_data_bucket" {
  description = "Name of the raw data S3 bucket"
  value       = module.s3.raw_data_bucket_name
}

output "mlflow_artifacts_bucket" {
  description = "Name of the MLflow artifacts S3 bucket"
  value       = module.s3.mlflow_artifacts_bucket_name
}

output "monitoring_reports_bucket" {
  description = "Name of the monitoring reports S3 bucket"
  value       = module.s3.monitoring_reports_bucket_name
}
