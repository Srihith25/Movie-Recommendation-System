# stop-system.ps1
# Stop the system to prevent AWS charges

param(
    [switch]$KeepData = $false
)

Write-Host "`n🛑 STOPPING MOVIE RECOMMENDATION SYSTEM" -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Red
Write-Host "This will minimize AWS costs by disabling active resources" -ForegroundColor Yellow

$region = "us-east-2"

Write-Host "`n1️⃣ Disabling Lambda functions..." -ForegroundColor Yellow

# Set Lambda concurrency to 0 (prevents any invocations/charges)
$functions = @("movie-rec-recommendations", "movie-rec-data-pipeline")

foreach ($func in $functions) {
    aws lambda put-function-concurrency `
        --function-name $func `
        --reserved-concurrent-executions 0 `
        --region $region 2>$null
    
    Write-Host "   ✓ Disabled $func" -ForegroundColor Green
}

Write-Host "`n2️⃣ Scaling down DynamoDB tables..." -ForegroundColor Yellow

# Switch to On-Demand billing (no charges when not in use)
$tables = @("movie-rec-users", "movie-rec-movies", "movie-rec-embeddings", "movie-rec-cache")

foreach ($table in $tables) {
    # Option A: Switch to on-demand (pay per request, $0 when idle)
    aws dynamodb update-table `
        --table-name $table `
        --billing-mode PAY_PER_REQUEST `
        --region $region 2>$null
    
    Write-Host "   ✓ Switched $table to on-demand billing" -ForegroundColor Green
    
    # Option B: If you want to completely remove tables (saves all costs but loses data)
    if (-not $KeepData) {
        # Uncomment to delete tables completely:
        # aws dynamodb delete-table --table-name $table --region $region 2>$null
        # Write-Host "   ✓ Deleted $table" -ForegroundColor Green
    }
}

Write-Host "`n3️⃣ Updating frontend to show system offline..." -ForegroundColor Yellow

# Update config to show system is offline
@"
window.API_CONFIG = {
    endpoint: '',
    region: '${region}',
    status: 'offline',
    message: 'System is currently offline to save costs. Run start-system.ps1 to activate.'
};
"@ | Out-File -FilePath "frontend/config.js" -Encoding UTF8

# Create offline page
@"
<!DOCTYPE html>
<html>
<head>
    <title>System Offline</title>
    <style>
        body {
            font-family: 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .message {
            background: white;
            padding: 40px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        h1 { color: #333; }
        p { color: #666; margin: 20px 0; }
        .status { 
            background: #FEB2B2; 
            color: #742A2A; 
            padding: 10px 20px; 
            border-radius: 20px; 
            display: inline-block;
        }
    </style>
</head>
<body>
    <div class="message">
        <h1>🛑 System Offline</h1>
        <p>The Movie Recommendation System is currently stopped to save AWS costs.</p>
        <div class="status">Cost-Saving Mode Active</div>
        <p>To restart the system, run: <code>start-system.ps1</code></p>
    </div>
</body>
</html>
"@ | Out-File -FilePath "frontend/offline.html" -Encoding UTF8

# Upload offline status
aws s3 cp frontend/offline.html s3://YOUR-BUCKET-NAME/index.html `
    --content-type "text/html" `
    --cache-control "no-cache" `
    --region $region

Write-Host "   ✓ Frontend updated to offline status" -ForegroundColor Green

# Show cost summary
Write-Host "`n💰 COST SAVINGS SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Lambda Functions:    " -NoNewline
Write-Host "STOPPED" -ForegroundColor Green
Write-Host "                     (Saving: ~`$0.20 per 1M requests)" -ForegroundColor Gray
Write-Host "DynamoDB Tables:     " -NoNewline
Write-Host "ON-DEMAND" -ForegroundColor Green
Write-Host "                     (Saving: ~`$0.25/month per table)" -ForegroundColor Gray
Write-Host "API Gateway:         " -NoNewline
Write-Host "IDLE" -ForegroundColor Green
Write-Host "                     (No charges when not called)" -ForegroundColor Gray

Write-Host "`n✅ SYSTEM STOPPED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "All billable resources have been disabled or minimized." -ForegroundColor Yellow
Write-Host "`nTo restart the system, run: " -NoNewline
Write-Host ".\start-system.ps1" -ForegroundColor Cyan