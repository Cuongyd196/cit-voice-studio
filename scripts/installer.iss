; Script dong goi CIT Voice Studio thanh MOT file Setup.exe duy nhat.
;
; Nguon dau vao la thu muc dist\CIT-Voice-Studio\ do build_desktop_exe.bat tao ra.
; Khong build lai gi ca - chi dong goi.
;
; Build:  make_installer.bat        (hoac ISCC.exe installer.iss)
; Ket qua: dist\CIT-Voice-Studio-v<AppVersion>-win-x86_64.exe

#define AppName        "CIT Voice Studio"
; Phien ban SAN PHAM CIT Voice Studio - day la so khach nhin thay trong
; Add/Remove Programs va phai khop voi so tren GitHub Release.
; KHAC voi `version` trong pyproject.toml: cai do la phien ban goi Python
; `vieneu`, bam theo engine VieNeu-TTS cua tac gia goc (dang 3.3.0).
#define AppVersion     "1.0.6"
#define AppPublisher   "Cuong IT"
#define AppURL         "https://me.cuongit.net"
#define AppExeName     "CIT-Voice-Studio.exe"
#define AppDir         "dist\CIT-Voice-Studio"

[Setup]
; File nay nam trong scripts\: moi duong dan tuong doi ben duoi tinh tu goc repo.
SourceDir=..
AppId={{8F2A5C41-9D3E-4B7A-A1C6-3E8D5F0B2764}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}

; Cai vao thu muc nguoi dung => KHONG hien canh bao UAC, khong can quyen admin.
; Quan trong hon ve ky thuat: thu muc ghi duoc nen cache mo hinh nam ngay canh app
; (runtime_paths.setup_hf_home), go app la sach, khong de lai rac trong profile.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=no

; App ~763 MB. LZMA2/max ep xuong con khoang 400 MB.
; SolidCompression gom tat ca thanh mot khoi -> nen tot hon nhieu voi hang nghin
; file nho cua Python, doi lai luc build cham hon.
Compression=lzma2/max
SolidCompression=yes

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

OutputDir=dist
OutputBaseFilename=CIT-Voice-Studio-v{#AppVersion}-win-x86_64
; Trang dieu khoan: phai chon "I accept" moi Next duoc (make_installer.bat sinh file).
LicenseFile=build\DIEU-KHOAN.txt
SetupIconFile=assets\icons\icon.ico
; Cai de len ban cu cung duong dan: Explorer van hien icon cu da luu dem (shortcut,
; taskbar). ChangesAssociations bat Inno goi SHChangeNotify(SHCNE_ASSOCCHANGED) cuoi
; buoi cai -> Windows lam moi icon ngay. App khong dang ky loai file nao ca.
ChangesAssociations=yes
WizardStyle=modern
ShowLanguageDialog=no
; App dang chay thi .exe bi khoa. Inno dung Restart Manager de phat hien va nhac
; nguoi dung dong app, thay vi ghi de that bai giua chung.
CloseApplications=yes
RestartApplications=no

[Languages]
; Inno Setup 6 khong kem san tieng Viet. Lay Default.isl (tieng Anh) lam nen roi
; ghi de TOAN BO cau chu nguoi dung nhin thay o muc [Messages] ben duoi.
; File .iss nay phai luu dang UTF-8 CO BOM thi dau tieng Viet moi hien dung.
Name: "vi"; MessagesFile: "compiler:Default.isl"

[Messages]
; --- Tieu de cua so ---
SetupAppTitle=Cài đặt
SetupWindowTitle=Cài đặt - %1
UninstallAppTitle=Gỡ cài đặt
UninstallAppFullTitle=Gỡ cài đặt %1

; --- Nut bam ---
ButtonBack=< &Quay lại
ButtonNext=&Tiếp tục >
ButtonInstall=&Cài đặt
ButtonCancel=Huỷ bỏ
ButtonYes=&Có
ButtonNo=&Không
ButtonFinish=&Hoàn tất
ButtonBrowse=&Chọn thư mục...
ButtonWizardBrowse=&Chọn thư mục...
ClickNext=Bấm Tiếp tục để đi tiếp, hoặc Huỷ bỏ để thoát.
ClickFinish=Bấm Hoàn tất để đóng cửa sổ cài đặt.

; --- Trang chao ---
WelcomeLabel1=Chào mừng bạn đến với [name]
WelcomeLabel2=Trình cài đặt sẽ đưa [name/ver] vào máy của bạn.%n%nNên đóng các chương trình khác trước khi tiếp tục.

; --- Dieu khoan su dung ---
WizardLicense=Điều khoản sử dụng
LicenseLabel=Vui lòng đọc kỹ trước khi cài đặt.
LicenseLabel3=Hãy đọc điều khoản dưới đây. Bạn cần đồng ý mới cài đặt được.
LicenseAccepted=Tôi đã đọc và &đồng ý điều khoản
LicenseNotAccepted=Tôi &không đồng ý

; --- Chon thu muc ---
WizardSelectDir=Chọn nơi cài đặt
SelectDirDesc=Bạn muốn cài [name] vào đâu?
SelectDirLabel3=Trình cài đặt sẽ đặt [name] vào thư mục dưới đây.
SelectDirBrowseLabel=Bấm Tiếp tục để dùng thư mục này. Muốn đổi thì bấm Chọn thư mục.
DiskSpaceGBLabel=Cần ít nhất [gb] GB trống.
DiskSpaceMBLabel=Cần ít nhất [mb] MB trống.
InvalidPath=Đường dẫn không hợp lệ. Hãy nhập đường dẫn đầy đủ, ví dụ: C:\Thu muc
DirExists=Thư mục này đã có sẵn:%n%n%1%n%nVẫn cài vào đó chứ?
DirDoesntExist=Thư mục %1 chưa có. Tạo mới luôn chứ?
CannotInstallToNetworkDrive=Không cài được vào ổ đĩa mạng.
CannotInstallToUNCPath=Không cài được vào đường dẫn UNC.

; --- Chon viec them ---
WizardSelectTasks=Tuỳ chọn thêm
SelectTasksDesc=Bạn muốn làm thêm việc gì?
SelectTasksLabel2=Chọn những việc bạn muốn trình cài đặt làm, rồi bấm Tiếp tục.

; --- San sang cai ---
WizardReady=Sẵn sàng cài đặt
ReadyLabel1=Mọi thứ đã sẵn sàng để cài [name] vào máy bạn.
ReadyLabel2a=Bấm Cài đặt để bắt đầu. Muốn xem lại hoặc sửa gì thì bấm Quay lại.
ReadyLabel2b=Bấm Cài đặt để bắt đầu.
ReadyMemoDir=Nơi cài đặt:
ReadyMemoTasks=Việc làm thêm:

; --- Dang cai ---
WizardPreparing=Đang chuẩn bị
PreparingDesc=Đang chuẩn bị cài [name] vào máy bạn.
WizardInstalling=Đang cài đặt
InstallingLabel=Đang cài [name], xin đợi một lát.
StatusExtractFiles=Đang giải nén tệp...
StatusCreateIcons=Đang tạo lối tắt...
StatusUninstalling=Đang gỡ %1...
StatusRollback=Đang hoàn tác các thay đổi...

; --- Xong ---
FinishedHeadingLabel=Đã cài xong [name]
FinishedLabel=[name] đã được cài vào máy bạn. Mở ứng dụng bằng lối tắt vừa tạo.
FinishedLabelNoIcons=[name] đã được cài vào máy bạn.
FinishedRestartLabel=Cần khởi động lại máy để hoàn tất. Khởi động lại ngay chứ?

; --- Loi / huy ---
ExitSetupTitle=Thoát cài đặt
ExitSetupMessage=Chưa cài xong. Thoát bây giờ thì ứng dụng sẽ không được cài.%n%nVẫn thoát chứ?
AbortRetryIgnoreSelectAction=Chọn cách xử lý
AbortRetryIgnoreRetry=&Thử lại
AbortRetryIgnoreIgnore=&Bỏ qua lỗi này và đi tiếp
AbortRetryIgnoreCancel=Huỷ cài đặt
ErrorTitle=Lỗi
SetupAborted=Cài đặt chưa hoàn tất.%n%nHãy xử lý lỗi rồi chạy lại.
FileAbortRetryIgnoreSkipNotRecommended=&Bỏ qua tệp này (không khuyến khích)
ExistingFileReadOnly2=Không ghi đè được tệp này vì nó ở chế độ chỉ đọc.
ExistingFileReadOnlyRetry=&Bỏ thuộc tính chỉ đọc rồi thử lại
ExistingFileReadOnlyKeepExisting=&Giữ nguyên tệp cũ

; --- Go cai dat ---
ConfirmUninstall=Bạn có chắc muốn gỡ %1 và mọi thành phần của nó không?
UninstallStatusLabel=Đang gỡ %1, xin đợi một lát.
UninstalledAll=Đã gỡ %1 khỏi máy.
UninstalledMost=Đã gỡ %1.%n%nMột vài tệp không xoá được, bạn có thể xoá tay sau.
UninstallNotFound=Không tìm thấy tệp "%1". Không gỡ được.
UninstallOpenError=Không mở được tệp "%1". Không gỡ được.

[CustomMessages]
vi.CreateDesktopIcon=Tạo biểu tượng ngoài màn hình Desktop
vi.LaunchApp=Mở {#AppName} ngay bây giờ
vi.AdditionalIcons=Lối tắt:
vi.UninstallProgram=Gỡ %1

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Toan bo thu muc dist\CIT-Voice-Studio, giu nguyen cay thu muc con.
; Da bao gom san mo hinh giong noi (models\) va cac DLL VC++ runtime, nen may
; khach khong can Internet va khong dinh loi onnxruntime_pybind11_state.
; Excludes: file app sinh ra khi chay thu exe trong dist truoc khi dong goi (log,
; chan doan, bo GPU tu cai, giong nhan ban) - khong duoc lot vao bo cai.
Source: "{#AppDir}\*"; DestDir: "{app}"; Excludes: "\cit-voice-studio.log,\chan-doan.txt,\gpu-selftest.txt,\kokoro-selftest.txt,\gpu_venv,\addons,custom_voices_*.json"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Chan doan loi"; Filename: "{app}\chan-doan.bat"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[InstallDelete]
; Cap nhat de len ban cu: xoa _internal cu truoc khi chep. Inno chi ghi de, khong xoa
; file thua, nen thu vien ban cu bo di van nam lai va bi nap nham (vd. thu muc
; websockets cua ban co gradio lam server khong khoi dong duoc). _internal chi chua ma
; dong goi; mo hinh, gpu_venv, addons nam ngoai nen khong mat.
Type: filesandordirs; Name: "{app}\_internal"

[UninstallDelete]
; File do app sinh ra luc chay, Inno khong biet nen phai xoa tay.
Type: files;      Name: "{app}\cit-voice-studio.log"
Type: files;      Name: "{app}\chan-doan.txt"
Type: filesandordirs; Name: "{app}\models\hf_cache"
; Bo ho tro GPU tu cai (Python goc + torch, vai GB) va file tu kiem tra GPU.
Type: filesandordirs; Name: "{app}\gpu_venv"
Type: filesandordirs; Name: "{app}\addons"
Type: files;      Name: "{app}\gpu-selftest.txt"
Type: files;      Name: "{app}\kokoro-selftest.txt"
Type: dirifempty; Name: "{app}\models"
Type: dirifempty; Name: "{app}"
