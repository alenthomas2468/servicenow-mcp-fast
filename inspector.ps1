# ServiceNow MCP Inspector Launcher
# This script starts the MCP server with the MCP Inspector attached.

# Get the script's directory (project root)
$projectRoot = (Get-Location).Path -replace '\\', '/'

# Load environment variables from .env file
$envFile = "$projectRoot/.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^([^#=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($name, $value)
        }
    }
    Write-Host "Loaded environment from .env"
} else {
    Write-Host "Warning: .env file not found. Make sure to configure your ServiceNow credentials."
}

# Set the PYTHONPATH to include the 'src' directory
$env:PYTHONPATH = "$projectRoot/src"

# Use the virtual environment's Python with forward slashes for npx compatibility
$pythonPath = "$projectRoot/.venv/Scripts/python.exe"
$serverPath = "$projectRoot/src/servicenow_mcp/server.py"

# Run the inspector
npx @modelcontextprotocol/inspector $pythonPath $serverPath
