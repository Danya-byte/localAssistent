[Setup]
AppId={{D9D625E1-F4C0-4186-8568-AE57346B13EC}
AppName=Local Assistant
AppVersion=0.1.0
AppPublisher=Open Source Contributors
AppPublisherURL=https://t.me/rollpit
AppSupportURL=https://t.me/rollpit
AppUpdatesURL=https://t.me/rollpit
DefaultDirName={autopf}\Local Assistant
DefaultGroupName=Local Assistant
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
OutputDir=..\dist
OutputBaseFilename=LocalAssistantSetup
SetupIconFile=..\assets\branding\installer.ico
UninstallDisplayIcon={app}\LocalAssistant.exe
WizardStyle=modern
WizardImageFile=..\assets\branding\wizard-side.png
WizardSmallImageFile=..\assets\branding\wizard-small.png
WizardBackImageFile=..\assets\branding\wizard-back.png
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
UsePreviousAppDir=no
UsePreviousTasks=no
ShowLanguageDialog=auto

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopShortcutTask}"
Name: "startmenuicon"; Description: "{cm:StartMenuShortcutTask}"

[Files]
Source: "..\dist\LocalAssistant\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autodesktop}\Local Assistant"; Filename: "{app}\LocalAssistant.exe"; IconFilename: "{app}\LocalAssistant.exe"; Tasks: desktopicon
Name: "{group}\Local Assistant"; Filename: "{app}\LocalAssistant.exe"; IconFilename: "{app}\LocalAssistant.exe"; Tasks: startmenuicon
Name: "{group}\Uninstall Local Assistant"; Filename: "{uninstallexe}"; Tasks: startmenuicon

[CustomMessages]
english.InstallPageTitle=Liquid glass setup
english.InstallPageSubtitle=Choose the install path, shortcuts, and first launch behavior.
english.InstallHero=Local Assistant
english.InstallTagline=Fast setup. Smooth launch. Stable install.
english.PathLabel=Install path
english.BrowseAction=Browse...
english.BrowsePrompt=Choose the folder for Local Assistant
english.OptionsLabel=Options
english.DesktopShortcutTask=Create desktop shortcut
english.StartMenuShortcutTask=Create Start Menu shortcut
english.LaunchAfterInstall=Launch Local Assistant after setup
english.SupportLabel=Developer
english.SupportLink=t.me/rollpit
english.InstallAction=Install
english.PathRequired=Choose an installation path before continuing.
english.FinishTitle=Local Assistant is installed
english.FinishBody=The application is ready to launch from the installed location.
english.LaunchFailed=The installer could not launch Local Assistant automatically.

russian.InstallPageTitle=Liquid glass установка
russian.InstallPageSubtitle=Выберите путь установки, ярлыки и автозапуск после установки.
russian.InstallHero=Local Assistant
russian.InstallTagline=Быстрая установка. Плавный запуск. Стабильная работа.
russian.PathLabel=Путь установки
russian.BrowseAction=Обзор...
russian.BrowsePrompt=Выберите папку для установки Local Assistant
russian.OptionsLabel=Параметры
russian.DesktopShortcutTask=Создать ярлык на рабочем столе
russian.StartMenuShortcutTask=Создать ярлык в меню Пуск
russian.LaunchAfterInstall=Запустить Local Assistant после установки
russian.SupportLabel=Разработчик
russian.SupportLink=t.me/rollpit
russian.InstallAction=Установить
russian.PathRequired=Перед продолжением выберите путь установки.
russian.FinishTitle=Local Assistant установлен
russian.FinishBody=Приложение готово к запуску из установленной директории.
russian.LaunchFailed=Инсталлер не смог автоматически запустить Local Assistant.

[Code]
var
  InstallPage: TWizardPage;
  HeroLabel: TNewStaticText;
  SubtitleLabel: TNewStaticText;
  PathLabel: TNewStaticText;
  OptionsLabel: TNewStaticText;
  SupportTitleLabel: TNewStaticText;
  SupportLinkLabel: TNewStaticText;
  PathEdit: TNewEdit;
  BrowseButton: TNewButton;
  DesktopShortcutCheck: TNewCheckBox;
  StartMenuShortcutCheck: TNewCheckBox;
  LaunchCheck: TNewCheckBox;
  LaunchAfterInstall: Boolean;

function BuildSelectedTasksValue(): String;
begin
  Result := '';
  if DesktopShortcutCheck.Checked then begin
    Result := 'desktopicon';
  end;

  if StartMenuShortcutCheck.Checked then begin
    if Result <> '' then begin
      Result := Result + ',';
    end;
    Result := Result + 'startmenuicon';
  end;
end;

procedure OpenDeveloperLink(Sender: TObject);
var
  ResultCode: Integer;
begin
  ShellExec('open', 'https://t.me/rollpit', '', '', SW_SHOWNORMAL, ewNoWait, ResultCode);
end;

procedure BrowseButtonClick(Sender: TObject);
var
  DirName: String;
begin
  DirName := PathEdit.Text;
  if BrowseForFolder(ExpandConstant('{cm:BrowsePrompt}'), DirName, False) then begin
    PathEdit.Text := DirName;
  end;
end;

procedure InitializeWizard;
begin
  InstallPage := CreateCustomPage(wpWelcome, ExpandConstant('{cm:InstallPageTitle}'), ExpandConstant('{cm:InstallPageSubtitle}'));

  HeroLabel := TNewStaticText.Create(WizardForm);
  HeroLabel.Parent := InstallPage.Surface;
  HeroLabel.Left := ScaleX(24);
  HeroLabel.Top := ScaleY(18);
  HeroLabel.Width := InstallPage.SurfaceWidth - ScaleX(48);
  HeroLabel.Caption := ExpandConstant('{cm:InstallHero}');
  HeroLabel.Font.Size := 20;
  HeroLabel.Font.Style := [fsBold];

  SubtitleLabel := TNewStaticText.Create(WizardForm);
  SubtitleLabel.Parent := InstallPage.Surface;
  SubtitleLabel.Left := ScaleX(24);
  SubtitleLabel.Top := ScaleY(54);
  SubtitleLabel.Width := InstallPage.SurfaceWidth - ScaleX(60);
  SubtitleLabel.Height := ScaleY(44);
  SubtitleLabel.AutoSize := False;
  SubtitleLabel.WordWrap := True;
  SubtitleLabel.Caption := ExpandConstant('{cm:InstallTagline}');

  PathLabel := TNewStaticText.Create(WizardForm);
  PathLabel.Parent := InstallPage.Surface;
  PathLabel.Left := ScaleX(24);
  PathLabel.Top := ScaleY(118);
  PathLabel.Caption := ExpandConstant('{cm:PathLabel}');
  PathLabel.Font.Style := [fsBold];

  PathEdit := TNewEdit.Create(WizardForm);
  PathEdit.Parent := InstallPage.Surface;
  PathEdit.Left := ScaleX(24);
  PathEdit.Top := ScaleY(142);
  PathEdit.Width := InstallPage.SurfaceWidth - ScaleX(138);
  PathEdit.Text := WizardDirValue;

  BrowseButton := TNewButton.Create(WizardForm);
  BrowseButton.Parent := InstallPage.Surface;
  BrowseButton.Left := InstallPage.SurfaceWidth - ScaleX(98);
  BrowseButton.Top := ScaleY(140);
  BrowseButton.Width := ScaleX(74);
  BrowseButton.Height := PathEdit.Height + ScaleY(2);
  BrowseButton.Caption := ExpandConstant('{cm:BrowseAction}');
  BrowseButton.OnClick := @BrowseButtonClick;

  OptionsLabel := TNewStaticText.Create(WizardForm);
  OptionsLabel.Parent := InstallPage.Surface;
  OptionsLabel.Left := ScaleX(24);
  OptionsLabel.Top := ScaleY(194);
  OptionsLabel.Caption := ExpandConstant('{cm:OptionsLabel}');
  OptionsLabel.Font.Style := [fsBold];

  DesktopShortcutCheck := TNewCheckBox.Create(WizardForm);
  DesktopShortcutCheck.Parent := InstallPage.Surface;
  DesktopShortcutCheck.Left := ScaleX(24);
  DesktopShortcutCheck.Top := ScaleY(220);
  DesktopShortcutCheck.Width := InstallPage.SurfaceWidth - ScaleX(48);
  DesktopShortcutCheck.Caption := ExpandConstant('{cm:DesktopShortcutTask}');
  DesktopShortcutCheck.Checked := True;

  StartMenuShortcutCheck := TNewCheckBox.Create(WizardForm);
  StartMenuShortcutCheck.Parent := InstallPage.Surface;
  StartMenuShortcutCheck.Left := ScaleX(24);
  StartMenuShortcutCheck.Top := ScaleY(246);
  StartMenuShortcutCheck.Width := InstallPage.SurfaceWidth - ScaleX(48);
  StartMenuShortcutCheck.Caption := ExpandConstant('{cm:StartMenuShortcutTask}');
  StartMenuShortcutCheck.Checked := True;

  LaunchCheck := TNewCheckBox.Create(WizardForm);
  LaunchCheck.Parent := InstallPage.Surface;
  LaunchCheck.Left := ScaleX(24);
  LaunchCheck.Top := ScaleY(272);
  LaunchCheck.Width := InstallPage.SurfaceWidth - ScaleX(48);
  LaunchCheck.Caption := ExpandConstant('{cm:LaunchAfterInstall}');
  LaunchCheck.Checked := True;

  SupportTitleLabel := TNewStaticText.Create(WizardForm);
  SupportTitleLabel.Parent := InstallPage.Surface;
  SupportTitleLabel.Left := ScaleX(24);
  SupportTitleLabel.Top := ScaleY(326);
  SupportTitleLabel.Caption := ExpandConstant('{cm:SupportLabel}');
  SupportTitleLabel.Font.Style := [fsBold];

  SupportLinkLabel := TNewStaticText.Create(WizardForm);
  SupportLinkLabel.Parent := InstallPage.Surface;
  SupportLinkLabel.Left := ScaleX(24);
  SupportLinkLabel.Top := ScaleY(350);
  SupportLinkLabel.Caption := ExpandConstant('{cm:SupportLink}');
  SupportLinkLabel.Cursor := crHand;
  SupportLinkLabel.Font.Style := [fsUnderline];
  SupportLinkLabel.Font.Color := clBlue;
  SupportLinkLabel.OnClick := @OpenDeveloperLink;

  WizardForm.NextButton.Width := ScaleX(108);
  LaunchCheck.Checked := not WizardSilent;
  LaunchAfterInstall := not WizardSilent;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = InstallPage.ID then begin
    WizardForm.NextButton.Caption := ExpandConstant('{cm:InstallAction}');
  end;

  if CurPageID = wpFinished then begin
    WizardForm.FinishedHeadingLabel.Caption := ExpandConstant('{cm:FinishTitle}');
    WizardForm.FinishedLabel.Caption := ExpandConstant('{cm:FinishBody}');
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;

  if CurPageID = InstallPage.ID then begin
    if Trim(PathEdit.Text) = '' then begin
      MsgBox(ExpandConstant('{cm:PathRequired}'), mbError, MB_OK);
      Result := False;
      exit;
    end;

    WizardForm.DirEdit.Text := RemoveBackslashUnlessRoot(Trim(PathEdit.Text));
    WizardSelectTasks(BuildSelectedTasksValue());
    LaunchAfterInstall := LaunchCheck.Checked;
  end;

  if CurPageID = wpFinished then begin
    if (not WizardSilent) and LaunchAfterInstall then begin
      if not ShellExec('open', ExpandConstant('{app}\LocalAssistant.exe'), '', '', SW_SHOWNORMAL, ewNoWait, ResultCode) then begin
        MsgBox(ExpandConstant('{cm:LaunchFailed}'), mbError, MB_OK);
      end;
    end;
  end;
end;
