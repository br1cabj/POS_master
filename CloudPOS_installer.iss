#define MyAppName "CloudPOS"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Bruno"
#define MyAppExeName "CloudPOS.exe"
#define MyAppSourceDir "dist\CloudPOS"

[Setup]
; Identificador único de la app (no cambiar entre versiones)
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=
AppSupportURL=
AppUpdatesURL=

; Carpeta de instalación por defecto
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}

; No pedir permisos de admin (instala por usuario si no es admin)
PrivilegesRequiredOverridesAllowed=dialog

; Nombre del instalador generado
OutputDir=installer_output
OutputBaseFilename=CloudPOS_Setup_v{#MyAppVersion}

; Ícono del instalador
SetupIconFile=icono.ico

; Compresión
Compression=lzma2/ultra64
SolidCompression=yes

; Mostrar asistente moderno
WizardStyle=modern

; Permitir que el usuario elija si crea acceso directo en escritorio
DisableProgramGroupPage=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
; Checkbox opcional en el wizard
Name: "desktopicon"; Description: "Crear acceso directo en el &escritorio"; GroupDescription: "Íconos adicionales:"; Flags: unchecked

[Files]
; Ejecutable principal
Source: "{#MyAppSourceDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Carpeta _internal con todo el runtime
Source: "{#MyAppSourceDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Acceso directo en menú inicio
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\icono.ico"

; Acceso directo en escritorio (solo si el usuario lo marcó)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\icono.ico"; Tasks: desktopicon

[Run]
; Opción de lanzar la app al terminar la instalación
Filename: "{app}\{#MyAppExeName}"; Description: "Iniciar {#MyAppName}"; Flags: nowait postinstall skipifsilent
