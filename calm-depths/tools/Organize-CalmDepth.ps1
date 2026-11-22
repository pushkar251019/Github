<#
  Organize-CalmDepth.ps1  -  tidies the Calm Depth channel folder.

  STEP 1 (preview, changes nothing):
      powershell -ExecutionPolicy Bypass -File .\Organize-CalmDepth.ps1
  STEP 2 (do it):
      powershell -ExecutionPolicy Bypass -File .\Organize-CalmDepth.ps1 -Apply
  UNDO (puts every file back where it was):
      powershell -ExecutionPolicy Bypass -File .\Organize-CalmDepth.ps1 -Undo

  Nothing is deleted. Every move is written to _organize_log.csv so it can be undone.
#>
param(
  [string]$Root = "C:\Users\pushk\OneDrive\Desktop\Claude\Calm Depth",
  [switch]$Apply,
  [switch]$Undo
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $Root)) { throw "Folder not found: $Root" }
$Log = Join-Path $Root "_organize_log.csv"

# ---------- UNDO ----------
if ($Undo) {
  if (-not (Test-Path -LiteralPath $Log)) { throw "No log found, nothing to undo." }
  $rows = @(Import-Csv -LiteralPath $Log)
  [array]::Reverse($rows)
  foreach ($r in $rows) {
    if (Test-Path -LiteralPath $r.To) {
      $dir = Split-Path -Parent $r.From
      if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
      Move-Item -LiteralPath $r.To -Destination $r.From
      Write-Host "restored  $($r.From)"
    }
  }
  Remove-Item -LiteralPath $Log
  Write-Host "`nUndo complete. (Empty new folders are left in place; delete them if you like.)"
  return
}

# ---------- folder plan ----------
$F = [ordered]@{
  Brand      = "01_Brand"            # logo, emblem, watermark, profile picture
  Overlays   = "02_Overlays"         # subscribe animation, other transparent overlays
  Intros     = "03_Intros"           # finished intro clips
  Voice      = "04_Voice"            # narrator voice files and samples
  RawVideo   = "05_Raw_Videos"       # Pixabay B-roll (royalty free)
  RawAudio   = "06_Raw_Audio"        # ambience / sound effects (royalty free)
  Thumbnails = "07_Thumbnails"
  Finals     = "08_Final_Videos"     # exported videos ready for YouTube
  Upload     = "09_Upload_Notes"     # titles, descriptions, captions (.md .txt .srt)
  Projects   = "10_Editing_Projects" # CapCut / editor project files
  Other      = "99_To_Sort"          # anything the rules could not place
}

$videoExt = ".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"
$audioExt = ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"
$imageExt = ".jpg", ".jpeg", ".png", ".webp", ".gif"
$textExt  = ".md", ".txt", ".srt", ".vtt", ".docx", ".pdf", ".csv"
$projExt  = ".prproj", ".drp", ".veg", ".capcut", ".json"

function Get-Target($file) {
  $n = $file.Name.ToLower(); $e = $file.Extension.ToLower()
  if ($n -match "thumb")                                              { return $F.Thumbnails }
  if ($n -match "subscribe|overlay|lower.?third")                     { return $F.Overlays }
  if ($n -match "logo|emblem|watermark|profile|brandstamp|banner")    { return $F.Brand }
  if ($n -match "intro" -and $videoExt -contains $e)                  { return $F.Intros }
  if ($n -match "narrator|voice|sample_|elevenlabs|el_[ab]")          { return $F.Voice }
  if ($n -match "final|upload" -and $videoExt -contains $e)           { return $F.Finals }
  if ($textExt -contains $e)                                          { return $F.Upload }
  if ($projExt -contains $e)                                          { return $F.Projects }
  if ($audioExt -contains $e)                                         { return $F.RawAudio }
  if ($videoExt -contains $e)                                         { return $F.RawVideo }
  if ($imageExt -contains $e)                                         { return $F.Brand }
  return $F.Other
}

# Simple, searchable names: strip the "CalmDepths_" prefix, spaces -> underscores,
# Pixabay downloads like "246688_medium.mp4" -> "Pixabay_246688.mp4".
function Get-CleanName($file) {
  $base = [IO.Path]::GetFileNameWithoutExtension($file.Name); $e = $file.Extension.ToLower()
  $base = $base -replace "^(?i)calm\s?depths?_", ""
  if ($base -match "^(\d{5,})_(tiny|small|medium|large)$") { $base = "Pixabay_$($Matches[1])" }
  elseif ($base -match "^[0-9a-f]{8}-(.+)$")               { $base = $Matches[1] }   # chat-upload prefix
  if ($base -match "^(.+?)-(\d{5,})$")                     { $base = "Pixabay_$($Matches[2])_$($Matches[1])" }  # pixabay audio
  $base = ($base -replace "[\s\-]+", "_" -replace "_+", "_").Trim("_")
  return "$base$e"
}

# Collect files: everything at the top level, plus anything inside an existing "raw ..." folder.
$known = @($F.Values)
$files = @(Get-ChildItem -LiteralPath $Root -File | Where-Object { $_.Name -ne "_organize_log.csv" -and $_.Name -notlike "Organize-CalmDepth*.ps1" })
$rawDirs = @(Get-ChildItem -LiteralPath $Root -Directory | Where-Object { $_.Name -match '(?i)(^|[\s_\-])raw([\s_\-]|$)' -and $known -notcontains $_.Name })
foreach ($d in $rawDirs) { $files += Get-ChildItem -LiteralPath $d.FullName -File -Recurse }
# Other loose folders (not ours, not raw) are reported, not touched.
$rawNames = @($rawDirs | ForEach-Object { $_.Name })
$otherDirs = @(Get-ChildItem -LiteralPath $Root -Directory | Where-Object { $known -notcontains $_.Name -and $rawNames -notcontains $_.Name })

$plan = foreach ($f in $files) {
  $t = Get-Target $f
  $inRaw = $rawDirs | Where-Object { $f.FullName.StartsWith($_.FullName + "\") }
  if ($inRaw -and $videoExt -contains $f.Extension.ToLower()) { $t = $F.RawVideo }
  elseif ($inRaw -and $audioExt -contains $f.Extension.ToLower()) { $t = $F.RawAudio }
  elseif ($inRaw) { $t = $F.RawVideo }   # anything else found in a raw folder stays with the raw footage
  [pscustomobject]@{ From = $f.FullName; To = Join-Path (Join-Path $Root $t) (Get-CleanName $f) }
}

# Never overwrite: add _2, _3 ... if a name is already taken.
$taken = @{}
foreach ($p in $plan) {
  $to = $p.To; $i = 2
  while ($taken.ContainsKey($to.ToLower()) -or ((Test-Path -LiteralPath $to) -and $to -ne $p.From)) {
    $to = Join-Path (Split-Path $p.To) ("{0}_{1}{2}" -f [IO.Path]::GetFileNameWithoutExtension($p.To), $i, [IO.Path]::GetExtension($p.To)); $i++
  }
  $taken[$to.ToLower()] = 1; $p.To = $to
}

Write-Host "`nCalm Depth folder: $Root`n"
$plan | Sort-Object To | ForEach-Object {
  "{0,-22} <- {1}" -f ((Split-Path (Split-Path $_.To) -Leaf)), ($_.From.Substring($Root.Length + 1) + "  =>  " + (Split-Path $_.To -Leaf))
}
if ($otherDirs) { Write-Host "`nFolders left untouched (move them by hand if needed): $($otherDirs.Name -join ', ')" }

if (-not $Apply) {
  Write-Host "`nPREVIEW ONLY - nothing moved. Run again with -Apply to do it."
  return
}

foreach ($k in $F.Keys) {
  $d = Join-Path $Root $F[$k]; if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Path $d | Out-Null }
}
$done = @()
foreach ($p in $plan) {
  if ($p.From -eq $p.To) { continue }
  Move-Item -LiteralPath $p.From -Destination $p.To
  $done += $p
}
$done | Export-Csv -LiteralPath $Log -NoTypeInformation -Append
# remove raw folders that are now empty
foreach ($d in $rawDirs) {
  if (-not (Get-ChildItem -LiteralPath $d.FullName -Recurse -File)) { Remove-Item -LiteralPath $d.FullName -Recurse }
}
# remove the 99_To_Sort folder if unused
$o = Join-Path $Root $F.Other
if ((Test-Path -LiteralPath $o) -and -not (Get-ChildItem -LiteralPath $o)) { Remove-Item -LiteralPath $o }
Write-Host "`nDone. Moved $($done.Count) files. Log: $Log (use -Undo to reverse)."
