#Requires -Version 7.3
[CmdletBinding()]
param([Parameter(Mandatory)][string]$OutputDir)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if (Test-Path -LiteralPath $OutputDir) { throw 'Test OutputDir must not exist' }
[void][IO.Directory]::CreateDirectory([IO.Path]::GetFullPath($OutputDir))
$root=[IO.Path]::GetFullPath($OutputDir)
$utility=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../scripts/verify_powerpoint.ps1'))
$shellPath=(Get-Process -Id $PID).Path
$results=[Collections.Generic.List[object]]::new()
function Assert-Test([bool]$Condition,[string]$Name) {
    $results.Add([ordered]@{test=$Name;status=$(if($Condition){'PASS'}else{'FAIL'})})
    if (-not $Condition) { throw "Test failed: $Name" }
}
function Run-Utility([string]$Artifact,[string]$Out,[string]$Plan='') {
    $argsList=@('-NoProfile','-File',$utility,'-Artifact',$Artifact,'-OutputDir',$Out,'-RenderWidth','640')
    if ($Plan) { $argsList+=@('-EditPlan',$Plan) }
    $output=& $shellPath @argsList 2>&1
    [pscustomobject]@{code=$LASTEXITCODE;output=($output|Out-String)}
}
function Release-TestCom($Value) { if ($null -ne $Value -and [Runtime.InteropServices.Marshal]::IsComObject($Value)) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($Value) } }
$app=$null; $deck=$null; $slides=$null; $pres=$null; $shapes=$null; $slide=$null
$fixture=Join-Path $root 'synthetic.pptx'
$duplicate=Join-Path $root 'duplicate-names.pptx'
$fatal=$null
try {
    $app=New-Object -ComObject PowerPoint.Application
    $pres=$app.Presentations; $deck=$pres.Add(0)
    $deck.PageSetup.SlideWidth=720; $deck.PageSetup.SlideHeight=405
    $slides=$deck.Slides; $slide=$slides.Add(1,12); $shapes=$slide.Shapes
    $label=$shapes.AddTextbox(1,50,30,220,30); $label.Name='label-main'; $label.TextFrame.TextRange.Text='Synthetic label'
    $a=$shapes.AddShape(1,80,130,120,60); $a.Name='node-a'; $a.TextFrame.TextRange.Text='Node A'
    $b=$shapes.AddShape(1,400,130,120,60); $b.Name='node-b'; $b.TextFrame.TextRange.Text='Node B'
    $connector=$shapes.AddConnector(1,200,160,400,160); $connector.Name='link-a-b'
    $connector.ConnectorFormat.BeginConnect($a,4); $connector.ConnectorFormat.EndConnect($b,2)
    $one=$shapes.AddShape(1,70,260,100,60); $one.Name='unit-box'
    $two=$shapes.AddTextbox(1,75,270,90,30); $two.Name='unit-label'; $two.TextFrame.TextRange.Text='Grouped text'
    $range=$shapes.Range(@('unit-box','unit-label')); $inner=$range.Group(); $inner.Name='unit-inner'; Release-TestCom $range
    $three=$shapes.AddShape(1,175,270,20,20); $three.Name='unit-dot'
    $range=$shapes.Range(@('unit-inner','unit-dot')); $group=$range.Group(); $group.Name='semantic-unit'; Release-TestCom $range
    foreach($obj in @($label,$a,$b,$connector,$one,$two,$inner,$three,$group)){Release-TestCom $obj}
    Release-TestCom $shapes; $shapes=$null; Release-TestCom $slide; $slide=$null
    $slide=$slides.Add(2,12); $shapes=$slide.Shapes
    $other=$shapes.AddTextbox(1,30,40,300,50); $other.Name='second-slide-label'; $other.TextFrame.TextRange.Text='Second slide'; Release-TestCom $other
    $deck.SaveAs($fixture,24); $deck.Close(); Release-TestCom $deck; $deck=$null
    Release-TestCom $shapes; $shapes=$null; Release-TestCom $slide; $slide=$null; Release-TestCom $slides; $slides=$null
    $hash=(Get-FileHash -LiteralPath $fixture).Hash
    $run=Run-Utility $fixture (Join-Path $root 'render-only')
    Assert-Test ($run.code -eq 0) 'Render-only invocation without EditPlan'
    $renderOnly=Get-Content -LiteralPath (Join-Path $root 'render-only/office-evidence.json') -Raw|ConvertFrom-Json
    Assert-Test ($renderOnly.edit_probe.status -eq 'NOT_REQUESTED' -and -not (Test-Path -LiteralPath (Join-Path $root 'render-only/edit-probe.pptx'))) 'Render-only invocation creates no probe'
    $plan=@(
        @{op='text';name='label-main';value='Edited native text'},
        @{op='move';name='semantic-unit';dx_pt=11;dy_pt=4},
        @{op='move';name='node-a';dx_pt=0;dy_pt=13},
        @{op='line_color';name='unit-box';rgb=@(255,32,64)},
        @{op='text';name='second-slide-label';slide=2;value='Edited slide two'}
    )|ConvertTo-Json -Depth 8 -Compress
    $validOut=Join-Path $root 'valid'
    $run=Run-Utility $fixture $validOut $plan
    $run.output|Set-Content -LiteralPath (Join-Path $root 'valid-output.txt') -Encoding utf8NoBOM
    Assert-Test ($run.code -eq 0) 'PowerPoint render and isolated edit run'
    $e=Get-Content -LiteralPath (Join-Path $validOut 'office-evidence.json') -Raw|ConvertFrom-Json
    Assert-Test ($e.schema_version -eq 1 -and $e.status -eq 'PASS' -and $e.source_unchanged) 'Evidence schema, successful status and unchanged source'
    Assert-Test ($e.slides.Count -eq 2 -and $e.edit_probe.slides.Count -eq 2) 'Every original and probe slide rendered'
    Assert-Test (-not [IO.Path]::IsPathFullyQualified($e.slides[0].render_path) -and (Test-Path -LiteralPath (Join-Path $validOut $e.slides[0].render_path))) 'Render paths are portable and resolve inside evidence output'
    Assert-Test ($e.edit_probe.operations.Count -eq 5 -and @($e.edit_probe.operations|Where-Object status -ne 'PASS').Count -eq 0) 'Text, group move, connected rectangle move and child style persisted'
    Assert-Test ($e.edit_probe.connector_bindings_persisted -and $e.edit_probe.connectors_before.Count -eq 1) 'Connector names, shape IDs and connection sites persisted'
    $nested=@($e.slides[0].text_bounds|Where-Object name -eq 'unit-label')
    Assert-Test ($nested.Count -eq 1 -and $nested[0].box_pt.Count -eq 4 -and $nested[0].box_pt[0] -gt 50) 'Recursive text bounds are present in slide coordinates'
    $invalidPlans=@(
        @{name='unsupported-op';json='[{"op":"replace_picture","name":"node-a"}]';preflight=$true},
        @{name='missing-name';json='[{"op":"move","name":"missing","dx_pt":1,"dy_pt":0}]';preflight=$false},
        @{name='unsupported-type';json='[{"op":"text","name":"semantic-unit","value":"bad"}]';preflight=$false},
        @{name='late-invalid';json='[{"op":"text","name":"label-main","value":"must not save"},{"op":"line_color","name":"semantic-unit","rgb":[1,2,3]}]';preflight=$false},
        @{name='invalid-number';json='[{"op":"move","name":"node-a","dx_pt":"1","dy_pt":0}]';preflight=$true}
    )
    foreach ($bad in $invalidPlans) {
        $badOut=Join-Path $root $bad.name; $run=Run-Utility $fixture $badOut $bad.json
        $run.output|Set-Content -LiteralPath (Join-Path $root ($bad.name+'-output.txt')) -Encoding utf8NoBOM
        Assert-Test ($run.code -ne 0 -and -not (Test-Path -LiteralPath (Join-Path $badOut 'edit-probe.pptx'))) ($bad.name+': reject before probe creation/save')
        if (-not $bad.preflight) {
            $failed=Get-Content -LiteralPath (Join-Path $badOut 'office-evidence.json') -Raw|ConvertFrom-Json
            Assert-Test ($failed.status -eq 'FAIL' -and $failed.source_unchanged) ($bad.name+': honest failure evidence')
        }
    }
    $evidenceHash=(Get-FileHash -LiteralPath (Join-Path $validOut 'office-evidence.json')).Hash
    $run=Run-Utility $fixture $validOut $plan
    Assert-Test ($run.code -ne 0 -and (Get-FileHash -LiteralPath (Join-Path $validOut 'office-evidence.json')).Hash -ceq $evidenceHash) 'Existing output directory refused without overwrite'
    [IO.File]::Copy($fixture,$duplicate,$false)
    $deck=$pres.Open($duplicate,0,0,0); $slides=$deck.Slides; $slide=$slides.Item(2); $shapes=$slide.Shapes; $dup=$shapes.Item(1); $dup.Name='unit-label'; Release-TestCom $dup
    Release-TestCom $shapes; $shapes=$null; Release-TestCom $slide; $slide=$null
    $slide=$slides.Item(1); $shapes=$slide.Shapes; $rotated=$shapes.Item('semantic-unit'); $rotated.Rotation=23; Release-TestCom $rotated
    $deck.Save(); $deck.Close(); Release-TestCom $deck; $deck=$null
    Release-TestCom $shapes; $shapes=$null; Release-TestCom $slide; $slide=$null; Release-TestCom $slides; $slides=$null
    $duplicateRender=Join-Path $root 'duplicate-render'; $run=Run-Utility $duplicate $duplicateRender
    Assert-Test ($run.code -eq 0) 'Read-only rendering allows duplicate irrelevant names'
    $dupEvidence=Get-Content -LiteralPath (Join-Path $duplicateRender 'office-evidence.json') -Raw|ConvertFrom-Json
    Assert-Test ('unit-label' -in $dupEvidence.ambiguous_names -and @($dupEvidence.slides|ForEach-Object{$_.text_bounds}|Where-Object name -eq 'unit-label').Count -eq 2) 'Duplicate names and all bounds retained in evidence'
    $rotatedText=@($dupEvidence.slides[0].text_bounds|Where-Object name -eq 'unit-label')[0]
    Assert-Test ([math]::Abs($rotatedText.rotation-23) -lt .05 -and [math]::Abs($rotatedText.ancestor_rotation-23) -lt .05 -and $rotatedText.ancestor_rotated -and -not $rotatedText.rotation_composition_verified) 'Reported angle preserved and rotated ancestor marked unsupported'
    $dupOut=Join-Path $root 'duplicate-rejected'; $run=Run-Utility $duplicate $dupOut '[{"op":"text","name":"unit-label","value":"ambiguous"}]'
    $run.output|Set-Content -LiteralPath (Join-Path $root 'duplicate-output.txt') -Encoding utf8NoBOM
    Assert-Test ($run.code -ne 0 -and -not (Test-Path -LiteralPath (Join-Path $dupOut 'edit-probe.pptx'))) 'Duplicate name across nested group and another slide rejected'
    Assert-Test ((Get-FileHash -LiteralPath $fixture).Hash -ceq $hash) 'Synthetic source SHA-256 unchanged through all cases'
    $deck=$pres.Open($fixture,-1,0,0)
    $openOut=Join-Path $root 'already-open'; $run=Run-Utility $fixture $openOut $plan
    Assert-Test ($run.code -ne 0 -and $deck.FullName -ceq $fixture -and $pres.Count -ge 1) 'Already-open source refused and existing presentation kept open'
    $deck.Close(); Release-TestCom $deck; $deck=$null
} catch { $fatal=$_.Exception.Message }
finally {
    if ($null -ne $deck) { try{$deck.Saved=-1; $deck.Close()}catch{}; Release-TestCom $deck }
    foreach($obj in @($shapes,$slide,$slides,$pres,$app)){Release-TestCom $obj}
    $report=[ordered]@{status=$(if($fatal){'FAIL'}else{'PASS'});error=$fatal;tests=$results.ToArray();scope='Bounded synthetic PowerPoint COM tests; no visual fidelity or exact glyph certification.'}
    $report|ConvertTo-Json -Depth 10|Set-Content -LiteralPath (Join-Path $root 'test-report.json') -Encoding utf8NoBOM
    $report|ConvertTo-Json -Depth 10
}
if($fatal){exit 1}
