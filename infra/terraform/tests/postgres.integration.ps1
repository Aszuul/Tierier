[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [string]$Region = "us-central1",
    [string]$InstanceName = "tierier-postgres-vm",
    [string]$NetworkName = "tierier-vpc",
    [string]$SubnetCidr = "10.10.0.0/24",
    [string]$DatabaseName = "tierier"
)

$ErrorActionPreference = "Stop"

if ($DatabaseName -notmatch '^[a-z][a-z0-9_]{0,62}$') {
    throw "DatabaseName must start with a lowercase letter and contain only lowercase letters, digits, and underscores."
}

$zone = "$Region-a"
$instanceJson = & gcloud compute instances describe $InstanceName --project $ProjectId --zone $zone --format json
if ($LASTEXITCODE -ne 0) {
    throw "Unable to describe VM '$InstanceName'. Check gcloud authentication, project access, and zone."
}
$instance = $instanceJson | ConvertFrom-Json

if ($instance.status -ne "RUNNING") {
    throw "Expected VM '$InstanceName' to be RUNNING; actual status: $($instance.status)."
}
if (-not $instance.machineType.EndsWith("/machineTypes/e2-micro")) {
    throw "Expected VM '$InstanceName' to use e2-micro; actual machine type: $($instance.machineType)."
}
if (-not $instance.networkInterfaces[0].networkIP) {
    throw "VM '$InstanceName' has no private IP address."
}

$firewallName = "$NetworkName-postgres"
$firewallJson = & gcloud compute firewall-rules describe $firewallName --project $ProjectId --format json
if ($LASTEXITCODE -ne 0) {
    throw "Unable to describe PostgreSQL firewall '$firewallName'."
}
$firewall = $firewallJson | ConvertFrom-Json
$postgresRule = $firewall.allowed | Where-Object {
    $_.IPProtocol -eq "tcp" -and $_.ports -contains "5432"
}
if (-not $postgresRule -or $firewall.sourceRanges.Count -ne 1 -or $firewall.sourceRanges[0] -ne $SubnetCidr) {
    throw "PostgreSQL firewall must allow TCP 5432 only from subnet $SubnetCidr."
}

$sql = "SELECT current_setting('listen_addresses') || '|' || current_setting('port') || '|' || EXISTS (SELECT 1 FROM pg_database WHERE datname = '$DatabaseName')"
$remoteCommand = "sudo systemctl is-active postgresql && sudo -u postgres psql --no-align --tuples-only --command `"$sql`""
$remoteOutput = & gcloud compute ssh $InstanceName --project $ProjectId --zone $zone --tunnel-through-iap --command $remoteCommand --quiet
if ($LASTEXITCODE -ne 0) {
    throw "PostgreSQL service check over IAP SSH failed. Verify IAP access and VM startup completion."
}
if (($remoteOutput -join "`n") -notmatch '(?m)^\*\|5432\|t\s*$') {
    throw "PostgreSQL is not listening on the expected port or database '$DatabaseName' does not exist. Output: $($remoteOutput -join ' ')"
}

Write-Output "Integration checks passed for $InstanceName ($($instance.networkInterfaces[0].networkIP)): VM, firewall, and PostgreSQL database are ready."