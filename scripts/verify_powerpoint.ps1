#Requires -Version 7.3
<#
.SYNOPSIS
Render a read-only PPTX in installed PowerPoint and optionally test edits on a copy.
.DESCRIPTION
OutputDir must not exist. EditPlan accepts a JSON array, or a path containing one.
Operations: {"op":"text","name":"label","value":"New text","slide":1},
{"op":"move","name":"unit","dx_pt":9,"dy_pt":0},
{"op":"line_color","name":"edge","rgb":[255,0,0]}.
Requested edit names must be globally unique, including group children. Duplicate
names remain in read-only evidence. Slide defaults to 1.
Text bounds are PowerPoint TextRange bounds in slide points, not exact glyph masks.
No automatic rerouting, reconnection, port edits, application Quit, or process kill.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Artifact,
    [Parameter(Mandatory)][string]$OutputDir,
    [string]$EditPlan,
    [ValidateRange(320,8192)][int]$RenderWidth = 1600
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Release-Com($Object) {
    if ($null -ne $Object -and [Runtime.InteropServices.Marshal]::IsComObject($Object)) {
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($Object)
    }
}
function Get-Sha([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Write-Json([object]$Value,[string]$Path) {
    $Value | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $Path -Encoding utf8NoBOM
}
function Assert-Number($Value,[string]$Label) {
    if ($Value -is [bool] -or $Value -is [string] -or $null -eq $Value -or
        $Value -isnot [ValueType] -or -not [double]::IsFinite([double]$Value)) {
        throw "$Label must be a finite JSON number"
    }
}
function Read-Plan([string]$InputValue) {
    if ([string]::IsNullOrWhiteSpace($InputValue)) { return ,@() }
    $raw = $InputValue
    if (-not $InputValue.TrimStart().StartsWith('[')) {
        $raw = Get-Content -LiteralPath $InputValue -Raw -Encoding utf8
    }
    $plan = ConvertFrom-Json -InputObject $raw -AsHashtable -NoEnumerate
    if ($plan -isnot [array] -or $plan.Count -gt 2000) { throw 'EditPlan must be a JSON array with at most 2000 operations' }
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($op in $plan) {
        if ($op -isnot [Collections.IDictionary]) { throw 'Each edit operation must be an object' }
        if (-not $op.Contains('op') -or $op.op -notin @('text','move','line_color')) { throw 'Unsupported or missing edit op' }
        if (-not $op.Contains('name') -or $op.name -isnot [string] -or [string]::IsNullOrWhiteSpace($op.name)) { throw 'Each operation requires a nonempty name' }
        if (-not $op.Contains('slide')) { $op.slide = 1 }
        Assert-Number $op.slide 'slide'
        if ($op.slide -lt 1 -or [math]::Truncate([double]$op.slide) -ne $op.slide) { throw 'slide must be a positive integer' }
        $allowed = @('op','name','slide')
        switch ($op.op) {
            text {
                $allowed += 'value'
                if (-not $op.Contains('value') -or $op.value -isnot [string]) { throw 'text.value must be a string' }
            }
            move {
                $allowed += @('dx_pt','dy_pt')
                foreach ($axis in @('dx_pt','dy_pt')) {
                    if (-not $op.Contains($axis)) { throw "move.$axis is required" }
                    Assert-Number $op[$axis] "move.$axis"
                    if ([math]::Abs([double]$op[$axis]) -gt 10000) { throw "move.$axis exceeds 10000 points" }
                }
            }
            line_color {
                $allowed += 'rgb'
                if (-not $op.Contains('rgb') -or $op.rgb -isnot [array] -or $op.rgb.Count -ne 3) { throw 'line_color.rgb must contain three integers in 0..255' }
                foreach ($c in $op.rgb) {
                    Assert-Number $c 'rgb channel'
                    if ($c -lt 0 -or $c -gt 255 -or [math]::Truncate([double]$c) -ne $c) { throw 'rgb channels must be integers in 0..255' }
                }
            }
        }
        foreach ($key in $op.Keys) { if ($key -notin $allowed) { throw "Unsupported edit field: $key" } }
        if (-not $seen.Add("$($op.slide)|$($op.name)|$($op.op)")) { throw 'Duplicate operation on the same shape/property is ambiguous' }
    }
    return ,$plan
}
function Get-Binding($Shape) {
    $cf = $null; $endShape = $null; $beginShape = $null
    try {
        $cf = $Shape.ConnectorFormat
        $b = [ordered]@{name=[string]$Shape.Name;shape_id=[int]$Shape.Id;begin_connected=($cf.BeginConnected -eq -1);end_connected=($cf.EndConnected -eq -1);begin_name=$null;begin_shape_id=$null;begin_site=$null;end_name=$null;end_shape_id=$null;end_site=$null}
        if ($b.begin_connected) {
            $beginShape = $cf.BeginConnectedShape
            $b.begin_name = [string]$beginShape.Name; $b.begin_shape_id = [int]$beginShape.Id; $b.begin_site = [int]$cf.BeginConnectionSite
        }
        if ($b.end_connected) {
            $endShape = $cf.EndConnectedShape
            $b.end_name = [string]$endShape.Name; $b.end_shape_id = [int]$endShape.Id; $b.end_site = [int]$cf.EndConnectionSite
        }
        return $b
    } finally { Release-Com $beginShape; Release-Com $endShape; Release-Com $cf }
}
function Add-ShapeEntry($Shape,[int]$SlideIndex,[string[]]$Parents,$State,$SlideRecord,[double]$AncestorRotation=0,[int[]]$ParentIds=@(),[bool]$AncestorRotated=$false) {
    $name = [string]$Shape.Name
    # COM can report an inherited angle on children. Do not sum it a second time.
    $reportedRotation=[double]$Shape.Rotation
    $item = [ordered]@{name=$name;shape_id=[int]$Shape.Id;type=[int]$Shape.Type;parent_groups=@($Parents);parent_group_ids=@($ParentIds);box_pt=@([double]$Shape.Left,[double]$Shape.Top,[double]$Shape.Width,[double]$Shape.Height);rotation=$reportedRotation;ancestor_rotation=$AncestorRotation;ancestor_rotated=$AncestorRotated;rotation_composition_verified=(-not $AncestorRotated);text=''}
    if ($State.map.ContainsKey($name)) { [void]$State.ambiguous.Add($name) }
    else { $State.map.Add($name,[pscustomobject]@{shape=$Shape;slide=$SlideIndex;record=$item}) }
    $State.entries.Add($Shape)
    $SlideRecord.shapes.Add($item)
    if ($Shape.HasTextFrame -eq -1) {
        $frame = $null; $range = $null
        try {
            $frame = $Shape.TextFrame
            if ($frame.HasText -eq -1) {
                $range = $frame.TextRange; $item.text = [string]$range.Text
                $measurement=[ordered]@{name=$name;shape_id=[int]$Shape.Id;parent_groups=@($Parents);parent_group_ids=@($ParentIds);text=[string]$range.Text;box_pt=@([double]$range.BoundLeft,[double]$range.BoundTop,[double]$range.BoundWidth,[double]$range.BoundHeight);rotation=$reportedRotation;ancestor_rotation=$AncestorRotation;ancestor_rotated=$AncestorRotated;rotation_composition_verified=(-not $AncestorRotated);line_count=$null}
                $lines=$null
                try {
                    $lines=$range.Lines()
                    $measurement.line_count=[int]$lines.Count
                } catch {
                    $measurement.line_count_error=$_.Exception.Message
                } finally { Release-Com $lines }
                $SlideRecord.text_bounds.Add($measurement)
            }
        } finally { Release-Com $range; Release-Com $frame }
    }
    if ($Shape.Connector -eq -1) { $SlideRecord.connectors.Add((Get-Binding $Shape)) }
    if ($Shape.HasTable -eq -1) { $SlideRecord.unverified.Add("$name`: table-cell text bounds are not supported by this shape-level collector") }
    if ($Shape.Type -eq 6) {
        $children = $null
        try {
            $children = $Shape.GroupItems
            for ($j=1; $j -le $children.Count; $j++) {
                $child = $children.Item($j)
                try { Add-ShapeEntry $child $SlideIndex (@($Parents)+$name) $State $SlideRecord $reportedRotation (@($ParentIds)+[int]$Shape.Id) ($AncestorRotated -or [math]::Abs($reportedRotation%360) -gt .001) }
                catch { if (-not $State.entries.Contains($child)) { Release-Com $child }; throw }
            }
        } finally { Release-Com $children }
    }
}
function New-Snapshot($Deck,[string]$RenderDir,[bool]$Render) {
    $state = @{map=[Collections.Generic.Dictionary[string,object]]::new([StringComparer]::OrdinalIgnoreCase);ambiguous=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase);entries=[Collections.Generic.List[object]]::new();slides=[Collections.Generic.List[object]]::new()}
    $slides = $null; $page = $null
    try {
        $page = $Deck.PageSetup; $state.width=[double]$page.SlideWidth; $state.height=[double]$page.SlideHeight
        if ($state.width -le 0 -or $state.height -le 0) { throw 'Invalid slide dimensions' }
        $renderHeight = [int][math]::Round($RenderWidth*$state.height/$state.width)
        if ($renderHeight -lt 1 -or $renderHeight -gt 16384) { throw 'Resulting render height must be in 1..16384 pixels' }
        $slides = $Deck.Slides
        if ($slides.Count -lt 1) { throw 'Presentation has no slides' }
        for ($i=1; $i -le $slides.Count; $i++) {
            $slide=$null; $shapes=$null
            try {
                $slide=$slides.Item($i)
                $sr=[ordered]@{index=$i;render_path=$null;render_sha256=$null;text_bounds=[Collections.Generic.List[object]]::new();shapes=[Collections.Generic.List[object]]::new();connectors=[Collections.Generic.List[object]]::new();unverified=[Collections.Generic.List[string]]::new()}
                if ($Render) {
                    $path=Join-Path $RenderDir ('slide-{0:D4}.png' -f $i)
                    $slide.Export($path,'PNG',$RenderWidth,$renderHeight)
                    if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Item -LiteralPath $path).Length -eq 0) { throw "PowerPoint produced no render for slide $i" }
                    $sr.render_path=[IO.Path]::GetRelativePath($outputPath,$path).Replace('\','/'); $sr.render_sha256=Get-Sha $path
                }
                $shapes=$slide.Shapes
                for ($j=1; $j -le $shapes.Count; $j++) {
                    $shape=$shapes.Item($j)
                    try { Add-ShapeEntry $shape $i @() $state $sr }
                    catch { if (-not $state.entries.Contains($shape)) { Release-Com $shape }; throw }
                }
                $state.slides.Add($sr)
            } finally { Release-Com $shapes; Release-Com $slide }
        }
        return $state
    } catch { Clear-Snapshot $state; throw }
    finally { Release-Com $slides; Release-Com $page }
}
function Clear-Snapshot($Snapshot) {
    if ($null -ne $Snapshot) {
        foreach ($entry in $Snapshot.entries) { Release-Com $entry }
        $Snapshot.entries.Clear(); $Snapshot.map.Clear()
    }
}
function Assert-PlanTargets($Plan,$Snapshot) {
    foreach ($op in $Plan) {
        if (-not $Snapshot.map.ContainsKey($op.name)) { throw "Missing edit shape: $($op.name)" }
        if ($Snapshot.ambiguous.Contains($op.name)) { throw "Globally ambiguous edit shape name: $($op.name)" }
        $target=$Snapshot.map[$op.name]; $shape=$target.shape
        if ($target.slide -ne $op.slide) { throw "Shape '$($op.name)' is on slide $($target.slide), not $($op.slide)" }
        switch ($op.op) {
            text { if ($shape.HasTextFrame -ne -1 -or $shape.Type -eq 6) { throw "Unsupported text target type for '$($op.name)'" } }
            move { if ($shape.Type -notin @(1,5,6,9,13,17) -or $shape.Connector -eq -1) { throw "Unsupported move target type for '$($op.name)'" } }
            line_color { if ($shape.Type -notin @(1,5,9,17)) { throw "Unsupported line_color target type for '$($op.name)'" } }
        }
    }
}
function Read-Property($Target,[string]$Op) {
    $frame=$null; $range=$null; $line=$null; $color=$null
    try {
        switch ($Op) {
            text { $frame=$Target.TextFrame; $range=$frame.TextRange; return [string]$range.Text }
            move { return ,@([double]$Target.Left,[double]$Target.Top) }
            line_color { $line=$Target.Line; $color=$line.ForeColor; return [int]$color.RGB }
        }
    } finally { Release-Com $range; Release-Com $frame; Release-Com $color; Release-Com $line }
}
function Set-Edit($Target,$Op) {
    $frame=$null; $range=$null; $line=$null; $color=$null
    try {
        $before=Read-Property $Target $Op.op
        switch ($Op.op) {
            text { $frame=$Target.TextFrame; $range=$frame.TextRange; $range.Text=$Op.value }
            move { $Target.Left=[double]$Target.Left+[double]$Op.dx_pt; $Target.Top=[double]$Target.Top+[double]$Op.dy_pt }
            line_color { $line=$Target.Line; $color=$line.ForeColor; $color.RGB=[int]($Op.rgb[0]+256*$Op.rgb[1]+65536*$Op.rgb[2]) }
        }
        $actual=Read-Property $Target $Op.op
        $applied=switch ($Op.op) {
            text { ($actual -replace "`r`n|`n","`r") -ceq ($Op.value -replace "`r`n|`n","`r") }
            move { [math]::Abs($actual[0]-($before[0]+$Op.dx_pt)) -le .05 -and [math]::Abs($actual[1]-($before[1]+$Op.dy_pt)) -le .05 }
            line_color { $actual -eq [int]($Op.rgb[0]+256*$Op.rgb[1]+65536*$Op.rgb[2]) }
        }
        if (-not $applied) { throw "Requested $($Op.op) edit did not apply to '$($Op.name)'" }
    } finally { Release-Com $range; Release-Com $frame; Release-Com $color; Release-Com $line }
}
function Get-ConnectorSignature($Snapshot) {
    # Bindings/sites only: PowerPoint may adjust connector geometry after a node move.
    $items=@($Snapshot.slides | ForEach-Object { $si=$_.index; $_.connectors | ForEach-Object { [ordered]@{slide=$si;binding=$_} } })
    return (ConvertTo-Json -InputObject $items -Depth 12 -Compress)
}

$artifactPath=(Resolve-Path -LiteralPath $Artifact).Path
if (-not (Test-Path -LiteralPath $artifactPath -PathType Leaf) -or [IO.Path]::GetExtension($artifactPath).ToLowerInvariant() -ne '.pptx') { throw 'Artifact must be an existing .pptx file' }
$outputPath=[IO.Path]::GetFullPath($OutputDir)
if (Test-Path -LiteralPath $outputPath) { throw 'OutputDir already exists; use a new directory' }
$plan=Read-Plan $EditPlan
$sourceHash=Get-Sha $artifactPath
# Atomic create-only directory claim prevents normal concurrent runs from overwriting evidence.
$parent=[IO.Path]::GetDirectoryName($outputPath)
if (-not (Test-Path -LiteralPath $parent -PathType Container)) { throw 'OutputDir parent must already exist' }
$claim=Join-Path $parent ('.'+[IO.Path]::GetFileName($outputPath)+'.office-claim')
$claimStream=$null; $app=$null; $presentations=$null; $deck=$null; $probe=$null; $snapshot=$null; $probeSnapshot=$null; $reopened=$null
$errorMessage=$null; $success=$false; $record=$null
try {
    $claimStream=[IO.File]::Open($claim,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    if (Test-Path -LiteralPath $outputPath) { throw 'OutputDir appeared while claiming output' }
    [void][IO.Directory]::CreateDirectory($outputPath)
    $record=[ordered]@{schema_version=1;artifact_sha256=$sourceHash;artifact=$artifactPath;renderer=$null;slide_width_pt=$null;slide_height_pt=$null;slides=@();ambiguous_names=@();status='NOT_VERIFIED';source_unchanged=$null;edit_probe=[ordered]@{status='NOT_REQUESTED'};claim_boundary='PowerPoint slide renders, TextRange bounding boxes and requested isolated edits only. Bounds are slide points, not exact glyph masks or visual acceptance. Rotation is PowerPoint Shape.Rotation; rotated-group composition and flipped/skewed transforms are not certified.';error=$null}
    $app=New-Object -ComObject PowerPoint.Application
    $record.renderer='Microsoft PowerPoint '+[string]$app.Version
    $presentations=$app.Presentations
    # PowerPoint may reuse an existing process. Do not take ownership of a deck
    # already opened by the user or another automation client.
    for ($i=1; $i -le $presentations.Count; $i++) {
        $existing=$null
        try {
            $existing=$presentations.Item($i)
            $existingPath=[string]$existing.FullName
            if ([IO.Path]::IsPathFullyQualified($existingPath) -and
                [IO.Path]::GetFullPath($existingPath).Equals($artifactPath,[StringComparison]::OrdinalIgnoreCase)) {
                throw 'Artifact is already open in PowerPoint; close that presentation before running this verifier'
            }
        } finally { Release-Com $existing }
    }
    $deck=$presentations.Open($artifactPath,-1,0,0)
    $snapshot=New-Snapshot $deck $outputPath $true
    $record.slide_width_pt=$snapshot.width; $record.slide_height_pt=$snapshot.height; $record.slides=$snapshot.slides.ToArray()
    $record.ambiguous_names=@($snapshot.ambiguous | Sort-Object)
    Assert-PlanTargets $plan $snapshot
    $bindings=Get-ConnectorSignature $snapshot
    Clear-Snapshot $snapshot; $snapshot=$null
    $deck.Close(); Release-Com $deck; $deck=$null
    if ($plan.Count -gt 0) {
        $probePath=Join-Path $outputPath 'edit-probe.pptx'
        [IO.File]::Copy($artifactPath,$probePath,$false)
        $probe=$presentations.Open($probePath,0,0,0)
        $probeSnapshot=New-Snapshot $probe $outputPath $false
        Assert-PlanTargets $plan $probeSnapshot
        $expected=[Collections.Generic.List[object]]::new()
        foreach ($op in $plan) { Set-Edit $probeSnapshot.map[$op.name].shape $op }
        # Capture the final expected state after all edits (including group/child interactions).
        foreach ($op in $plan) { $expected.Add([ordered]@{op=$op.op;name=$op.name;slide=[int]$op.slide;expected=(Read-Property $probeSnapshot.map[$op.name].shape $op.op)}) }
        Clear-Snapshot $probeSnapshot; $probeSnapshot=$null
        $probe.Save(); $probe.Close(); Release-Com $probe; $probe=$null
        $probe=$presentations.Open($probePath,-1,0,0)
        $probeRender=Join-Path $outputPath 'edit-probe-renders'; [void][IO.Directory]::CreateDirectory($probeRender)
        $reopened=New-Snapshot $probe $probeRender $true
        Assert-PlanTargets $plan $reopened
        foreach ($test in $expected) {
            $actual=Read-Property $reopened.map[$test.name].shape $test.op
            $pass=if ($test.op -eq 'move') { [math]::Abs($actual[0]-$test.expected[0]) -le .05 -and [math]::Abs($actual[1]-$test.expected[1]) -le .05 } else { $actual -ceq $test.expected }
            $test.actual=$actual; $test.status=if ($pass) {'PASS'} else {'FAIL'}
        }
        $bindingsPersisted=(Get-ConnectorSignature $reopened) -ceq $bindings
        $record.edit_probe=[ordered]@{status='FAIL';path='edit-probe.pptx';sha256=(Get-Sha $probePath);operations=$expected.ToArray();connector_bindings_persisted=$bindingsPersisted;connectors_before=($bindings|ConvertFrom-Json -NoEnumerate);connectors_after=((Get-ConnectorSignature $reopened)|ConvertFrom-Json -NoEnumerate);slides=$reopened.slides.ToArray();claim_boundary='Requested edits and connector binding/site persistence on this copy; no arbitrary drag/routing or source fidelity certification.'}
        if (@($expected|Where-Object status -eq 'FAIL').Count -gt 0 -or -not $bindingsPersisted) { throw 'One or more saved/reopened edits or connector bindings did not persist' }
        $record.edit_probe.status='PASS'
        Clear-Snapshot $reopened; $reopened=$null
        $probe.Close(); Release-Com $probe; $probe=$null
    }
    $success=$true
} catch { $errorMessage=$_.Exception.Message }
finally {
    Clear-Snapshot $snapshot; Clear-Snapshot $probeSnapshot; Clear-Snapshot $reopened
    foreach ($owned in @($probe,$deck)) {
        if ($null -ne $owned) {
            try { $owned.Saved=-1; $owned.Close() } catch { $success=$false; $errorMessage="Owned presentation close failed: $($_.Exception.Message); $errorMessage" }
            Release-Com $owned
        }
    }
    Release-Com $presentations; Release-Com $app
    try { $unchanged=(Get-Sha $artifactPath) -ceq $sourceHash } catch { $unchanged=$false; $errorMessage="Source hash recheck failed: $($_.Exception.Message); $errorMessage" }
    if (-not $unchanged) { $success=$false; $errorMessage="Source artifact changed during verification; $errorMessage" }
    if ($null -ne $record) {
        $record.source_unchanged=$unchanged; $record.status=if ($success) {'PASS'} else {'FAIL'}; $record.error=$errorMessage
        Write-Json $record (Join-Path $outputPath 'office-evidence.json')
    }
    if ($null -ne $claimStream) { $claimStream.Dispose(); Remove-Item -LiteralPath $claim }
}
if (-not $success) { Write-Error $errorMessage; exit 1 }
Write-Output (Join-Path $outputPath 'office-evidence.json')
