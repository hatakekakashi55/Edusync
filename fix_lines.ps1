$filePath = "c:\Users\wayne\Documents\edusync-babu\communication_stage.html"
$fixFile = "c:\Users\wayne\Documents\edusync-babu\full_script_fix.js"
$lines = Get-Content $filePath -Encoding UTF8

$startLine = -1
$endLine = -1

for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "currentAIChatMode = mode;") {
        $startLine = $i + 2
    }
    if ($lines[$i] -match "// 17. PRONUNCIATION GUIDE") {
        $endLine = $i
    }
}

if ($startLine -ne -1 -and $endLine -ne -1 -and $endLine -gt $startLine) {
    $before = $lines[0..($startLine)] # Keep currentAIChatMode line
    $fix = Get-Content $fixFile -Encoding UTF8
    $after = $lines[$endLine..($lines.Count-1)]
    
    # Combined with UTF8
    $finalLines = $before + $fix + $after
    $finalLines | Out-File $filePath -Encoding UTF8
    Write-Host "File fixed successfully from $startLine to $endLine."
} else {
    Write-Host "Could not find lines. Start: $startLine, End: $endLine"
}
