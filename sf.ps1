[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsList
)

$cliScript = "c:\Users\juhai\Downloads\Slicer-main\cli.py"
& "C:\Python313\python.exe" $cliScript @ArgsList
