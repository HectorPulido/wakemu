param([switch]$Check)
# Portable native UI. Credentials travel to the local backend through stdin only.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
$script:Root = Split-Path $PSScriptRoot -Parent
$script:Loading = $true
$script:Busy = $false
$script:PasswordEdited = $false
$script:ActiveProcess = $null
$script:ActiveAction = ''
$script:Data = $null
$script:CurrentId = 'lan'
$script:LoadedIdentity = ''
$script:Controls = @{}
$script:WebView = $null
$script:WebEpoch = 0
$script:WebIdentity = ''
$script:WebAvailable = $false
$script:WebFolders = New-Object 'Collections.Generic.List[string]'
$script:ActiveEpoch = 0
$script:AdvancedExpanded = $false
$script:LastDomain = ''
$script:DiscoveryDomain = ''
$script:DiscoveryId = ''
$script:Ink = [Drawing.ColorTranslator]::FromHtml('#173746')
$script:Teal = [Drawing.ColorTranslator]::FromHtml('#287C81')
$script:Paper = [Drawing.ColorTranslator]::FromHtml('#F5F8FA')
$form = New-Object Windows.Forms.Form
$form.Text = 'Wakfu - Minilauncher'
$form.ClientSize = New-Object Drawing.Size(800, 560)
$form.MinimumSize = New-Object Drawing.Size(816, 599)
$form.StartPosition = 'CenterScreen'
$form.BackColor = $script:Paper
$form.ForeColor = $script:Ink
$form.Font = New-Object Drawing.Font('Segoe UI', 10)
$form.AutoScaleMode = [Windows.Forms.AutoScaleMode]::Dpi
$form.FormBorderStyle = 'Sizable'
$form.MaximizeBox = $true
function Label($parent, $text, $x, $y, $width=210) {
    $c = New-Object Windows.Forms.Label
    $c.Text = $text; $c.Location = New-Object Drawing.Point($x,$y)
    $c.Size = New-Object Drawing.Size($width,24)
    $parent.Controls.Add($c); return $c
}
function Input($parent, $key, $x, $y, $width) {
    $c = New-Object Windows.Forms.TextBox
    $c.Location = New-Object Drawing.Point($x,$y); $c.Size = New-Object Drawing.Size($width,28)
    $parent.Controls.Add($c); $script:Controls[$key] = $c; return $c
}
function Button($parent,$text,$x,$y,$width=104) {
    $c = New-Object Windows.Forms.Button
    $c.Text=$text; $c.Location=New-Object Drawing.Point($x,$y); $c.Size=New-Object Drawing.Size($width,34)
    $c.FlatStyle='Flat'; $c.FlatAppearance.BorderColor=[Drawing.ColorTranslator]::FromHtml('#C7D8DF')
    $parent.Controls.Add($c); return $c
}
$header=New-Object Windows.Forms.Panel
$header.Location=New-Object Drawing.Point(0,0); $header.Size=New-Object Drawing.Size(780,92)
$header.BackColor=$script:Ink; $form.Controls.Add($header)
$title=Label $header 'WAKFU' 28 15 420
$title.Font=New-Object Drawing.Font('Segoe UI Semibold',25); $title.Height=44; $title.ForeColor=[Drawing.Color]::White
$sub=Label $header 'Tu servidor. Tus cuentas. Listo para jugar.' 30 61 550
$sub.ForeColor=[Drawing.ColorTranslator]::FromHtml('#BFDADC')
$version=Label $header '1.93.1+79' 628 33 120
$version.ForeColor=[Drawing.ColorTranslator]::FromHtml('#D6B773')
$serverBox=New-Object Windows.Forms.ComboBox
$serverBox.DropDownStyle='DropDownList'; $serverBox.Location=New-Object Drawing.Point(28,112)
$serverBox.Size=New-Object Drawing.Size(506,29); $serverBox.DisplayMember='name'; $form.Controls.Add($serverBox)
$new=Button $form 'Nuevo servidor' 546 108 204
$group=New-Object Windows.Forms.GroupBox
$group.Text='Configuración avanzada'; $group.Location=New-Object Drawing.Point(28,268); $group.Visible=$false; $group.Size=New-Object Drawing.Size(722,362)
$form.Controls.Add($group)
$null=Label $group 'Nombre del servidor' 18 26 300
$null=Input $group 'name' 18 51 682
$null=Label $form 'Dominio o IP del servidor' 28 158 506
$domain=Input $form 'server_host' 28 184 506
$detect=Button $form 'Detectar configuración' 546 180 204
$advanced=Button $form 'Configuración avanzada >' 28 226 300
$null=Label $group 'Puerto de conexion' 18 88 210
$null=Input $group 'dispatch_port' 18 113 210
$null=Label $group 'Puerto del mundo' 252 88 210
$null=Input $group 'game_port' 252 113 210
$null=Label $group 'Puerto del chat' 486 88 210
$null=Input $group 'chat_port' 486 113 214
$null=Label $group 'Autenticacion (URL)' 18 150 326
$null=Input $group 'api_url' 18 175 326
$null=Label $group 'Recursos del juego (URL)' 364 150 336
$null=Input $group 'http_url' 364 175 336
$null=Label $group 'Tienda (URL)' 18 212 326
$null=Input $group 'shop_url' 18 237 326
$null=Label $group 'IP o dominio del chat' 364 212 336
$null=Input $group 'chat_host' 364 237 336
$null=Label $group 'Certificado del servidor (opcional)' 18 274 500
$null=Input $group 'certificate' 18 299 564
$browse=Button $group 'Elegir...' 594 296 106
$accountBox=New-Object Windows.Forms.GroupBox
$accountBox.Text='Cuenta'; $accountBox.Location=New-Object Drawing.Point(28,536); $accountBox.Size=New-Object Drawing.Size(722,122)
$form.Controls.Add($accountBox)
$null=Label $accountBox 'Usuario' 18 23 300
$username=New-Object Windows.Forms.ComboBox
$username.DropDownStyle='DropDown'; $username.Location=New-Object Drawing.Point(18,48)
$username.Size=New-Object Drawing.Size(326,28); $accountBox.Controls.Add($username)
$null=Label $accountBox 'Contraseña' 364 23 300
$password=Input $accountBox 'password' 364 48 336
$password.UseSystemPasswordChar=$true
$remember=New-Object Windows.Forms.CheckBox
$remember.Text='Guardar cuenta y contraseña'; $remember.Location=New-Object Drawing.Point(18,85)
$remember.Size=New-Object Drawing.Size(326,26); $remember.Checked=$true; $accountBox.Controls.Add($remember)
$show=New-Object Windows.Forms.CheckBox
$show.Text='Mostrar contraseña'; $show.Location=New-Object Drawing.Point(364,85)
$show.Size=New-Object Drawing.Size(300,26); $accountBox.Controls.Add($show)
$status=Label $form 'Cargando tus servidores...' 30 673 720
$status.Height=28
$forget=Button $form 'Olvidar acceso' 28 711 146
$register=Button $form 'Registrarse' 190 711 142
$checkButton=Button $form 'Comprobar' 458 707 132
$play=Button $form 'Jugar' 606 703 144
$play.Height=42; $play.BackColor=$script:Teal; $play.ForeColor=[Drawing.Color]::White
$play.FlatAppearance.BorderSize=0; $play.Font=New-Object Drawing.Font('Segoe UI Semibold',12)
$form.AcceptButton=$play
# Keep the existing connection controls together; the web page is a native top-level view.
$connectionControls=@($form.Controls)
$tabs=New-Object Windows.Forms.TabControl
$tabs.Dock='Fill'
$connectionTab=New-Object Windows.Forms.TabPage
$connectionTab.Text='Jugar'; $connectionTab.BackColor=$script:Paper; $connectionTab.AutoScroll=$true
$connectionTab.AutoScrollMinSize=New-Object Drawing.Size(780,512)
$webTab=New-Object Windows.Forms.TabPage
$webTab.Text='Logros y mazmorras'; $webTab.BackColor=$script:Paper
$tabs.TabPages.Add($connectionTab); $tabs.TabPages.Add($webTab)
foreach ($control in $connectionControls) { $form.Controls.Remove($control); $connectionTab.Controls.Add($control) }
$form.Controls.Add($tabs)
$webLayout=New-Object Windows.Forms.TableLayoutPanel
$webLayout.Dock='Fill'; $webLayout.ColumnCount=1; $webLayout.RowCount=2
$webLayout.Margin=0; $webLayout.Padding=0
$null=$webLayout.RowStyles.Add((New-Object Windows.Forms.RowStyle([Windows.Forms.SizeType]::Absolute,100)))
$null=$webLayout.RowStyles.Add((New-Object Windows.Forms.RowStyle([Windows.Forms.SizeType]::Percent,100)))
$webTab.Controls.Add($webLayout)
$webToolbar=New-Object Windows.Forms.Panel
$webToolbar.Size=New-Object Drawing.Size(1000,100)
$webToolbar.Dock='Fill'; $webToolbar.Margin=0; $webLayout.Controls.Add($webToolbar,0,0)
$null=Label $webToolbar 'Página de logros (URL del servidor)' 12 9 290
$webAddress=Input $webToolbar 'achievements_url' 12 35 660
$webAddress.Anchor='Top,Left,Right'
$webOpen=Button $webToolbar 'Abrir con esta cuenta' 690 31 190
$webOpen.Anchor='Top,Right'
$webInstall=Button $webToolbar 'Instalar WebView2' 690 65 190
$webInstall.Anchor='Top,Right'; $webInstall.Visible=$false
$webStatus=Label $webToolbar 'Inicia el juego y abre los logros con la cuenta seleccionada.' 12 70 670
$webStatus.Anchor='Top,Left,Right'
$webErrorBox=New-Object Windows.Forms.TextBox
$webErrorBox.Location=New-Object Drawing.Point(12,103)
$webErrorBox.Size=New-Object Drawing.Size(660,125)
$webErrorBox.Multiline=$true; $webErrorBox.ReadOnly=$true; $webErrorBox.ScrollBars='Both'
$webErrorBox.WordWrap=$true; $webErrorBox.Anchor='Top,Left,Right'; $webErrorBox.Visible=$false
$webToolbar.Controls.Add($webErrorBox)
$webCopyError=Button $webToolbar 'Copiar error' 690 105 190
$webCopyError.Anchor='Top,Right'; $webCopyError.Visible=$false
$script:WebErrorDetails=''
$webHost=New-Object Windows.Forms.Panel
$webHost.Dock='Fill'; $webHost.Margin=0; $webLayout.Controls.Add($webHost,0,1)
function Protect-WebErrorText($text) {
    $safe=[string]$text
    # SDK errors can include URLs; query strings and fragments must never reach the clipboard.
    $safe=[regex]::Replace($safe,'(?i)(https?://[^\s?#"''<>]+)[?#][^\s"''<>]*','$1[oculto]')
    $safe=[regex]::Replace($safe,'(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+','Bearer [oculto]')
    $safe=[regex]::Replace($safe,'(?i)(["'']?(?:password|password_confirm|api_token|remember_token|access_token|session_token|token)["'']?\s*[:=]\s*["'']?)[^\s,"'';&<>]+','$1[oculto]')
    foreach ($control in @($password,$username)) {
        if ($control -and $control.Text) { $safe=$safe.Replace([string]$control.Text,'[oculto]') }
    }
    return $safe
}
function Clear-WebError {
    $script:WebErrorDetails=''
    $webErrorBox.Clear(); $webErrorBox.Visible=$false; $webCopyError.Visible=$false
    $webLayout.RowStyles[0].Height=100
}
function Set-WebError($exception) {
    $current=if ($exception -is [System.Management.Automation.ErrorRecord]) { $exception.Exception } else { $exception }
    $lines=New-Object 'Collections.Generic.List[string]'
    for ($depth=0; $current -and $depth -lt 6; $depth++) {
        $message=if ($current.Message) { [string]$current.Message } else { [string]$current }
        $kind=$current.GetType().FullName
        $code=if ($current -is [Exception]) { ' (HRESULT 0x'+('{0:X8}' -f $current.HResult)+')' } else { '' }
        $lines.Add($kind+$code+"`r`n"+$message)
        $current=$current.InnerException
    }
    if (!$lines.Count) { $lines.Add('WebView2 no pudo inicializarse y no proporcionó más detalles.') }
    $script:WebErrorDetails=Protect-WebErrorText ($lines -join "`r`n`r`n")
    $webErrorBox.Text=$script:WebErrorDetails
    $webErrorBox.Visible=$true; $webCopyError.Visible=$true
    $webLayout.RowStyles[0].Height=240
    $webStatus.Text='No se pudieron abrir los logros. El detalle completo aparece debajo.'
    $status.Text='Error al abrir los logros. Consulta el detalle en su pestaña.'
}
$webCopyError.Add_Click({
    if (!$script:WebErrorDetails) { return }
    try {
        [Windows.Forms.Clipboard]::SetText($script:WebErrorDetails)
        $webStatus.Text='Error copiado. Puedes pegarlo para revisar el problema.'
    } catch { $webStatus.Text='No se pudo copiar. Puedes seleccionar y copiar el texto del detalle.' }
})
function Reset-WebSession {
    $script:WebEpoch++
    $script:WebIdentity=''
    if ($script:WebView) {
        try { $script:WebView.Stop(); $script:WebView.Dispose() } catch { }
        $script:WebView=$null
    }
    $webHost.Controls.Clear()
    $webStatus.Text='Abre los logros con la cuenta seleccionada en Jugar.'
    if ($webErrorBox) { Clear-WebError }
}
function Assert-WebDependency($path,$expectedHash) {
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) {
        throw 'Faltan archivos de WebView2. Extrae el parche completo del minilauncher.'
    }
    $actual=(Get-FileHash -LiteralPath $path -Algorithm SHA256 -ErrorAction Stop).Hash
    if ($actual -ne $expectedHash) {
        throw ('El archivo de WebView2 no coincide con el paquete oficial: '+[IO.Path]::GetFileName($path)+'. Extrae de nuevo el parche completo.')
    }
}
function Initialize-WebDependencies {
    if ($script:WebAvailable) { return }
    $folder=Join-Path $PSScriptRoot 'webview2'
    # Select the official SDK target for the current PowerShell runtime.
    $modern=$PSVersionTable.PSEdition -eq 'Core'
    $managedFolder=if ($modern) { Join-Path $folder 'netcore' } else { $folder }
    $architecture=if ([IntPtr]::Size -eq 4) { 'x86' } elseif ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'arm64' } else { 'x64' }
    $loader=Join-Path $folder ($architecture+'\WebView2Loader.dll')
    # Digests are pinned to Microsoft.Web.WebView2 1.0.3650.58. Do not trust
    # a downloaded file merely because it shares a known assembly filename.
    $nativeHashes=@{
        x64='8427b1fc58ec707813e5c0a51eb5d69397bb333250a7b891be4d3b123f1e0f1c'
        x86='44ab92c2246ebfb5f98aa5726626fb44beb61543f2ef1803338af9fd295e63f0'
        arm64='df5816669f5123595c475d97929240d7d0e04f0bdc7dbe18af1dda42348b73a6'
    }
    $core=Join-Path $managedFolder 'Microsoft.Web.WebView2.Core.dll'
    $forms=Join-Path $managedFolder 'Microsoft.Web.WebView2.WinForms.dll'
    $formsHash=if ($modern) { '08c7014d311979c3e37ea56ae8233f3bdf363013498b11b1c7ee2bcfb29cf08a' } else { 'bbc50575b6a191fd433df854227921937f256e91a81b47c697d95ea8ed027ff6' }
    Assert-WebDependency $core '2b999d1775004e98b32f281f4518f3952df650970748527ef5b54fa9979d6c9c'
    Assert-WebDependency $forms $formsHash
    Assert-WebDependency $loader $nativeHashes[$architecture]
    # Explorer can propagate the ZIP's Internet-zone mark to its DLLs. Remove
    # that mark only from these verified SDK files, never from arbitrary files
    # or by weakening machine-wide .NET/execution policies.
    foreach ($path in @($core,$forms,$loader)) {
        try { Unblock-File -LiteralPath $path -ErrorAction Stop }
        catch { throw ('No se pudo desbloquear WebView2: '+[IO.Path]::GetFileName($path)+'. Extrae el parche en una carpeta local con permisos de escritura.') }
    }
    if (!('WakfuLauncher.NativeLoader' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace WakfuLauncher {
    public static class NativeLoader {
        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
        public static extern IntPtr LoadLibrary(string path);
    }
}
'@
    }
    if ([WakfuLauncher.NativeLoader]::LoadLibrary($loader) -eq [IntPtr]::Zero) {
        throw 'No se pudo cargar WebView2. Extrae el parche completo y usa Windows de 64 bits.'
    }
    Add-Type -Path $core -ErrorAction Stop
    Add-Type -Path $forms -ErrorAction Stop
    try {
        $runtime=[Microsoft.Web.WebView2.Core.CoreWebView2Environment]::GetAvailableBrowserVersionString($null)
        if (!$runtime) { throw 'Missing runtime' }
    } catch {
        $webInstall.Visible=$true
        throw 'Instala Microsoft Edge WebView2 Runtime con el botón de esta pestaña y vuelve a abrir los logros.'
    }
    $script:WebAvailable=$true; $webInstall.Visible=$false
}

function Show-WebPage($address) {
    $target=$null; $configured=$null
    if (![Uri]::TryCreate([string]$address,[UriKind]::Absolute,[ref]$target) -or
        ![Uri]::TryCreate($webAddress.Text.Trim(),[UriKind]::Absolute,[ref]$configured) -or
        $target.Scheme -notin @('http','https') -or $target.UserInfo -or
        $target.GetLeftPart([UriPartial]::Authority) -ne $configured.GetLeftPart([UriPartial]::Authority) -or
        $target.AbsolutePath -ne '/player/') { throw 'La página de logros no coincide con el servidor seleccionado.' }
    Initialize-WebDependencies
    Reset-WebSession
    $script:WebIdentity=$script:CurrentId+'|'+$username.Text.Trim()
    $view=New-Object Microsoft.Web.WebView2.WinForms.WebView2
    $view.Dock='Fill'
    $properties=New-Object Microsoft.Web.WebView2.WinForms.CoreWebView2CreationProperties
    $sessionRoot=Join-Path ([IO.Path]::GetTempPath()) ('Wakfu-MiniLauncher-'+[guid]::NewGuid().ToString('N'))
    $properties.UserDataFolder=$sessionRoot; $script:WebFolders.Add($sessionRoot)
    $properties.IsInPrivateModeEnabled=$true
    $view.CreationProperties=$properties
    $view.Tag=[pscustomobject]@{url=$target.AbsoluteUri;origin=$target.GetLeftPart([UriPartial]::Authority);epoch=$script:WebEpoch}
    $script:WebView=$view; $webHost.Controls.Add($view)
    $view.Add_CoreWebView2InitializationCompleted({
        param($sender,$event)
        if ($sender.IsDisposed -or $sender.Tag.epoch -ne $script:WebEpoch -or $sender -ne $script:WebView) { return }
        if (!$event.IsSuccess) {
            Set-WebError $event.InitializationException
            $webInstall.Visible=$true
            return
        }
        $core=$sender.CoreWebView2
        $core.Settings.AreDevToolsEnabled=$false
        $core.Settings.AreDefaultContextMenusEnabled=$false
        $core.Settings.AreHostObjectsAllowed=$false
        $core.Settings.IsWebMessageEnabled=$false
        $core.Settings.IsPasswordAutosaveEnabled=$false
        $core.Settings.IsGeneralAutofillEnabled=$false
        $core.Add_NavigationStarting({
            param($browser,$navigation)
            $destination=$null
            if (!$script:WebView -or ![Uri]::TryCreate($navigation.Uri,[UriKind]::Absolute,[ref]$destination) -or
                $destination.GetLeftPart([UriPartial]::Authority) -ne $script:WebView.Tag.origin -or
                $destination.Scheme -notin @('http','https') -or $destination.UserInfo) {
                $navigation.Cancel=$true
                $webStatus.Text='Solo se abre la página del servidor configurado.'
            }
        })
        $core.Add_NewWindowRequested({ param($browser,$event) $event.Handled=$true })
        $core.Add_PermissionRequested({ param($browser,$event) $event.State=[Microsoft.Web.WebView2.Core.CoreWebView2PermissionState]::Deny })
        $sender.Add_NavigationCompleted({
            param($browser,$navigation)
            if ($browser -eq $script:WebView) {
                $webStatus.Text=if ($navigation.IsSuccess) { 'Logros de '+$username.Text.Trim()+'. Las acciones se aplican al personaje conectado.' } else { 'No se pudo cargar la página. Comprueba la conexión y pulsa Abrir.' }
            }
        })
        $core.Navigate($sender.Tag.url)
        $sender.Tag.url=''
    })
    # Initialization completion is raised on this UI thread; never block its message pump.
    $view.Tag | Add-Member -NotePropertyName initTask -NotePropertyValue ($view.EnsureCoreWebView2Async($null))
    $webStatus.Text='Cargando la página de logros...'
}
$saveTimer=New-Object Windows.Forms.Timer; $saveTimer.Interval=900
$pollTimer=New-Object Windows.Forms.Timer; $pollTimer.Interval=120
function Start-Backend($action,$payload) {
    $info=New-Object Diagnostics.ProcessStartInfo
    $info.FileName=Join-Path $script:Root 'python\python.exe'
    $backend=Join-Path $PSScriptRoot 'launcher_backend.py'
    $info.Arguments='-B "'+$backend+'" --action '+$action
    $info.WorkingDirectory=$script:Root
    $info.UseShellExecute=$false; $info.CreateNoWindow=$true
    $info.RedirectStandardInput=$true; $info.RedirectStandardOutput=$true; $info.RedirectStandardError=$true
    $info.StandardOutputEncoding=New-Object Text.UTF8Encoding($false)
    $info.StandardErrorEncoding=New-Object Text.UTF8Encoding($false)
    $info.EnvironmentVariables['PYTHONIOENCODING']='utf-8'
    $p=New-Object Diagnostics.Process; $p.StartInfo=$info
    $null=$p.Start()
    $p | Add-Member -NotePropertyName OutputTask -NotePropertyValue ($p.StandardOutput.ReadToEndAsync())
    $p | Add-Member -NotePropertyName ErrorTask -NotePropertyValue ($p.StandardError.ReadToEndAsync())
    # Write explicit UTF-8 bytes; Windows PowerShell 5.1 may use an OEM code page.
    $json=$payload | ConvertTo-Json -Depth 12 -Compress
    $bytes=[Text.Encoding]::UTF8.GetBytes($json)
    $inputStream=$p.StandardInput.BaseStream
    $inputStream.Write($bytes,0,$bytes.Length)
    $inputStream.Flush(); $inputStream.Close()
    return $p
}
function Read-Backend($p) {
    $raw=$p.OutputTask.GetAwaiter().GetResult(); $null=$p.ErrorTask.GetAwaiter().GetResult()
    try { $result=$raw | ConvertFrom-Json } catch { throw 'No se pudo leer la respuesta del launcher.' }
    if (!$result.ok) { throw [string]$result.error }
    return $result
}
function Request-Backend($action,$payload) {
    $p=Start-Backend $action $payload
    try {
        if (!$p.WaitForExit(12000)) { $p.Kill(); throw 'El launcher tardó demasiado en responder.' }
        return Read-Backend $p
    } finally { $p.Dispose() }
}
function Payload {
    $fields=@{}
    foreach ($key in @('name','server_host','chat_host','http_url','shop_url','api_url','certificate','achievements_url')) {
        $fields[$key]=$script:Controls[$key].Text.Trim()
    }
    foreach ($key in @('dispatch_port','chat_port')) {
        $number=0
        if (![int]::TryParse($script:Controls[$key].Text,[ref]$number)) { throw 'Revisa los puertos: deben ser números.' }
        $fields[$key]=$number
    }
    $worldPort=0
    if (![int]::TryParse($script:Controls['game_port'].Text,[ref]$worldPort)) { throw 'Revisa el puerto del mundo.' }
    $fields['game_ports']=@($worldPort)
    $fields['id']=$script:CurrentId
    return @{server=$fields;selected_id=$script:CurrentId;username=$username.Text.Trim();password=$password.Text;remember=$remember.Checked;password_edited=$script:PasswordEdited}
}
function Apply-State($data) {
    $nextIdentity=[string]$data.selected_id+'|'+[string]$data.username
    if ($script:WebIdentity -and $script:WebIdentity -ne $nextIdentity) { Reset-WebSession }
    $script:Loading=$true
    try {
        $script:Data=$data
        $script:CurrentId=[string]$data.selected_id
        $serverBox.Items.Clear()
        foreach ($server in $data.servers) { $null=$serverBox.Items.Add($server) }
        $chosen=$null
        foreach ($server in $serverBox.Items) { if ($server.id -eq $data.selected_id) { $chosen=$server; break } }
        if (!$chosen -and $serverBox.Items.Count -gt 0) { $chosen=$serverBox.Items[0] }
        if ($chosen) {
            $serverBox.SelectedItem=$chosen
            foreach ($key in @('name','server_host','chat_host','http_url','shop_url','api_url','certificate','dispatch_port','chat_port','achievements_url')) {
                $script:Controls[$key].Text=[string]$chosen.$key
            }
            $script:Controls['game_port'].Text=[string]$chosen.game_ports[0]
            if (!$script:Controls['achievements_url'].Text) { $script:Controls['achievements_url'].Text='https://wakemu.p.hectorpulido.net' }
        }
        $username.Items.Clear()
        foreach ($account in $data.accounts) { $null=$username.Items.Add([string]$account) }
        $username.Text=[string]$data.username
        $password.Text=[string]$data.password
        $remember.Checked=[bool]$data.remember
        $script:PasswordEdited=$false
        $script:LoadedIdentity=$script:CurrentId+'|'+$username.Text.Trim()
        $script:LastDomain=$script:Controls['server_host'].Text.Trim().ToLowerInvariant()
    } finally { $script:Loading=$false }
}
function Schedule-Save {
    if ($script:Loading -or $script:Busy) { return }
    $saveTimer.Stop(); $saveTimer.Start()
}
function Save-Current {
    $saveTimer.Stop()
    $result=Request-Backend 'save' (Payload)
    $script:Data=$result.state
    if ($serverBox.SelectedItem -and $serverBox.SelectedItem.id -eq $script:CurrentId) {
        $serverBox.SelectedItem.name=$script:Controls['name'].Text.Trim()
        # Refresh the ComboBox display without changing selection or editable fields.
        $serverBox.DisplayMember=''; $serverBox.DisplayMember='name'
    }
    $status.Text='Guardado. Recuperaremos esta selección al abrir el launcher.'
    return $result
}
function Begin-Action($action,$requestedBody=$null) {
    if ($script:Busy) { return }
    try {
        if ($action -eq 'check' -and $saveTimer.Enabled) { $null=Save-Current }
        $saveTimer.Stop()
        $body=if ($null -ne $requestedBody) { $requestedBody } else { Payload }
        if ($action -eq 'web-login') { Initialize-WebDependencies; Reset-WebSession }
        $script:ActiveEpoch=$script:WebEpoch
        $script:ActiveProcess=Start-Backend $action $body
        $script:ActiveAction=$action; $script:Busy=$true
        $group.Enabled=$false; $accountBox.Enabled=$false; $serverBox.Enabled=$false
        $new.Enabled=$false; $forget.Enabled=$false; $checkButton.Enabled=$false; $play.Enabled=$false; $register.Enabled=$false
        $webOpen.Enabled=$false; $webAddress.Enabled=$false
        $domain.Enabled=$false; $detect.Enabled=$false; $advanced.Enabled=$false
        $status.Text=if ($action -eq 'play') { 'Conectando con tu servidor...' } elseif ($action -eq 'web-login') { 'Abriendo los logros de tu cuenta...' } elseif ($action -eq 'register') { 'Creando tu nueva cuenta...' } elseif ($action -eq 'discover') { 'Detectando la configuración del servidor...' } else { 'Comprobando los servicios configurados...' }
        if ($action -eq 'web-login') { $webStatus.Text=$status.Text }
        $pollTimer.Start()
    } catch {
        $status.Text=$_.Exception.Message
        if ($action -eq 'web-login') { Set-WebError $_ }
    }
}
$saveTimer.Add_Tick({
    if ($script:Busy) { $saveTimer.Stop(); return }
    try { $null=Save-Current } catch { $saveTimer.Stop(); $status.Text=$_.Exception.Message }
})
$pollTimer.Add_Tick({
    if (!$script:ActiveProcess -or !$script:ActiveProcess.HasExited) { return }
    $pollTimer.Stop()
    try {
        $result=Read-Backend $script:ActiveProcess
        $status.Text=[string]$result.message
        if ($script:ActiveAction -eq 'check' -and $result.checks) {
            $lines=@($result.checks | ForEach-Object { $_.service+': '+$(if ($_.ok) {'Disponible'} else {'Sin conexion'}) })
            $null=[Windows.Forms.MessageBox]::Show(($lines -join "`r`n"),'Conexión al servidor','OK','Information')
        }
        if ($script:ActiveAction -eq 'web-login' -and $script:ActiveEpoch -eq $script:WebEpoch) {
            Show-WebPage ([string]$result.url)
        }
        if ($script:ActiveAction -eq 'discover') {
            Apply-Discovery $result
        }
        if ($script:ActiveAction -eq 'register') {
            Reset-WebSession
            Apply-State $result.state
            $status.Text=[string]$result.message
        }
        if ($script:ActiveAction -eq 'play') {
            # Refresh the saved account list without replacing fields while a user types.
            $refreshed=Request-Backend 'state' @{selected_id=$serverBox.SelectedItem.id;username=$username.Text}
            Apply-State $refreshed.state
            $status.Text=[string]$result.message
        }
    } catch {
        $status.Text=$_.Exception.Message
        if ($script:ActiveAction -eq 'web-login') { Set-WebError $_ }
    }
    finally {
        $script:ActiveProcess.Dispose(); $script:ActiveProcess=$null; $script:Busy=$false
        $group.Enabled=$true; $accountBox.Enabled=$true; $serverBox.Enabled=$true
        $new.Enabled=$true; $forget.Enabled=$true; $checkButton.Enabled=$true; $play.Enabled=$true; $register.Enabled=$true
        $webOpen.Enabled=$true; $webAddress.Enabled=$true
        $domain.Enabled=$true; $detect.Enabled=$true; $advanced.Enabled=$true
    }
})
foreach ($key in @('name','server_host','chat_host','http_url','shop_url','api_url','certificate','dispatch_port','chat_port','game_port','achievements_url')) {
    $script:Controls[$key].Tag=$key
    $script:Controls[$key].Add_TextChanged({
        if (!$script:Loading) {
            if ($this.Tag -ne 'name') {
                Reset-WebSession
                $script:Loading=$true; $password.Text=''; $script:Loading=$false; $script:PasswordEdited=$false
                $script:LoadedIdentity=''
            }
            Schedule-Save
        }
    })
}
# Commit the previous field's pending changes before account or endpoint edits.
$flushBeforeEdit={
    if (!$script:Loading -and !$script:Busy -and $saveTimer.Enabled) {
        try { $null=Save-Current } catch { $status.Text=$_.Exception.Message }
    }
}
$username.Add_Enter($flushBeforeEdit)
foreach ($key in @('name','server_host','chat_host','http_url','shop_url','api_url','certificate','dispatch_port','chat_port','game_port','achievements_url')) {
    $script:Controls[$key].Add_Enter($flushBeforeEdit)
}
$password.Add_TextChanged({ if (!$script:Loading) { $script:PasswordEdited=$true; Schedule-Save } })
$username.Add_TextChanged({
    if (!$script:Loading) {
        Reset-WebSession
        $script:Loading=$true; $password.Text=''; $remember.Checked=$true; $script:Loading=$false
        $script:PasswordEdited=$false; $script:LoadedIdentity=''; Schedule-Save
    }
})
$remember.Add_CheckedChanged({ Schedule-Save })
$show.Add_CheckedChanged({ $password.UseSystemPasswordChar=!$show.Checked })
$serverBox.Add_SelectionChangeCommitted({
    $wantedId=[string]$serverBox.SelectedItem.id
    Reset-WebSession
    try {
        if ($saveTimer.Enabled) { $null=Save-Current }
        $saveTimer.Stop()
        $result=Request-Backend 'state' @{selected_id=$wantedId}
        Apply-State $result.state
        $status.Text='Servidor selecciónado. Los cambios se guardan automáticamente.'
        Schedule-Save
    } catch { $status.Text=$_.Exception.Message }
})
$loadAccount={
    if ($script:Loading -or $script:Busy -or !$serverBox.SelectedItem) { return }
    $wanted=$username.Text.Trim()
    $identity=$script:CurrentId+'|'+$wanted
    if ($identity -eq $script:LoadedIdentity) { return }
    try {
        # Persist endpoint edits before looking up a password for this selection.
        if ($saveTimer.Enabled) { $null=Save-Current }
        $saveTimer.Stop()
        $result=Request-Backend 'state' @{selected_id=$script:CurrentId;username=$wanted}
        $script:Loading=$true
        $password.Text=[string]$result.state.password
        $remember.Checked=if (@($result.state.accounts) -contains $wanted) { [bool]$result.state.remember } else { $true }
        $script:Loading=$false
        $script:PasswordEdited=$false; $script:LoadedIdentity=$identity; Schedule-Save
    } catch { $script:Loading=$false; $status.Text=$_.Exception.Message }
}
$username.Add_SelectionChangeCommitted($loadAccount)
$username.Add_Leave($loadAccount)
$new.Add_Click({
    Reset-WebSession
    if ($saveTimer.Enabled) {
        try { $null=Save-Current } catch { $status.Text=$_.Exception.Message; return }
    }
    $saveTimer.Stop()
    $script:Loading=$true
    try {
        $fresh=[pscustomobject]@{id=[guid]::NewGuid().ToString('N');name='Nuevo servidor';server_host='wakemu.p.hectorpulido.net';dispatch_port=15558;game_ports=@(15556);chat_port=16337;chat_host='wakemu.p.hectorpulido.net';api_url='https://wakemu.p.hectorpulido.net';http_url='https://wakemu.p.hectorpulido.net';shop_url='https://wakemu.p.hectorpulido.net';certificate='';achievements_url='https://wakemu.p.hectorpulido.net'}
        $null=$serverBox.Items.Add($fresh); $serverBox.SelectedItem=$fresh
        $script:CurrentId=[string]$fresh.id
        $script:LoadedIdentity=''
        foreach ($key in @('name','server_host','chat_host','http_url','shop_url','api_url','certificate','dispatch_port','chat_port','achievements_url')) { $script:Controls[$key].Text=[string]$fresh.$key }
        $script:Controls['game_port'].Text='15556'; $username.Items.Clear(); $username.Text=''; $password.Text=''
        $script:PasswordEdited=$false
    } finally { $script:Loading=$false }
    $script:Controls['name'].Focus(); $script:Controls['name'].SelectAll(); Schedule-Save
})
$browse.Add_Click({
    if ($saveTimer.Enabled) { try { $null=Save-Current } catch { $status.Text=$_.Exception.Message; return } }
    $dialog=New-Object Windows.Forms.OpenFileDialog
    $dialog.Title='Certificado del servidor'; $dialog.Filter='Certificados (*.pem;*.crt;*.cer)|*.pem;*.crt;*.cer|Todos los archivos (*.*)|*.*'
    if ($dialog.ShowDialog() -eq 'OK') { $script:Controls['certificate'].Text=$dialog.FileName }
    $dialog.Dispose()
})
$forget.Add_Click({
    Reset-WebSession
    try {
        $result=Request-Backend 'forget' (Payload)
        Apply-State $result.state; $status.Text='Acceso guardado eliminado.'
    } catch { $status.Text=$_.Exception.Message }
})
function Update-ConnectionLayout {
    $accountTop=if ($script:AdvancedExpanded) { 646 } else { 268 }
    $group.Visible=$script:AdvancedExpanded
    $accountBox.Top=$accountTop; $status.Top=$accountTop+137
    $forget.Top=$accountTop+175; $register.Top=$accountTop+175
    $checkButton.Top=$accountTop+171; $play.Top=$accountTop+167
    $connectionTab.AutoScrollMinSize=New-Object Drawing.Size(780,($accountTop+244))
    $advanced.Text=if ($script:AdvancedExpanded) { 'Ocultar configuración avanzada' } else { 'Configuración avanzada >' }
    $connectionTab.PerformLayout()
}
function Begin-Discovery {
    if ($script:Busy -or $script:Loading) { return }
    $server=@{}
    if ($serverBox.SelectedItem) {
        foreach ($property in $serverBox.SelectedItem.PSObject.Properties) { $server[$property.Name]=$property.Value }
    }
    $server['id']=$script:CurrentId
    $server['name']=$script:Controls['name'].Text.Trim()
    $server['server_host']=$domain.Text.Trim()
    if ($domain.Text.Trim().ToLowerInvariant() -ne $script:LastDomain) {
        # A newly entered domain must never retain another server's hidden authentication endpoint.
        $origin='https://'+$domain.Text.Trim()
        $script:Loading=$true
        try {
            foreach ($key in @('api_url','http_url','shop_url','achievements_url')) { $script:Controls[$key].Text=$origin; $server[$key]=$origin }
            $script:Controls['chat_host'].Text=$domain.Text.Trim(); $server['chat_host']=$domain.Text.Trim()
            $script:Controls['certificate'].Text=''; $server['certificate']=''
            $script:Controls['dispatch_port'].Text='15558'; $server['dispatch_port']=15558
            $script:Controls['chat_port'].Text='16337'; $server['chat_port']=16337
            $script:Controls['game_port'].Text='15556'; $server['game_ports']=@(15556)
        } finally { $script:Loading=$false }
    }
    $script:DiscoveryDomain=$domain.Text.Trim().ToLowerInvariant()
    $script:DiscoveryId=$script:CurrentId
    # Discovery is public metadata: send no username, password or remembered credentials.
    Begin-Action 'discover' @{server=$server}
}
function Apply-Discovery($result) {
    if ($script:CurrentId -ne $script:DiscoveryId -or $domain.Text.Trim().ToLowerInvariant() -ne $script:DiscoveryDomain) {
        $status.Text='Se descartó una configuración de un servidor anterior.'; return
    }
    if (!$result.server -or [string]$result.server.id -ne $script:CurrentId) { throw 'La configuración detectada no corresponde al servidor seleccionado.' }
    $previousApi=$script:Controls['api_url'].Text.Trim().TrimEnd('/')
    $previousUsername=$username.Text.Trim(); $previousPassword=$password.Text
    $script:Loading=$true
    try {
        foreach ($key in @('name','server_host','chat_host','http_url','shop_url','api_url','certificate','dispatch_port','chat_port','achievements_url')) {
            $script:Controls[$key].Text=[string]$result.server.$key
        }
        $script:Controls['game_port'].Text=[string]$result.server.game_ports[0]
    } finally { $script:Loading=$false }
    Reset-WebSession
    $saved=Request-Backend 'save' (Payload)
    Apply-State $saved.state
    # Keep a deliberately unsaved password only while the authentication origin and account stay identical.
    if (!$remember.Checked -and !$password.Text -and $previousApi -eq $script:Controls['api_url'].Text.Trim().TrimEnd('/') -and $previousUsername -eq $username.Text.Trim()) {
        $script:Loading=$true
        try { $password.Text=$previousPassword } finally { $script:Loading=$false }
    }
    $script:LastDomain=$domain.Text.Trim().ToLowerInvariant()
    $status.Text=[string]$result.message
}
$advanced.Add_Click({
    $script:AdvancedExpanded=!$script:AdvancedExpanded
    Update-ConnectionLayout
    if (!$script:AdvancedExpanded -and $form.WindowState -eq [Windows.Forms.FormWindowState]::Normal) { $form.ClientSize=New-Object Drawing.Size($form.ClientSize.Width,560) }
})
$detect.Add_Click({ Begin-Discovery })
$domain.Add_Leave({
    if (!$script:Loading -and !$script:Busy -and $domain.Text.Trim().ToLowerInvariant() -ne $script:LastDomain) { Begin-Discovery }
})
Update-ConnectionLayout
function Begin-Registration {
    if ($script:Busy) { return }
    try {
        if ($saveTimer.Enabled) { $null=Save-Current }
        $current=Payload
    } catch { $status.Text=$_.Exception.Message; return }
    $dialog=New-Object Windows.Forms.Form
    $dialog.Text='Crear una cuenta de Wakemu'
    $dialog.ClientSize=New-Object Drawing.Size(460,350)
    $dialog.FormBorderStyle='FixedDialog'; $dialog.MaximizeBox=$false; $dialog.MinimizeBox=$false
    $dialog.StartPosition='CenterParent'; $dialog.Font=$form.Font
    $dialog.BackColor=$script:Paper; $dialog.ForeColor=$script:Ink
    $null=Label $dialog ('Servidor: '+$current.server.name) 20 16 420
    $null=Label $dialog 'Nuevo usuario' 20 50 420
    $registrationUsername=New-Object Windows.Forms.TextBox
    $registrationUsername.Location=New-Object Drawing.Point(20,76)
    $registrationUsername.Size=New-Object Drawing.Size(420,28); $registrationUsername.MaxLength=128
    $dialog.Controls.Add($registrationUsername)
    $null=Label $dialog 'Contraseña' 20 112 420
    $registrationPassword=New-Object Windows.Forms.TextBox
    $registrationPassword.Location=New-Object Drawing.Point(20,138)
    $registrationPassword.Size=New-Object Drawing.Size(420,28); $registrationPassword.MaxLength=256
    $registrationPassword.UseSystemPasswordChar=$true; $dialog.Controls.Add($registrationPassword)
    $null=Label $dialog 'Confirmar contraseña' 20 174 420
    $registrationConfirmation=New-Object Windows.Forms.TextBox
    $registrationConfirmation.Location=New-Object Drawing.Point(20,200)
    $registrationConfirmation.Size=New-Object Drawing.Size(420,28); $registrationConfirmation.MaxLength=256
    $registrationConfirmation.UseSystemPasswordChar=$true; $dialog.Controls.Add($registrationConfirmation)
    $registrationMessage=Label $dialog 'La cuenta se creará al pulsar Crear cuenta.' 20 240 420
    $registrationMessage.Height=42
    $create=Button $dialog 'Crear cuenta' 280 296 160
    $cancel=Button $dialog 'Cancelar' 128 296 140
    $cancel.DialogResult=[Windows.Forms.DialogResult]::Cancel
    $dialog.AcceptButton=$create; $dialog.CancelButton=$cancel
    $dialog.Tag=@{username=$registrationUsername;password=$registrationPassword;confirmation=$registrationConfirmation;message=$registrationMessage}
    $create.Add_Click({
        $modal=$this.FindForm(); $fields=$modal.Tag
        if (!$fields.username.Text.Trim() -or !$fields.password.Text) {
            $fields.message.Text='Escribe un usuario y una contraseña.'; return
        }
        if ($fields.password.Text -cne $fields.confirmation.Text) {
            $fields.message.Text='Las contraseñas no coinciden.'; return
        }
        $modal.DialogResult=[Windows.Forms.DialogResult]::OK
    })
    try {
        if ($dialog.ShowDialog($form) -eq [Windows.Forms.DialogResult]::OK) {
            $body=@{server=$current.server;username=$registrationUsername.Text.Trim();password=$registrationPassword.Text;password_confirm=$registrationConfirmation.Text;remember=$remember.Checked}
            # Only the explicit registration request is sent; selection changes after backend success.
            Begin-Action 'register' $body
        }
    } finally {
        $registrationPassword.Clear(); $registrationConfirmation.Clear(); $dialog.Dispose()
    }
}
$register.Add_Click({ Begin-Registration })
$play.Add_Click({ Begin-Action 'play' })
$checkButton.Add_Click({ Begin-Action 'check' })
$webOpen.Add_Click({ Begin-Action 'web-login' })
$webInstall.Add_Click({ Start-Process 'https://developer.microsoft.com/microsoft-edge/webview2/' })
$tabs.Add_SelectedIndexChanged({
    $form.AcceptButton=if ($tabs.SelectedTab -eq $connectionTab) { $play } else { $webOpen }
    if ($tabs.SelectedTab -eq $webTab -and $form.ClientSize.Width -lt 1000 -and $form.WindowState -eq [Windows.Forms.FormWindowState]::Normal) { $form.ClientSize=New-Object Drawing.Size(1040,800) }
    if ($tabs.SelectedTab -eq $webTab -and !$script:WebView -and !$script:Busy -and $username.Text.Trim() -and $password.Text) { Begin-Action 'web-login' }
})
$form.Add_Shown({
    try {
        $result=Request-Backend 'state' @{}
        Apply-State $result.state
        $status.Text='Elige un servidor y una cuenta. Los cambios se guardan automáticamente.'
        if ($Check) { Begin-Action 'check' }
    } catch { $script:Loading=$false; $status.Text=$_.Exception.Message }
})
$form.Add_FormClosing({
    if ($script:Busy) { $_.Cancel=$true; $status.Text='Espera a que termine la conexion.'; return }
    $saveTimer.Stop()
    try { $null=Save-Current } catch {
        $answer=[Windows.Forms.MessageBox]::Show('Hay cambios incompletos que no se pueden guardar. ¿Cerrar de todos modos?','Cerrar launcher','YesNo','Question')
        if ($answer -ne 'Yes') { $_.Cancel=$true }
    }
})
$form.Add_FormClosed({ Reset-WebSession })
[void]$form.ShowDialog()
# Private browsing avoids persisting session storage; remove best-effort browser cache after disposal.
foreach ($folder in $script:WebFolders) { try { Remove-Item -LiteralPath $folder -Recurse -Force -ErrorAction Stop } catch { } }
$saveTimer.Dispose(); $pollTimer.Dispose(); $form.Dispose()
