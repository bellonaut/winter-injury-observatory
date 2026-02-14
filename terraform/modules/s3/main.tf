variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# S3 Bucket for Raw Data
resource "aws_s3_bucket" "raw_data" {
  bucket = "${var.project_name}-${var.environment}-raw-data"

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-raw-data"
      Environment = var.environment
      Purpose     = "Raw data storage"
    }
  )
}

resource "aws_s3_bucket_versioning" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id

  rule {
    id     = "transition_old_data"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 180
      storage_class = "GLACIER"
    }

    expiration {
      days = 730  # 2 years
    }
  }
}

resource "aws_s3_bucket_public_access_block" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Bucket for MLflow Artifacts
resource "aws_s3_bucket" "mlflow_artifacts" {
  bucket = "${var.project_name}-${var.environment}-mlflow-artifacts"

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-mlflow-artifacts"
      Environment = var.environment
      Purpose     = "MLflow artifacts and models"
    }
  )
}

resource "aws_s3_bucket_versioning" "mlflow_artifacts" {
  bucket = aws_s3_bucket.mlflow_artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "mlflow_artifacts" {
  bucket = aws_s3_bucket.mlflow_artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "mlflow_artifacts" {
  bucket = aws_s3_bucket.mlflow_artifacts.id

  rule {
    id     = "cleanup_old_models"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

resource "aws_s3_bucket_public_access_block" "mlflow_artifacts" {
  bucket = aws_s3_bucket.mlflow_artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Bucket for Evidently Reports
resource "aws_s3_bucket" "monitoring_reports" {
  bucket = "${var.project_name}-${var.environment}-monitoring-reports"

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-monitoring-reports"
      Environment = var.environment
      Purpose     = "Evidently monitoring reports"
    }
  )
}

resource "aws_s3_bucket_server_side_encryption_configuration" "monitoring_reports" {
  bucket = aws_s3_bucket.monitoring_reports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "monitoring_reports" {
  bucket = aws_s3_bucket.monitoring_reports.id

  rule {
    id     = "cleanup_old_reports"
    status = "Enabled"

    expiration {
      days = 90
    }
  }
}

resource "aws_s3_bucket_public_access_block" "monitoring_reports" {
  bucket = aws_s3_bucket.monitoring_reports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Bucket for Lambda Deployment Packages
resource "aws_s3_bucket" "lambda_code" {
  bucket = "${var.project_name}-${var.environment}-lambda-code"

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-lambda-code"
      Environment = var.environment
      Purpose     = "Lambda deployment packages"
    }
  )
}

resource "aws_s3_bucket_versioning" "lambda_code" {
  bucket = aws_s3_bucket.lambda_code.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lambda_code" {
  bucket = aws_s3_bucket.lambda_code.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "lambda_code" {
  bucket = aws_s3_bucket.lambda_code.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Outputs
output "raw_data_bucket_name" {
  description = "Name of the raw data S3 bucket"
  value       = aws_s3_bucket.raw_data.id
}

output "raw_data_bucket_arn" {
  description = "ARN of the raw data S3 bucket"
  value       = aws_s3_bucket.raw_data.arn
}

output "mlflow_artifacts_bucket_name" {
  description = "Name of the MLflow artifacts S3 bucket"
  value       = aws_s3_bucket.mlflow_artifacts.id
}

output "mlflow_artifacts_bucket_arn" {
  description = "ARN of the MLflow artifacts S3 bucket"
  value       = aws_s3_bucket.mlflow_artifacts.arn
}

output "monitoring_reports_bucket_name" {
  description = "Name of the monitoring reports S3 bucket"
  value       = aws_s3_bucket.monitoring_reports.id
}

output "monitoring_reports_bucket_arn" {
  description = "ARN of the monitoring reports S3 bucket"
  value       = aws_s3_bucket.monitoring_reports.arn
}

output "lambda_code_bucket_name" {
  description = "Name of the Lambda code S3 bucket"
  value       = aws_s3_bucket.lambda_code.id
}

output "lambda_code_bucket_arn" {
  description = "ARN of the Lambda code S3 bucket"
  value       = aws_s3_bucket.lambda_code.arn
}
