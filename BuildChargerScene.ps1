param(
    [Parameter(Mandatory)][string]$ChargerArchive,
    [Parameter(Mandatory)][string]$StudioDirectory
)

$ErrorActionPreference = 'Stop'
$work = Join-Path $PSScriptRoot 'work'
$studio = (Resolve-Path -LiteralPath $StudioDirectory).Path
$lib = Join-Path $studio 'libs'
$config = Join-Path $studio 'ForzaTech Studio.runtimeconfig.json'
$version = (Get-Content -LiteralPath $config -Raw | ConvertFrom-Json).runtimeOptions.framework.version
$major = ($version -split '\.')[0]
$frameworkRoot = Join-Path $env:ProgramFiles 'dotnet\shared\Microsoft.NETCore.App'
$framework = Get-ChildItem -LiteralPath $frameworkRoot -Directory |
    Where-Object Name -Like "$major.*" | Sort-Object { [version]$_.Name } -Descending |
    Select-Object -First 1
if (!$framework) { throw "Install the .NET $major runtime used by ForzaTech Studio." }
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$installation = & $vswhere -latest -products '*' -requires Microsoft.Component.MSBuild -property installationPath
if (!$installation) { throw 'Visual Studio Build Tools were not found.' }
$csc = Join-Path $installation 'MSBuild\Current\Bin\Roslyn\csc.exe'
$references = @('System.Private.CoreLib.dll','System.Runtime.dll','System.Collections.dll',
    'System.Linq.dll','System.Numerics.Vectors.dll','System.Runtime.Loader.dll') |
    ForEach-Object { "/r:$($framework.FullName)\$_" }
$tool = Join-Path $work 'AddRoofUpgrades.exe'
& $csc /nologo /noconfig /nostdlib /langversion:latest @references "/r:$lib\ForzaTools.Shared.dll" `
    "/r:$lib\ForzaTools.Bundles.dll" "/out:$tool" (Join-Path $PSScriptRoot 'AddRoofUpgrades.cs')
if ($LASTEXITCODE -ne 0) { throw 'Could not compile the scene builder.' }
$name = 'DOD_ChargerSRT8_12'
$stock = Join-Path $work "stock-$name.carbin"
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path -LiteralPath $ChargerArchive).Path)
try {
    [System.IO.Compression.ZipFileExtensions]::ExtractToFile($zip.GetEntry("$name.carbin"), $stock, $true)
} finally {
    $zip.Dispose()
}
$placement = python -c "import sys; sys.path.insert(0, sys.argv[1]); from BuildPack import CHARGER_SHIFT; print(*CHARGER_SHIFT)" $PSScriptRoot
if ($LASTEXITCODE -ne 0) { throw 'Could not load the Charger placement.' }
$offsets = $placement -split ' '
dotnet exec --runtimeconfig $config $tool $lib $stock (Join-Path $work 'ALF_4C_14.carbin') `
    (Join-Path $work "$name.carbin") 1422000 $name @offsets
if ($LASTEXITCODE -ne 0) { throw 'Could not build or verify the Charger scene.' }
