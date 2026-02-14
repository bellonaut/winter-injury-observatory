variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where Lambda will be deployed"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for Lambda"
  type        = list(string)
}

variable "db_security_group_id" {
  description = "Security group ID of the RDS instance"
  type        = string
}

variable "lambda_code_bucket" {
  description = "S3 bucket containing Lambda deployment packages"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Security Group for Lambda Functions
resource "aws_security_group" "lambda" {
  name        = "${var.project_name}-${var.environment}-lambda-sg"
  description = "Security group for Lambda functions"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-lambda-sg"
      Environment = var.environment
    }
  )
}

# IAM Role for Lambda Execution
resource "aws_iam_role" "lambda_execution" {
  name = "${var.project_name}-${var.environment}-lambda-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-lambda-execution"
      Environment = var.environment
    }
  )
}

resource "aws_iam_role_policy_attachment" "lambda_vpc_execution" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "lambda_s3" {
  name = "${var.project_name}-${var.environment}-lambda-s3"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.project_name}-${var.environment}-*",
          "arn:aws:s3:::${var.project_name}-${var.environment}-*/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_secrets" {
  name = "${var.project_name}-${var.environment}-lambda-secrets"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:*:*:secret:${var.project_name}-${var.environment}-*"
      }
    ]
  })
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "weather_ingestion" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-weather-ingestion"
  retention_in_days = 14

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-weather-ingestion-logs"
      Environment = var.environment
    }
  )
}

resource "aws_cloudwatch_log_group" "model_training" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-model-training"
  retention_in_days = 14

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-model-training-logs"
      Environment = var.environment
    }
  )
}

# Lambda Function: Weather Data Ingestion
resource "aws_lambda_function" "weather_ingestion" {
  function_name = "${var.project_name}-${var.environment}-weather-ingestion"
  role          = aws_iam_role.lambda_execution.arn
  handler       = "lambda_handler.handler"
  runtime       = "python3.11"
  timeout       = 300
  memory_size   = 512

  s3_bucket = var.lambda_code_bucket
  s3_key    = "weather_ingestion.zip"

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      ENVIRONMENT           = var.environment
      DATABASE_SECRET_ARN   = "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}-${var.environment}-db-password"
      RAW_DATA_BUCKET      = "${var.project_name}-${var.environment}-raw-data"
    }
  }

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-weather-ingestion"
      Environment = var.environment
    }
  )

  depends_on = [aws_cloudwatch_log_group.weather_ingestion]
}

# Lambda Function: Model Training Trigger
resource "aws_lambda_function" "model_training" {
  function_name = "${var.project_name}-${var.environment}-model-training"
  role          = aws_iam_role.lambda_execution.arn
  handler       = "lambda_handler.handler"
  runtime       = "python3.11"
  timeout       = 900  # 15 minutes
  memory_size   = 2048

  s3_bucket = var.lambda_code_bucket
  s3_key    = "model_training.zip"

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      ENVIRONMENT           = var.environment
      DATABASE_SECRET_ARN   = "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}-${var.environment}-db-password"
      MLFLOW_BUCKET        = "${var.project_name}-${var.environment}-mlflow-artifacts"
    }
  }

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-model-training"
      Environment = var.environment
    }
  )

  depends_on = [aws_cloudwatch_log_group.model_training]
}

# EventBridge Rule: Hourly Weather Ingestion
resource "aws_cloudwatch_event_rule" "weather_ingestion_hourly" {
  name                = "${var.project_name}-${var.environment}-weather-ingestion-hourly"
  description         = "Trigger weather ingestion every hour"
  schedule_expression = "rate(1 hour)"

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-weather-ingestion-hourly"
      Environment = var.environment
    }
  )
}

resource "aws_cloudwatch_event_target" "weather_ingestion_hourly" {
  rule      = aws_cloudwatch_event_rule.weather_ingestion_hourly.name
  target_id = "WeatherIngestionLambda"
  arn       = aws_lambda_function.weather_ingestion.arn
}

resource "aws_lambda_permission" "weather_ingestion_hourly" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.weather_ingestion.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weather_ingestion_hourly.arn
}

# EventBridge Rule: Weekly Model Training
resource "aws_cloudwatch_event_rule" "model_training_weekly" {
  name                = "${var.project_name}-${var.environment}-model-training-weekly"
  description         = "Trigger model training weekly"
  schedule_expression = "cron(0 4 ? * SUN *)"  # Sunday at 4 AM UTC

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-model-training-weekly"
      Environment = var.environment
    }
  )
}

resource "aws_cloudwatch_event_target" "model_training_weekly" {
  rule      = aws_cloudwatch_event_rule.model_training_weekly.name
  target_id = "ModelTrainingLambda"
  arn       = aws_lambda_function.model_training.arn
}

resource "aws_lambda_permission" "model_training_weekly" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.model_training.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.model_training_weekly.arn
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "weather_ingestion_errors" {
  alarm_name          = "${var.project_name}-${var.environment}-weather-ingestion-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors weather ingestion Lambda errors"
  alarm_actions       = []  # Add SNS topic ARN for notifications

  dimensions = {
    FunctionName = aws_lambda_function.weather_ingestion.function_name
  }

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}-weather-ingestion-errors"
      Environment = var.environment
    }
  )
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# Outputs
output "weather_ingestion_function_arn" {
  description = "ARN of the weather ingestion Lambda function"
  value       = aws_lambda_function.weather_ingestion.arn
}

output "model_training_function_arn" {
  description = "ARN of the model training Lambda function"
  value       = aws_lambda_function.model_training.arn
}

output "lambda_security_group_id" {
  description = "Security group ID for Lambda functions"
  value       = aws_security_group.lambda.id
}
