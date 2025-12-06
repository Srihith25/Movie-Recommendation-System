# status-system.ps1
# Check the current status of the system

Write-Host "`n📊 SYSTEM STATUS CHECK" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$region = "us-east-2"

# Check Lambda functions
Write-Host "`nLambda Functions:" -ForegroundColor Yellow
$functions = @("movie-rec-recommendations", "movie-rec-data-pipeline")

foreach ($func in $functions) {
    $concurrency = aws lambda get-function-concurrency `
        --function-name $func `
        --region $region `
        --output json 2>$null | ConvertFrom-Json
    
    if ($concurrency.ReservedConcurrentExecutions -eq 0) {
        Write-Host "  ❌ $func : DISABLED" -ForegroundColor Red
    } else {
        Write-Host "  ✅ $func : ACTIVE" -ForegroundColor Green
    }
}

# Check DynamoDB tables
Write-Host "`nDynamoDB Tables:" -ForegroundColor Yellow
$tables = aws dynamodb list-tables --region $region --output json | ConvertFrom-Json

foreach ($table in $tables.TableNames) {
    if ($table -like "movie-rec-*") {
        $tableInfo = aws dynamodb describe-table `
            --table-name $table `
            --region $region `
            --output json | ConvertFrom-Json
        
        $billing = $tableInfo.Table.BillingModeSummary.BillingMode
        if ($billing -eq "PAY_PER_REQUEST") {
            Write-Host "  💤 ${table}: ON-DEMAND (No cost when idle)" -ForegroundColor Yellow
        } else {
            $rcu = $tableInfo.Table.ProvisionedThroughput.ReadCapacityUnits
            $wcu = $tableInfo.Table.ProvisionedThroughput.WriteCapacityUnits
            Write-Host "  💰 ${table}: PROVISIONED (${rcu}R/${wcu}W - Incurring charges)" -ForegroundColor Red
        }
    }
}

# Check S3 bucket
Write-Host "`nS3 Bucket:" -ForegroundColor Yellow
$objects = aws s3 ls s3://YOUR-BUCKET-NAME/ --region $region
Write-Host "  📦 YOUR-BUCKET-NAME: " -NoNewline
Write-Host "ACTIVE" -ForegroundColor Green
Write-Host "     Files: $(($objects | Measure-Object).Count)" -ForegroundColor Gray

# Check API Gateway
Write-Host "`nAPI Gateway:" -ForegroundColor Yellow
$apis = aws apigateway get-rest-apis --region $region --output json | ConvertFrom-Json
$movieApi = $apis.items | Where-Object { $_.name -eq "MovieRecAPI" }

if ($movieApi) {
    Write-Host "  🌐 MovieRecAPI: " -NoNewline
    Write-Host "DEPLOYED" -ForegroundColor Green
    Write-Host "     Endpoint: https://$($movieApi.id).execute-api.${region}.amazonaws.com/prod" -ForegroundColor Gray
}

# Estimate current costs
Write-Host "`n💵 ESTIMATED MONTHLY COSTS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$lambdaCost = 0
$dynamoCost = 0
$s3Cost = 0.01  # Minimal S3 storage

# Check if Lambdas are active
foreach ($func in $functions) {
    $concurrency = aws lambda get-function-concurrency `
        --function-name $func `
        --region $region `
        --output json 2>$null | ConvertFrom-Json
    
    if ($concurrency.ReservedConcurrentExecutions -ne 0) {
        $lambdaCost += 0.00  # Free tier covers 1M requests
    }
}

# Check DynamoDB billing
foreach ($table in $tables.TableNames) {
    if ($table -like "movie-rec-*") {
        $tableInfo = aws dynamodb describe-table `
            --table-name $table `
            --region $region `
            --output json 2>$null | ConvertFrom-Json
        
        if ($tableInfo.Table.BillingModeSummary.BillingMode -ne "PAY_PER_REQUEST") {
            $dynamoCost += 0.25  # Approximate provisioned cost per table
        }
    }
}

Write-Host "Lambda Functions:  `$$('{0:N2}' -f $lambdaCost)/month" -ForegroundColor $(if($lambdaCost -eq 0){"Green"}else{"Yellow"})
Write-Host "DynamoDB Tables:   `$$('{0:N2}' -f $dynamoCost)/month" -ForegroundColor $(if($dynamoCost -eq 0){"Green"}else{"Yellow"})
Write-Host "S3 Storage:        `$$('{0:N2}' -f $s3Cost)/month" -ForegroundColor Green
Write-Host "API Gateway:       `$0.00/month (within free tier)" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
$totalCost = $lambdaCost + $dynamoCost + $s3Cost
Write-Host "TOTAL ESTIMATED:   `$$('{0:N2}' -f $totalCost)/month" -ForegroundColor $(if($totalCost -lt 0.50){"Green"}else{"Red"})

if ($totalCost -gt 0) {
    Write-Host "`n💡 TIP: Run .\stop-system.ps1 to minimize costs" -ForegroundColor Yellow
}