#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif

[Setup]
AppId={{D9D625E1-F4C0-4186-8568-AE57346B13EC}
AppName=Local Assistant
AppVersion={#AppVersion}
AppPublisher=Open Source Contributors
DefaultDirName={autopf}\Local Assistant
DefaultGroupName=Local Assistant
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=LocalAssistantSetup
SetupIconFile=..\assets\branding\installer.ico
UninstallDisplayIcon={app}\LocalAssistant.exe
WizardStyle=modern
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
UsePreviousAppDir=no
UsePreviousTasks=no
ShowLanguageDialog=auto
CloseApplications=yes
RestartApplications=yes
CloseApplicationsFilter=LocalAssistant.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopShortcutTask}"
Name: "startmenuicon"; Description: "{cm:StartMenuShortcutTask}"; Flags: checkedonce
Name: "recommendedmodel"; Description: "{cm:RecommendedModelTask}"; Flags: checkedonce

[Files]
Source: "..\dist\LocalAssistant\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autodesktop}\Local Assistant"; Filename: "{app}\LocalAssistant.exe"; IconFilename: "{app}\LocalAssistant.exe"; Tasks: desktopicon
Name: "{group}\Local Assistant"; Filename: "{app}\LocalAssistant.exe"; IconFilename: "{app}\LocalAssistant.exe"; Tasks: startmenuicon
Name: "{group}\Uninstall Local Assistant"; Filename: "{uninstallexe}"; Tasks: startmenuicon

[Run]
Filename: "{app}\LocalAssistant.exe"; Parameters: "--bootstrap-install-recommended-model"; Description: "{cm:RecommendedModelTask}"; Tasks: recommendedmodel
Filename: "{app}\LocalAssistant.exe"; Description: "{cm:LaunchAfterInstall}"; Flags: nowait postinstall skipifsilent

[CustomMessages]
english.DesktopShortcutTask=Create desktop shortcut
english.StartMenuShortcutTask=Create Start Menu shortcut
english.RecommendedModelTask=Install recommended model (~940 MB, requires internet)
english.LaunchAfterInstall=Launch Local Assistant
english.WelcomeTitle=Install Local Assistant
english.WelcomeBody=Choose the install path, review shortcuts, and finish setup in a few clicks.
english.FinishTitle=Local Assistant is installed
english.FinishBody=The app is ready to launch. Support links are available inside Settings.

russian.DesktopShortcutTask=Создать ярлык на рабочем столе
russian.StartMenuShortcutTask=Создать ярлык в меню Пуск
russian.LaunchAfterInstall=Запустить Local Assistant
russian.WelcomeTitle=Установка Local Assistant
russian.WelcomeBody=Выберите путь установки, проверьте ярлыки и завершите установку за несколько кликов.
russian.FinishTitle=Local Assistant установлен
russian.FinishBody=Приложение готово к запуску. Ссылки на поддержку доступны внутри настроек.

russian.RecommendedModelTask=Установить рекомендованную модель (~940 MB, нужен интернет)

[Code]
procedure InitializeWizard;
begin
  WizardForm.WelcomeLabel1.Caption := ExpandConstant('{cm:WelcomeTitle}');
  WizardForm.WelcomeLabel2.Caption := ExpandConstant('{cm:WelcomeBody}');
  WizardForm.FinishedHeadingLabel.Caption := ExpandConstant('{cm:FinishTitle}');
  WizardForm.FinishedLabel.Caption := ExpandConstant('{cm:FinishBody}');
end;
