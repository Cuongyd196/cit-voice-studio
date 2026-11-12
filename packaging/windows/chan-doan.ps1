# Cong cu chan doan CIT Voice Studio.
# Viet bang PowerShell chu khong phai .bat: batch hieu ky tu > va >= trong chuoi
# thanh toan tu chuyen huong, lam mat noi dung va sinh file rac.

$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$out  = Join-Path $root "chan-doan.txt"
$lines = New-Object System.Collections.Generic.List[string]

function Say([string]$t = "") {
    Write-Host $t
    $lines.Add($t)
}

Say "================================================================"
Say " CIT VOICE STUDIO - KET QUA CHAN DOAN"
Say " $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Say "================================================================"
Say ""

Say "== Windows =="
$os = Get-CimInstance Win32_OperatingSystem
Say ("  {0}" -f $os.Caption)
Say ("  Build {0} | {1}" -f $os.BuildNumber, $env:PROCESSOR_ARCHITECTURE)
Say ""

Say "== .NET Framework  (can tu 461808 tro len, tuc 4.7.2) =="
$rel = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full' -Name Release).Release
if ($rel) {
    $ok = if ($rel -ge 461808) { "OK" } else { "QUA CU" }
    Say ("  Release = {0}   [{1}]" -f $rel, $ok)
} else {
    Say "  KHONG TIM THAY - thieu .NET Framework 4.x"
}
Say ""

Say "== Microsoft Edge WebView2 Runtime =="
$guids = @{
    "Runtime" = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    "Beta"    = "{2CD8A007-E189-409D-A2C8-9AF4EF3C72AA}"
    "Dev"     = "{0D50BFEC-CD6A-4F9A-964C-C7416E3ACB10}"
    "Canary"  = "{65C35B14-6C1D-4122-AC46-7148CC9D6497}"
}
$found = $false
foreach ($name in $guids.Keys) {
    foreach ($hive in @("HKLM:\SOFTWARE\WOW6432Node\Microsoft", "HKLM:\SOFTWARE\Microsoft", "HKCU:\SOFTWARE\Microsoft")) {
        $p = "$hive\EdgeUpdate\Clients\$($guids[$name])"
        $pv = (Get-ItemProperty $p -Name pv).pv
        if ($pv) {
            Say ("  {0}: {1}   ({2})" -f $name, $pv, $hive)
            $found = $true
        }
    }
}
if (-not $found) {
    Say "  KHONG CO WEBVIEW2 - day la nguyen nhan pho bien nhat cua man hinh trang."
    Say "  Cai mien phi tai: https://go.microsoft.com/fwlink/p/?LinkId=2124703"
}
Say ""

Say "== Microsoft Visual C++ Redistributable (onnxruntime bat buoc can) =="
$sys32 = Join-Path $env:SystemRoot "System32"
$need  = @("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll", "msvcp140_1.dll")
$miss  = @()
foreach ($d in $need) {
    $has = Test-Path (Join-Path $sys32 $d)
    if (-not $has) { $miss += $d }
    Say ("  {0,-22}: {1}" -f $d, $(if ($has) { "CO" } else { "THIEU" }))
}
if ($miss.Count -gt 0) {
    Say ""
    Say "  THIEU VC++ REDISTRIBUTABLE - day la nguyen nhan cua loi:"
    Say "    DLL load failed while importing onnxruntime_pybind11_state"
    Say "  Cai ban x64 (mien phi, cua Microsoft):"
    Say "    https://aka.ms/vs/17/release/vc_redist.x64.exe"
    Say "  (Ban dong goi .exe khong dinh loi nay - no tu mang san 4 file tren.)"
}
Say ""

Say "== File ung dung =="
$checks = @{
    "CIT-Voice-Studio.exe"                                     = "File chay"
    "_internal\app-desktop\cit-voice-app\dist\index.html"      = "Giao dien React"
    "models\hf_cache\hub"                                      = "Mo hinh kem san"
}
foreach ($k in $checks.Keys) {
    $has = Test-Path (Join-Path $root $k)
    Say ("  {0,-18}: {1}" -f $checks[$k], $(if ($has) { "CO" } else { "KHONG THAY" }))
}
Say ""

Say "== Cong 8001 =="
$busy = Get-NetTCPConnection -LocalPort 8001 -State Listen
if ($busy) {
    foreach ($c in $busy) {
        $pr = Get-Process -Id $c.OwningProcess
        Say ("  Dang bi chiem boi: {0} (PID {1}) - chay stop.bat truoc" -f $pr.ProcessName, $c.OwningProcess)
    }
} else {
    Say "  Trong - OK"
}
Say ""

Say "== Log lan chay gan nhat =="
$log = Join-Path $root "cit-voice-studio.log"
if (Test-Path $log) {
    Get-Content $log | ForEach-Object { Say ("  " + $_) }
} else {
    Say "  Chua co cit-voice-studio.log."
    Say "  Hay mo ung dung mot lan (de no chay toi luc hien man hinh trang), dong lai,"
    Say "  roi chay lai file chan doan nay."
}
Say ""
Say "================================================================"
Say " Da luu ket qua vao:"
Say "   $out"
Say ""
Say " Gui file do cho nguoi ho tro."
Say ""
Say " Muon xem loi JavaScript ben trong cua so trang, chay lenh sau"
Say " trong cua so nay (DevTools se mo kem, xem tab Console):"
Say "   `$env:CIT_DEBUG=1; .\CIT-Voice-Studio.exe"
Say "================================================================"

$lines | Set-Content -Path $out -Encoding UTF8
Write-Host ""
Read-Host "Nhan Enter de dong"
