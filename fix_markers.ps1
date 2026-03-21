$filePath = "c:\Users\wayne\Documents\edusync-babu\communication_stage.html"
$fixFile = "c:\Users\wayne\Documents\edusync-babu\full_script_fix.js"
$content = [System.IO.File]::ReadAllText($filePath)
$newBlock = [System.IO.File]::ReadAllText($fixFile)

# Find boundaries
$startMarker = "            currentAIChatMode = mode;"
$endMarker = "// ==========================================================\r\n        // 17. PRONUNCIATION GUIDE"

$startIndex = $content.IndexOf($startMarker) + $startMarker.Length + 10 # skip some lines
$endIndex = $content.IndexOf($endMarker)

if ($startIndex -gt 10 -and $endIndex -gt $startIndex) {
    $before = $content.Substring(0, $startIndex)
    $after = $content.Substring($endIndex)
    $finalContent = $before + "\r\n" + $newBlock + "\r\n        " + $after
    [System.IO.File]::WriteAllText($filePath, $finalContent, [System.Text.Encoding]::UTF8)
    Write-Host "Success: File updated."
} else {
    Write-Host "Markers not found or indices invalid. Start: $startIndex, End: $endIndex"
}
