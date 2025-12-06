Write-Host "`n4️⃣ Updating frontend configuration..." -ForegroundColor Yellow

if ($apiId) {
    $configContent = @"
window.API_CONFIG = {
    endpoint: '$apiEndpoint',
    region: '$region',
    status: 'active'
};
"@

    # Write config.js
    $configContent | Out-File -FilePath "./frontend/config.js" -Encoding UTF8

    # Upload to S3
    aws s3 cp ./frontend/config.js s3://YOUR-BUCKET-NAME/config.js `
        --content-type "application/javascript" `
        --cache-control "no-cache" `
        --region $region

    aws s3 cp ./frontend/index.html s3://YOUR-BUCKET-NAME/index.html `
        --content-type "text/html" `
        --cache-control "no-cache" `
        --region $region

    Write-Host "   ✓ Frontend updated" -ForegroundColor Green
}
