output "artifact_bucket" {
  description = "S3 bucket used to upload Lambda deployment ZIPs"
  value       = aws_s3_bucket.artifacts.id
}

output "api_lambda_name" {
  description = "Name of FastAPI Lambda function"
  value       = aws_lambda_function.api.function_name
}

output "worker_lambda_name" {
  description = "Name of evidence processing Lambda function"
  value       = aws_lambda_function.worker.function_name
}
