# GitHub Actions -> AWS deployment (single AWS account)

This repository includes **.github/workflows/deploy-aws-dev.yml**. It deploys to your EXISTING AWS account with temporary OpenID Connect credentials. Do NOT use the root user or put root access keys in GitHub.

The workflow performs Python tests, React build (demo mode OFF), Lambda packaging, API+worker Lambda updates, S3 frontend upload, CloudFront cache invalidation and an API health check. It is **manual-first**, and does not execute Terraform apply/destroy.

## 1. Secure root; make your own administrator identity

AWS Console -> IAM Identity Center -> configure your own admin account/permission set for normal work. Enable MFA on your root user and the administrative identity. Keep root for account-level emergencies only; remove root access keys if any exist. You do not need teammates or a second AWS account.

Console: https://console.aws.amazon.com/
Select Asia Pacific (Sydney), ap-southeast-2. Set a billing budget and cost alerts first; alerts do not cap spending.

## 2. Bootstrap Terraform exactly once

If Terraform infrastructure has **not** already been deployed, install Git, Docker, Python 3.12, Node 22, Terraform >=1.6 and AWS CLI v2. Use an AWS CLI IAM Identity Center profile for infrastructure provisioning:

    aws configure sso --profile insurance-dev
    aws sso login --profile insurance-dev
    export AWS_PROFILE=insurance-dev
    aws sts get-caller-identity

Then from repository root:

    python infrastructure/scripts/build_lambda.py
    terraform -chdir=infrastructure/terraform init
    terraform -chdir=infrastructure/terraform fmt
    terraform -chdir=infrastructure/terraform validate
    terraform -chdir=infrastructure/terraform plan -out=dev.tfplan
    terraform -chdir=infrastructure/terraform apply dev.tfplan

Review the plan before apply. Terraform creates NAT gateway and RDS which accrue charges while idle. Initial Terraform state is local and gitignored: keep it secured and backed up. Before multiple team members can deploy infrastructure, migrate to an encrypted remote S3 backend with locking. If infrastructure already exists, **reuse that exact state**, never apply from an empty workspace.

Get your resource IDs:

    terraform -chdir=infrastructure/terraform output

## 3. Create IAM GitHub OIDC provider

From your non-root AWS admin console:
1. IAM -> Identity providers -> Add provider -> OpenID Connect.
2. Provider URL: https://token.actions.githubusercontent.com
3. Audience: sts.amazonaws.com
4. Create it once per AWS account; reuse if existing.
5. IAM -> Roles -> Create role -> Web identity -> select provider and audience.
6. Name it insurance-github-deploy-dev.
7. Trust relationships -> Edit trust policy. Replace AWS_ACCOUNT_ID with your AWS 12-digit account ID:

~~~json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::AWS_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": "repo:kevanly-GB/ai-insurance-valuation:environment:aws-dev"
      }
    }
  }]
}
~~~

**Important:** The trust condition matches the GitHub environment aws-dev. ALSO restrict that environment to deployments from the main branch in GitHub Settings. Do not use a wildcard repository subject. The role is not an administrator and cannot change IAM or create a database.

## 4. Attach least-privilege deployment IAM policy

Create an IAM custom policy attached to insurance-github-deploy-dev, replacing WEB_BUCKET, ARTIFACT_BUCKET, API_FUNCTION, WORKER_FUNCTION, CLOUDFRONT_ID and AWS_ACCOUNT_ID using your Terraform outputs.

~~~json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DeploymentBucketListing",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::WEB_BUCKET",
        "arn:aws:s3:::ARTIFACT_BUCKET"
      ]
    },
    {
      "Sid": "DeployWebAndLambdaCode",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": [
        "arn:aws:s3:::WEB_BUCKET/*",
        "arn:aws:s3:::ARTIFACT_BUCKET/lambda/*"
      ]
    },
    {
      "Sid": "UpdateOnlyAppLambdaCode",
      "Effect": "Allow",
      "Action": ["lambda:UpdateFunctionCode", "lambda:GetFunctionConfiguration"],
      "Resource": [
        "arn:aws:lambda:ap-southeast-2:AWS_ACCOUNT_ID:function:API_FUNCTION",
        "arn:aws:lambda:ap-southeast-2:AWS_ACCOUNT_ID:function:WORKER_FUNCTION"
      ]
    },
    {
      "Sid": "InvalidateOnlyApplicationCloudFront",
      "Effect": "Allow",
      "Action": ["cloudfront:CreateInvalidation"],
      "Resource": "arn:aws:cloudfront::AWS_ACCOUNT_ID:distribution/CLOUDFRONT_ID"
    }
  ]
}
~~~

Use the minimum access for application deployments. Do not attach AdministratorAccess or use static access keys.

## 5. Configure GitHub

Open repository **kevanly-GB/ai-insurance-valuation** -> Settings -> Environments -> New environment named **aws-dev**. Set Deployment branches/tags to **Selected branches: main**. If an approval rule is available, optionally require approval; if you are the only reviewer, avoid preventing your own deployments.

Then Settings -> Secrets and variables -> Actions -> Variables -> New repository variable. Add the following:

| Variable | Value |
|---|---|
| AWS_DEPLOY_ROLE_ARN | arn:aws:iam::AWS_ACCOUNT_ID:role/insurance-github-deploy-dev |
| AWS_FRONTEND_BUCKET | Terraform output web_bucket |
| AWS_ARTIFACT_BUCKET | Terraform output artifact_bucket |
| AWS_CLOUDFRONT_ID | Terraform output cloudfront_id |
| AWS_API_URL | Terraform output api_url |
| AWS_COGNITO_POOL_ID | Terraform output cognito_pool_id |
| AWS_COGNITO_CLIENT_ID | Terraform output cognito_client_id |
| AWS_API_FUNCTION | Terraform output api_lambda_name |
| AWS_WORKER_FUNCTION | Terraform output worker_lambda_name |
| AUTO_DEPLOY | false |

No AWS_SECRET_ACCESS_KEY or AWS_ACCESS_KEY_ID is required. Client IDs, bucket names, URLs and role ARN are non-secret identifiers. **AUTO_DEPLOY must be a repository variable** because it is evaluated as a job condition before the job enters the environment.

## 6. Run your first deployment

After reviewing and merging the pipeline pull request into **main**, open GitHub -> Actions -> **Deploy application to AWS (dev)** -> Run workflow -> select main -> Run workflow.

The deploy workflow must be present on default branch to enable GitHub's manual Run workflow feature.

Check job output for deployment errors and ensure /health returns status ok. In AWS inspect CloudWatch logs for the two Lambdas. Get the website URL with:

    terraform -chdir=infrastructure/terraform output -raw website_url

Test with *synthetic* insurance data and Cognito claimant/assessor accounts.

## 7. Enable automatic deployment later

After one successful manual deployment, change repository variable **AUTO_DEPLOY=true**. A push to main that changes frontend/, backend/, Lambda packaging script or deployment workflow triggers the deployment. Pull requests only run CI tests; deploying is a separate workflow. Keep feature branches and review PRs first.

## 8. Known caveats

- This pipeline deploys application ZIP and compiled frontend ONLY. It does not create infrastructure; initial Terraform must be performed by your human admin login.
- Subsequent Terraform apply using old ZIP state might revert a Lambda code update. Coordinate Terraform and CI updates or use lifecycle ignore_changes for code once pipeline owns deployments.
- The current template is a capstone MVP. It lacks production-grade malicious-document scanning, enterprise IAM reviews, exhaustive integration tests, and compliant handling of real claim records.
- NAT gateway, RDS and other AWS services can charge even if no one visits the website. After the capstone, destroy from the original Terraform state and clear versioned S3 buckets as required.

References:
- AWS root user best practices: https://docs.aws.amazon.com/IAM/latest/UserGuide/root-user-best-practices.html
- GitHub OIDC for AWS: https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws
- GitHub environments: https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
