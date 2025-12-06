# movie-rec.ps1 - Master control script
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("start", "stop", "status", "clean", "test")]
    [string]$Action
)

switch ($Action) {
    "start" {
        .\start-system.ps1
    }
    "stop" {
        .\stop-system.ps1
    }
    "status" {
        .\status-system.ps1
    }
    "clean" {
        .\clean-system.ps1
    }
    "test" {
        $apiId = (aws apigateway get-rest-apis --region us-east-2 --query "items[?name=='MovieRecAPI'].id" --output text)
        $url = "https://${apiId}.execute-api.us-east-2.amazonaws.com/prod/users/1/recommendations"
        Invoke-RestMethod -Uri $url | ConvertTo-Json
    }
    default {
        Write-Host "Usage: .\movie-rec.ps1 -Action [start|stop|status|clean|test]"
    }
}