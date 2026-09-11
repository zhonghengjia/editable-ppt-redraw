param([Parameter(Mandatory=$true)][string]$InputPath,[Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName PresentationCore
if(Test-Path -LiteralPath $OutputPath){throw 'Coverage output already exists'}
$r=Get-Content -LiteralPath $InputPath -Raw | ConvertFrom-Json
$g=[System.Windows.Media.Geometry]::Parse('F1 '+$r.d)
$pen=[System.Windows.Media.Pen]::new([System.Windows.Media.Brushes]::Black,[double]$r.width)
$pen.LineJoin=[System.Windows.Media.PenLineJoin]::Round
$wide=$g.GetWidenedPathGeometry($pen,[double]$r.tolerance,[System.Windows.Media.ToleranceType]::Absolute)
$union=[System.Windows.Media.Geometry]::Combine($g,$wide,[System.Windows.Media.GeometryCombineMode]::Union,$null,[double]$r.tolerance,[System.Windows.Media.ToleranceType]::Absolute)
if($union.IsEmpty()){throw 'Empty computed coverage'}
$d=$union.ToString([Globalization.CultureInfo]::InvariantCulture)
if($d.StartsWith('F1')){$d=$d.Substring(2)}
$result=@{d=$d;fill_rule=$union.FillRule.ToString();engine=[System.Windows.Media.Geometry].Assembly.FullName}
[IO.File]::WriteAllText($OutputPath,($result|ConvertTo-Json -Depth 3),[Text.UTF8Encoding]::new($false))
