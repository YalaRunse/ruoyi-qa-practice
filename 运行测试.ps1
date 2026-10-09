# 统一入口：默认离线检查，显式选择模式才连接隔离副本。
param(
    [ValidateSet('Validate','Evidence','ReadOnly','Users','Batch')]
    [string]$Mode = 'Validate',
    [string]$PythonPath = '',
    [string]$ConfigPath = '',
    [string]$EvidenceRoot = ''
)
$ErrorActionPreference = 'Stop'
$originalLocation = Get-Location
$previousUtf8 = $env:PYTHONUTF8
$previousToken = $env:RUOYI_TEST_TOKEN
$previousConsoleEncoding = [Console]::OutputEncoding
$tokenWasEntered = $false
try {
    Set-Location -LiteralPath $PSScriptRoot
    $env:PYTHONUTF8 = '1'
    # PowerShell 5.1 也按 UTF-8 接收 Python 输出，减少中文乱码。
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    # 优先使用工程自己的虚拟环境，再兼容当前学习目录的环境。
    if (-not $PythonPath) {
        $candidates = @((Join-Path $PSScriptRoot '.venv\Scripts\python.exe'),
                        (Join-Path $PSScriptRoot '..\..\.venv\Scripts\python.exe'))
        $PythonPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
    if (-not $PythonPath -or -not (Test-Path -LiteralPath $PythonPath)) {
        throw '找不到Python，请按README准备环境或指定-PythonPath。'
    }
    if (-not $ConfigPath) { $ConfigPath = Join-Path $PSScriptRoot 'config.local.json' }
    if (-not $EvidenceRoot) { $EvidenceRoot = Join-Path $PSScriptRoot '..\qa-api' }
    $runPath = Join-Path $PSScriptRoot ('runs\' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '_' + $Mode)
    New-Item -ItemType Directory -Path $runPath -Force | Out-Null
    if ($Mode -eq 'Evidence') {
        & $PythonPath '.\核对首轮证据.py' --source-root $EvidenceRoot --output (Join-Path $runPath '首轮核对.json') 2>&1 |
            Tee-Object -FilePath (Join-Path $runPath '执行记录.txt')
    } else {
        $testArgs = @('-m','pytest','--junitxml', (Join-Path $runPath '结果.xml'))
        if ($Mode -eq 'Validate') { $testArgs += 'checks' }
        else {
            $testTarget = if ($Mode -eq 'Users') { 'tests/test_local_api.py' } else { 'tests' }
            $testArgs += @($testTarget,'--lab-config', $ConfigPath)
            if ($Mode -eq 'ReadOnly') { $testArgs += @('-m','not write and not authenticated') }
            else {
                # 用户手工登录并完成验证码；这里只读取现成令牌，不读取Redis验证码。
                if (-not $env:RUOYI_TEST_TOKEN) {
                    $secureToken = Read-Host '请粘贴隔离页面登录后请求头中的令牌（输入不显示）' -AsSecureString
                    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
                    try { $env:RUOYI_TEST_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
                    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
                    $tokenWasEntered = $true
                }
            }
        }
        & $PythonPath @testArgs 2>&1 | Tee-Object -FilePath (Join-Path $runPath '执行记录.txt')
    }
    $resultCode = $LASTEXITCODE
    if ($Mode -ne 'Evidence' -and (Test-Path -LiteralPath (Join-Path $runPath '结果.xml'))) {
        # 先保存原测试退出码；生成摘要不会把失败测试改成成功。
        & $PythonPath '.\生成执行摘要.py' --run-directory $runPath
        if ($LASTEXITCODE -ne 0) { throw '执行摘要生成失败，请保留本轮原始记录。' }
    }
    Write-Host ('本轮记录：' + $runPath)
    if ($resultCode -ne 0) { throw ('本轮执行未全部通过，退出码：' + $resultCode) }
} finally {
    # 清除本次手动输入的令牌，恢复调用者原有环境和工作位置。
    if ($tokenWasEntered) { $env:RUOYI_TEST_TOKEN = $previousToken }
    $env:PYTHONUTF8 = $previousUtf8
    [Console]::OutputEncoding = $previousConsoleEncoding
    Set-Location -LiteralPath $originalLocation
}
