# clean-system.ps1
# Completely remove all resources (use with caution!)

param(
    [switch]$Confirm = $false
)

Write-Host "`n⚠️  WARNING: This will DELETE all resources!" -ForegroundColor Red

if (-not $Confirm) {
    $response = Read-Host "Type 'DELETE' to confirm complete system removal"
    if ($response -ne "DELETE") {
        Write-Host "Cleanup cancelled." -ForegroundColor Yellow
        return
    }
}

Write-Host "`n🗑️  REMOVING ALL RESOURCES..." -ForegroundColor Red

$region = "us-east-2"

# Delete Lambda functions
Write-Host "Deleting Lambda functions..." -ForegroundColor Yellow
aws lambda delete-function --function-name movie-rec-recommendations --region $region 2>$null
aws lambda delete-function --function-name movie-rec-data-pipeline --region $region 2>$null

# Delete DynamoDB tables
Write-Host "Deleting DynamoDB tables..." -ForegroundColor Yellow
$tables = @("movie-rec-users", "movie-rec-movies", "movie-rec-embeddings", "movie-rec-cache")
foreach ($table in $tables) {
    aws dynamodb delete-table --table-name $table --region $region 2>$null
}

# Delete API Gateway
Write-Host "Deleting API Gateway..." -ForegroundColor Yellow
$apis = aws apigateway get-rest-apis --region $region --output json | ConvertFrom-Json
$movieApi = $apis.items | Where-Object { $_.name -eq "MovieRecAPI" }
if ($movieApi) {
    aws apigateway delete-rest-api --rest-api-id $movieApi.id --region $region 2>$null
}

# Delete S3 bucket contents and bucket
Write-Host "Deleting S3 bucket..." -ForegroundColor Yellow
aws s3 rm s3://YOUR-BUCKET-NAME --recursive 2>$null
aws s3 rb s3://YOUR-BUCKET-NAME 2>$null

# Delete IAM role
Write-Host "Deleting IAM role..." -ForegroundColor Yellow
aws iam detach-role-policy `
    --role-name movie-rec-lambda-role `
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>$null
aws iam detach-role-policy `
    --role-name movie-rec-lambda-role `
    --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess 2>$null
aws iam delete-role --role-name movie-rec-lambda-role 2>$null

Write-Host "`n✅ All resources deleted!" -ForegroundColor Green
Write-Host "Your AWS account is clean. No further charges will occur." -ForegroundColor Yellow