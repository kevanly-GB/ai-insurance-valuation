terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}
provider "aws" { region = var.aws_region }
data "aws_availability_zones" "available" { state = "available" }
variable "aws_region" { default = "ap-southeast-2" }
variable "prefix" { default = "insurance-capstone-dev" }
variable "lambda_zip_path" { default = "../../build/insurance-lambda.zip" }
variable "db_class" { default = "db.t4g.micro" }
variable "bedrock_model_id" { default = "" }
locals {
  origin = format("https://%s", aws_cloudfront_distribution.web.domain_name)
  env = {
    APP_ENV = "aws"
    PGHOST = aws_db_instance.db.address
    PGPORT = "5432"
    PGDATABASE = "insurance"
    DB_SECRET_ARN = aws_db_instance.db.master_user_secret[0].secret_arn
    S3_BUCKET_NAME = aws_s3_bucket.evidence.id
    COGNITO_USER_POOL_ID = aws_cognito_user_pool.users.id
    COGNITO_APP_CLIENT_ID = aws_cognito_user_pool_client.web.id
    FRONTEND_ORIGINS = local.origin
    PROCESS_QUEUE_URL = aws_sqs_queue.jobs.id
    BEDROCK_MODEL_ID = var.bedrock_model_id
  }
}
resource "aws_vpc" "app" {
  cidr_block = "10.42.0.0/16"
  enable_dns_support = true
  enable_dns_hostnames = true
}
resource "aws_internet_gateway" "igw" { vpc_id = aws_vpc.app.id }
resource "aws_subnet" "public" {
  vpc_id = aws_vpc.app.id
  cidr_block = "10.42.1.0/24"
  availability_zone = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
}
resource "aws_subnet" "a" {
  vpc_id = aws_vpc.app.id
  cidr_block = "10.42.11.0/24"
  availability_zone = data.aws_availability_zones.available.names[0]
}
resource "aws_subnet" "b" {
  vpc_id = aws_vpc.app.id
  cidr_block = "10.42.12.0/24"
  availability_zone = data.aws_availability_zones.available.names[1]
}
resource "aws_route_table" "pub" { vpc_id = aws_vpc.app.id }
resource "aws_route" "pub" {
  route_table_id = aws_route_table.pub.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id = aws_internet_gateway.igw.id
}
resource "aws_route_table_association" "pub" {
  subnet_id = aws_subnet.public.id
  route_table_id = aws_route_table.pub.id
}
resource "aws_eip" "nat" { domain = "vpc" }
resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat.id
  subnet_id = aws_subnet.public.id
  depends_on = [aws_internet_gateway.igw]
}
resource "aws_route_table" "priv" { vpc_id = aws_vpc.app.id }
resource "aws_route" "priv" {
  route_table_id = aws_route_table.priv.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id = aws_nat_gateway.nat.id
}
resource "aws_route_table_association" "a" {
  subnet_id = aws_subnet.a.id
  route_table_id = aws_route_table.priv.id
}
resource "aws_route_table_association" "b" {
  subnet_id = aws_subnet.b.id
  route_table_id = aws_route_table.priv.id
}
resource "aws_vpc_endpoint" "s3" {
  vpc_id = aws_vpc.app.id
  service_name = format("com.amazonaws.%s.s3", var.aws_region)
  vpc_endpoint_type = "Gateway"
  route_table_ids = [aws_route_table.priv.id]
}
resource "aws_security_group" "fn" {
  name_prefix = "insurance-lambda-"
  vpc_id = aws_vpc.app.id
  egress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_security_group" "db" {
  name_prefix = "insurance-db-"
  vpc_id = aws_vpc.app.id
  ingress {
    from_port = 5432
    to_port = 5432
    protocol = "tcp"
    security_groups = [aws_security_group.fn.id]
  }
}
resource "aws_db_subnet_group" "db" {
  name = format("%s-db",var.prefix)
  subnet_ids = [aws_subnet.a.id, aws_subnet.b.id]
}
resource "aws_db_instance" "db" {
  identifier = format("%s-postgres", var.prefix)
  engine = "postgres"
  engine_version = "16"
  instance_class = var.db_class
  allocated_storage = 20
  storage_type = "gp3"
  storage_encrypted = true
  db_name = "insurance"
  username = "insuranceadmin"
  manage_master_user_password = true
  publicly_accessible = false
  db_subnet_group_name = aws_db_subnet_group.db.name
  vpc_security_group_ids = [aws_security_group.db.id]
  backup_retention_period = 1
  deletion_protection = false
  skip_final_snapshot = true
}
resource "aws_s3_bucket" "artifacts" {
  bucket_prefix = format("%s-build-",var.prefix)
  force_destroy = false
}
resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  block_public_acls = true
  block_public_policy = true
  ignore_public_acls = true
  restrict_public_buckets = true
}
resource "aws_s3_object" "lambda" {
  bucket = aws_s3_bucket.artifacts.id
  key = "lambda/insurance-lambda.zip"
  source = var.lambda_zip_path
  etag = filemd5(var.lambda_zip_path)
  server_side_encryption = "AES256"
}
resource "aws_s3_bucket" "evidence" {
  bucket_prefix = format("%s-evidence-",var.prefix)
  force_destroy = false
}
resource "aws_s3_bucket_public_access_block" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  block_public_acls = true
  block_public_policy = true
  ignore_public_acls = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_server_side_encryption_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_s3_bucket_versioning" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_cors_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["POST"]
    allowed_origins = [local.origin]
    max_age_seconds = 3600
  }
}
resource "aws_s3_bucket" "web" {
  bucket_prefix = format("%s-web-",var.prefix)
  force_destroy = false
}
resource "aws_s3_bucket_public_access_block" "web" {
  bucket = aws_s3_bucket.web.id
  block_public_acls = true
  block_public_policy = true
  ignore_public_acls = true
  restrict_public_buckets = true
}
resource "aws_cloudfront_origin_access_control" "oac" {
  name = format("%s-oac",var.prefix)
  origin_access_control_origin_type = "s3"
  signing_behavior = "always"
  signing_protocol = "sigv4"
}
resource "aws_cloudfront_distribution" "web" {
  enabled = true
  default_root_object = "index.html"
  price_class = "PriceClass_100"
  origin {
    domain_name = aws_s3_bucket.web.bucket_regional_domain_name
    origin_id = "web"
    origin_access_control_id = aws_cloudfront_origin_access_control.oac.id
  }
  default_cache_behavior {
    target_origin_id = "web"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods = ["GET","HEAD"]
    cached_methods = ["GET","HEAD"]
    compress = true
    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }
    min_ttl = 0
    default_ttl = 3600
    max_ttl = 86400
  }
  custom_error_response {
    error_code = 403
    response_code = 200
    response_page_path = "/index.html"
  }
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  viewer_certificate { cloudfront_default_certificate = true }
}
data "aws_iam_policy_document" "web" {
  statement {
    actions = ["s3:GetObject"]
    resources = [format("%s/*",aws_s3_bucket.web.arn)]
    principals {
      type = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test = "StringEquals"
      variable = "AWS:SourceArn"
      values = [aws_cloudfront_distribution.web.arn]
    }
  }
}
resource "aws_s3_bucket_policy" "web" {
  bucket = aws_s3_bucket.web.id
  policy = data.aws_iam_policy_document.web.json
}
resource "aws_cognito_user_pool" "users" {
  name = format("%s-users",var.prefix)
  username_attributes = ["email"]
  auto_verified_attributes = ["email"]
  username_configuration { case_sensitive = false }
  password_policy {
    minimum_length = 12
    require_lowercase = true
    require_uppercase = true
    require_numbers = true
    require_symbols = true
  }
  admin_create_user_config { allow_admin_create_user_only = false }
  mfa_configuration = "OPTIONAL"
  software_token_mfa_configuration { enabled = true }
  account_recovery_setting {
    recovery_mechanism {
      name = "verified_email"
      priority = 1
    }
  }
}
resource "aws_cognito_user_pool_client" "web" {
  name = format("%s-spa",var.prefix)
  user_pool_id = aws_cognito_user_pool.users.id
  generate_secret = false
  explicit_auth_flows = ["ALLOW_USER_SRP_AUTH","ALLOW_REFRESH_TOKEN_AUTH"]
  prevent_user_existence_errors = "ENABLED"
}
resource "aws_cognito_user_group" "assessor" {
  name = "assessor"
  user_pool_id = aws_cognito_user_pool.users.id
}
resource "aws_sqs_queue" "dlq" {
  name = format("%s-dlq",var.prefix)
  message_retention_seconds = 1209600
}
resource "aws_sqs_queue" "jobs" {
  name = format("%s-jobs",var.prefix)
  visibility_timeout_seconds = 1200
  redrive_policy = jsonencode({deadLetterTargetArn=aws_sqs_queue.dlq.arn,maxReceiveCount=3})
}
data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}
resource "aws_iam_role" "lambda" {
  name = format("%s-lambda",var.prefix)
  assume_role_policy = data.aws_iam_policy_document.assume.json
}
resource "aws_iam_role_policy_attachment" "basic" {
  role = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
resource "aws_iam_role_policy_attachment" "vpc" {
  role = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}
data "aws_iam_policy_document" "app" {
  statement {
    actions = ["s3:GetObject","s3:PutObject","s3:DeleteObject"]
    resources = [format("%s/*",aws_s3_bucket.evidence.arn)]
  }
  statement {
    actions = ["s3:ListBucket"]
    resources = [aws_s3_bucket.evidence.arn]
  }
  statement {
    actions = ["secretsmanager:GetSecretValue"]
    resources = [aws_db_instance.db.master_user_secret[0].secret_arn]
  }
  statement {
    actions = ["sqs:SendMessage","sqs:ReceiveMessage","sqs:DeleteMessage","sqs:GetQueueAttributes"]
    resources = [aws_sqs_queue.jobs.arn]
  }
  statement {
    actions = ["textract:DetectDocumentText","bedrock:InvokeModel"]
    resources = ["*"]
  }
}
resource "aws_iam_role_policy" "app" {
  role = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.app.json
}
resource "aws_cloudwatch_log_group" "api" {
  name = format("/aws/lambda/%s-api",var.prefix)
  retention_in_days = 14
}
resource "aws_cloudwatch_log_group" "worker" {
  name = format("/aws/lambda/%s-worker",var.prefix)
  retention_in_days = 14
}
resource "aws_lambda_function" "api" {
  function_name = format("%s-api",var.prefix)
  s3_bucket = aws_s3_bucket.artifacts.id
  s3_key = aws_s3_object.lambda.key
  source_code_hash = filebase64sha256(var.lambda_zip_path)
  runtime = "python3.12"
  handler = "app.main.handler"
  role = aws_iam_role.lambda.arn
  timeout = 45
  memory_size = 1024
  vpc_config {
    subnet_ids = [aws_subnet.a.id,aws_subnet.b.id]
    security_group_ids = [aws_security_group.fn.id]
  }
  environment { variables = local.env }
  depends_on = [aws_iam_role_policy_attachment.vpc,aws_iam_role_policy_attachment.basic,aws_iam_role_policy.app]
}
resource "aws_lambda_function" "worker" {
  function_name = format("%s-worker",var.prefix)
  s3_bucket = aws_s3_bucket.artifacts.id
  s3_key = aws_s3_object.lambda.key
  source_code_hash = filebase64sha256(var.lambda_zip_path)
  runtime = "python3.12"
  handler = "app.worker.handler"
  role = aws_iam_role.lambda.arn
  timeout = 180
  memory_size = 2048
  vpc_config {
    subnet_ids = [aws_subnet.a.id,aws_subnet.b.id]
    security_group_ids = [aws_security_group.fn.id]
  }
  environment { variables = local.env }
  depends_on = [aws_iam_role_policy_attachment.vpc,aws_iam_role_policy_attachment.basic,aws_iam_role_policy.app]
}
resource "aws_lambda_event_source_mapping" "jobs" {
  event_source_arn = aws_sqs_queue.jobs.arn
  function_name = aws_lambda_function.worker.arn
  batch_size = 1
  function_response_types = ["ReportBatchItemFailures"]
}
resource "aws_apigatewayv2_api" "api" {
  name = format("%s-http",var.prefix)
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins = [local.origin]
    allow_methods = ["GET","POST","OPTIONS"]
    allow_headers = ["authorization","content-type"]
  }
}
resource "aws_apigatewayv2_integration" "api" {
  api_id = aws_apigatewayv2_api.api.id
  integration_type = "AWS_PROXY"
  integration_uri = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}
resource "aws_apigatewayv2_route" "default" {
  api_id = aws_apigatewayv2_api.api.id
  route_key = "$default"
  target = format("integrations/%s",aws_apigatewayv2_integration.api.id)
}
resource "aws_apigatewayv2_stage" "default" {
  api_id = aws_apigatewayv2_api.api.id
  name = "$default"
  auto_deploy = true
}
resource "aws_lambda_permission" "api" {
  statement_id = "AllowHttpApi"
  action = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal = "apigateway.amazonaws.com"
  source_arn = format("%s/*/*",aws_apigatewayv2_api.api.execution_arn)
}
output "api_url" { value = aws_apigatewayv2_api.api.api_endpoint }
output "website_url" { value = local.origin }
output "web_bucket" { value = aws_s3_bucket.web.id }
output "evidence_bucket" { value = aws_s3_bucket.evidence.id }
output "cloudfront_id" { value = aws_cloudfront_distribution.web.id }
output "cognito_pool_id" { value = aws_cognito_user_pool.users.id }
output "cognito_client_id" { value = aws_cognito_user_pool_client.web.id }
output "db_host" { value = aws_db_instance.db.address }
