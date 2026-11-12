"""
CIT Voice Studio - Desktop App Launcher (PyWebView + FastAPI + VieNeu-TTS)
========================================================================
Tự động khởi chạy Backend AI ngầm và mở cửa sổ ứng dụng Desktop Native.
Không cần cài đặt Node.js hay Rust khi chạy hoặc đóng gói.
"""
import io
import json
import os
import socket
import sys
import time
import threading
from pathlib import Path
import urllib.request
import uvicorn

# PyWebView trên Windows chạy qua pythonnet + .NET Framework. Nếu máy người dùng thiếu
# .NET Framework 4.7.2+ (hoặc bản đóng gói thiếu file runtime), import này sẽ hỏng.
# Khi đó ứng dụng không được chết - nó rớt về trình duyệt mặc định (xem _run_in_browser).
try:
    import webview
    _WEBVIEW_IMPORT_ERROR = None
except Exception as _webview_exc:
    webview = None
    _WEBVIEW_IMPORT_ERROR = _webview_exc

# Fix Windows / PyInstaller Windowed Unicode Encoding issues
if sys.platform == "win32":
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if sys.stderr is None:
        sys.stderr = io.StringIO()
    else:
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _log_path() -> "Path":
    """Nơi ghi log. Cạnh file .exe nếu ghi được, không thì %LOCALAPPDATA%."""
    try:
        if sys.platform == "darwin" and getattr(sys, "frozen", False):
            # Không ghi log vào trong gói .app (xem apps/runtime_paths_macos.py).
            from apps.runtime_paths_macos import data_dir
            return data_dir() / "cit-voice-studio.log"
        base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
            else Path(__file__).resolve().parents[1]
        probe = base / ".write_test"
        probe.write_bytes(b"")
        probe.unlink()
        return base / "cit-voice-studio.log"
    except Exception:
        d = Path(os.getenv("LOCALAPPDATA") or Path.home()) / "CitVoiceStudio"
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return d / "cit-voice-studio.log"


LOG_FILE = _log_path()
try:  # mỗi lần chạy bắt đầu một file mới, khỏi phình vô hạn
    LOG_FILE.write_text("", encoding="utf-8")
except Exception:
    pass


def log(msg: str):
    """Log an toàn không gây crash charmap UnicodeEncodeError.

    GHI RA FILE nữa: bản đóng gói chạy `--windowed` nên không có console, mọi thứ in
    ra đều biến mất. Không có file log thì lỗi trên máy người dùng là không thể chẩn
    đoán - đúng tình cảnh gặp phải với sự cố màn hình trắng.
    """
    try:
        print(msg)
    except Exception:
        try:
            print(msg.encode("ascii", errors="replace").decode("ascii"))
        except Exception:
            pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(f"{time.strftime('%H:%M:%S')}  {msg}\n")
    except Exception:
        pass


# Thêm thư mục gốc và src vào sys.path (hỗ trợ cả frozen exe)
if getattr(sys, "frozen", False):
    ROOT_DIR = Path(sys._MEIPASS)
else:
    ROOT_DIR = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

# Cache Hugging Face dùng chung cho cả 3 entry point. Phải chạy TRƯỚC khi import
# web_stream (nó kéo theo huggingface_hub, thư viện đọc HF_HOME ngay lúc import).
from apps.runtime_paths import setup_hf_home
setup_hf_home()

from apps.server_settings import setup_port
from apps import remote_access

PORT = setup_port()
BACKEND_URL = f"http://127.0.0.1:{PORT}"

# Lỗi làm chết thread backend (model nạp hỏng, cổng bị chiếm...). main() đọc biến này
# để báo rõ cho người dùng, thay vì mở một cửa sổ trắng trỏ vào server không tồn tại.
_BACKEND_ERROR = None


WEBVIEW2_DOWNLOAD_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"


def webview2_available() -> bool:
    """Máy đã có Microsoft Edge WebView2 Runtime chưa.

    Vì sao phải tự kiểm: pywebview ÂM THẦM tụt xuống MSHTML (engine IE11) khi không
    thấy WebView2 - kể cả khi đã ép `gui="edgechromium"` (xem `is_chromium` trong
    webview/platforms/winforms.py). Nó chỉ ghi một dòng warning, mà bản đóng gói
    `--windowed` thì không có console để đọc. IE11 không chạy nổi bundle React (Vite
    build ra ES2020), nên người dùng nhận một CỬA SỔ TRẮNG không kèm lý do gì.

    Windows 11 có sẵn WebView2. Windows 10 thì không chắc - bản LTSC hoặc máy chưa
    từng cài Edge mới là thiếu.

    Logic dò bám theo đúng pywebview để không lệch kết quả, nhưng đọc registry trực
    tiếp nên chạy được cả khi pythonnet hỏng.
    """
    if sys.platform != "win32":
        return True
    try:
        import winreg
    except Exception:
        return False

    def pv(hive, sub: str) -> str:
        try:
            with winreg.OpenKey(hive, sub) as k:
                return str(winreg.QueryValueEx(k, "pv")[0])
        except Exception:
            return "0"

    def as_tuple(s: str):
        try:
            return tuple(int(x) for x in s.split("."))
        except Exception:
            return (0,)

    keys = (
        "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",  # Runtime chính thức
        "{2CD8A007-E189-409D-A2C8-9AF4EF3C72AA}",  # Beta
        "{0D50BFEC-CD6A-4F9A-964C-C7416E3ACB10}",  # Dev
        "{65C35B14-6C1D-4122-AC46-7148CC9D6497}",  # Canary
    )
    for key in keys:
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for prefix in (r"SOFTWARE\Microsoft", r"SOFTWARE\WOW6432Node\Microsoft"):
                if as_tuple(pv(hive, rf"{prefix}\EdgeUpdate\Clients\{key}")) >= (86, 0, 622, 0):
                    return True
    return False


# Kich thuoc cua so mong muon. Chi la MONG MUON - luon bi kep lai cho vua man hinh.
WINDOW_PREFERRED = (1120, 720)
WINDOW_MIN = (800, 500)
# Chua mep cho cua so khong dinh sat vien vung lam viec.
WINDOW_MARGIN = 16


def fit_window_to_screen(work, preferred=WINDOW_PREFERRED, minimum=WINDOW_MIN):
    """Tính kích thước và vị trí cửa sổ sao cho vừa MỌI màn hình.

    `work` là vùng làm việc theo pixel LOGIC (đã trừ taskbar): (x, y, rộng, cao).
    Trả về dict truyền thẳng cho `webview.create_window`.

    Vì sao phải tự tính: không truyền x/y thì pywebview rơi vào
    `FormStartPosition.CenterScreen` của WinForms, và cái đó căn theo TOÀN BỘ chiều
    cao màn hình chứ không trừ taskbar - cửa sổ luôn bị đẩy xuống thấp hơn tâm thật
    của vùng dùng được.

    Tệ hơn là chuyện kích thước. Đo trên máy 2560x1440 ở scale 175%: vùng làm việc
    chỉ còn 775 px LOGIC cao, trong khi cửa sổ đặt cứng 800 - cao hơn cả chỗ trống,
    nên phần dưới chui xuống dưới taskbar. Màn hình càng nhỏ hoặc scale càng cao thì
    càng nặng.

    Nên mọi số ở đây đều bị kẹp theo `work`, kể cả min_size: một `min_size` lớn hơn
    màn hình sẽ bị WinForms ép giữ, làm cửa sổ tràn ra ngoài y như cũ.
    """
    wx, wy, ww, wh = (int(v) for v in work)
    ww, wh = max(ww, 1), max(wh, 1)

    # min_size khong bao gio duoc vuot vung lam viec.
    min_w = min(int(minimum[0]), ww)
    min_h = min(int(minimum[1]), wh)

    # Kich thuoc: lay theo mong muon, nhung khong qua vung lam viec tru mep.
    w = min(int(preferred[0]), max(min_w, ww - WINDOW_MARGIN))
    h = min(int(preferred[1]), max(min_h, wh - WINDOW_MARGIN))
    w = max(min_w, min(w, ww))
    h = max(min_h, min(h, wh))

    # Can giua theo VUNG LAM VIEC, khong phai theo man hinh.
    x = wx + (ww - w) // 2
    y = wy + (wh - h) // 2
    return {"width": w, "height": h, "x": x, "y": y, "min_size": (min_w, min_h)}


def _primary_work_area_logical():
    """Vùng làm việc màn hình chính, quy về pixel LOGIC. None nếu không đọc được.

    pywebview nhận toạ độ theo pixel logic rồi tự nhân với DPI của cửa sổ, nên ở đây
    phải trả về logic chứ không phải pixel vật lý.

    Chỗ dễ sai: `GetSystemMetrics` / `SPI_GETWORKAREA` trả về gì còn tuỳ tiến trình
    đã khai báo DPI-aware hay chưa. Chưa khai báo thì Windows đã tự quy đổi sẵn (tức
    đang LOGIC rồi), khai báo rồi thì là pixel VẬT LÝ. Chia sai thêm một lần nữa là
    cửa sổ bé tí trên màn 4K. Nên phải so với độ phân giải thật lấy từ
    EnumDisplaySettings để biết đang ở trạng thái nào.
    """
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        rect = RECT()
        if not user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
            return None
        reported_h = user32.GetSystemMetrics(1)
        if reported_h <= 0:
            return None

        class DEVMODE(ctypes.Structure):
            _fields_ = [("dmDeviceName", wintypes.WCHAR * 32),
                        ("dmSpecVersion", wintypes.WORD), ("dmDriverVersion", wintypes.WORD),
                        ("dmSize", wintypes.WORD), ("dmDriverExtra", wintypes.WORD),
                        ("dmFields", wintypes.DWORD), ("dmPositionX", ctypes.c_long),
                        ("dmPositionY", ctypes.c_long), ("dmDisplayOrientation", wintypes.DWORD),
                        ("dmDisplayFixedOutput", wintypes.DWORD), ("dmColor", ctypes.c_short),
                        ("dmDuplex", ctypes.c_short), ("dmYResolution", ctypes.c_short),
                        ("dmTTOption", ctypes.c_short), ("dmCollate", ctypes.c_short),
                        ("dmFormName", wintypes.WCHAR * 32), ("dmLogPixels", wintypes.WORD),
                        ("dmBitsPerPel", wintypes.DWORD), ("dmPelsWidth", wintypes.DWORD),
                        ("dmPelsHeight", wintypes.DWORD), ("dmDisplayFlags", wintypes.DWORD),
                        ("dmDisplayFrequency", wintypes.DWORD), ("dmICMMethod", wintypes.DWORD),
                        ("dmICMIntent", wintypes.DWORD), ("dmMediaType", wintypes.DWORD),
                        ("dmDitherType", wintypes.DWORD), ("dmReserved1", wintypes.DWORD),
                        ("dmReserved2", wintypes.DWORD), ("dmPanningWidth", wintypes.DWORD),
                        ("dmPanningHeight", wintypes.DWORD)]

        dm = DEVMODE()
        dm.dmSize = ctypes.sizeof(DEVMODE)
        scale = 1.0
        if user32.EnumDisplaySettingsW(None, -1, ctypes.byref(dm)) and dm.dmPelsHeight:
            # Bao cao trung do phan giai that => dang DPI-aware => so lieu la VAT LY.
            if abs(int(dm.dmPelsHeight) - int(reported_h)) <= 1:
                try:
                    dpi = user32.GetDpiForSystem()
                except Exception:
                    dpi = 96
                if dpi and dpi > 0:
                    scale = dpi / 96.0
        if scale <= 0:
            scale = 1.0

        return (int(rect.left / scale), int(rect.top / scale),
                int((rect.right - rect.left) / scale), int((rect.bottom - rect.top) / scale))
    except Exception as e:
        log(f"[Chẩn đoán] Không đọc được vùng làm việc màn hình: {e}")
        return None


def splash_close() -> None:
    """Tắt màn hình chờ của PyInstaller (`--splash`), nếu đang hiện.

    Màn hình chờ này do bootloader vẽ TRƯỚC khi Python khởi động, nên nó là thứ duy
    nhất che được khoảng vài giây đầu lúc giải nén bundle. Chữ trên đó là chữ tĩnh
    trong `assets/splash.png`: dạng `--splash` dòng lệnh không bật vùng chữ động.

    Phải gọi ở MỌI nhánh thoát, nếu không màn hình chờ sẽ nằm đè lên cửa sổ thật
    hoặc che mất hộp thoại báo lỗi.

    Chỉ import khi bootloader thật sự bật màn hình chờ: bản Linux/macOS không có
    `--splash` nhưng `pyi_splash` vẫn bị gom vào bundle, và import nó ở đó in ra
    traceback `KeyError: '_PYI_SPLASH_IPC'` vào log.
    """
    if "_PYI_SPLASH_IPC" not in os.environ:
        return
    try:
        import pyi_splash  # chỉ tồn tại trong bản đóng gói có --splash
        pyi_splash.close()
    except Exception:
        pass


def _show_error(title: str, message: str) -> None:
    """Báo lỗi để người dùng thật sự nhìn thấy.

    Bản đóng gói chạy PyInstaller `--windowed` nên không có console - mọi thứ in ra
    đều rơi vào hư không. Phải dùng hộp thoại gốc của Windows.
    """
    log(f"[Desktop App] {title}: {message}")
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
        except Exception:
            pass


def _probe_health(url: str, timeout: float = 1.0):
    """Gọi /health. Trả dict nếu đúng backend của app này, None nếu không.

    Kiểm tra cả hình dạng JSON: cổng 8001 có thể đang bị một ứng dụng khác chiếm và
    vẫn trả HTTP 200 - khi đó không được coi là backend của mình.
    """
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"{url}/health", timeout=timeout) as res:
            if res.status != 200:
                return None
            data = json.loads(res.read().decode("utf-8", errors="replace"))
    except Exception:
        return None
    if isinstance(data, dict) and "engine" in data and "sample_rate" in data:
        return data
    return None


def _reserve_backend_socket(preferred: int, host: str = "127.0.0.1"):
    """Reserve a private listener so concurrent launches cannot claim the same port."""
    for port in range(preferred, min(preferred + 21, 65536)):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if sys.platform == "win32":
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                # Linux/macOS: không có cờ này thì cổng vừa tắt app còn kẹt TIME_WAIT
                # ~60 giây, mở lại (kể cả nút Khởi động lại) bị đẩy sang 8002. Trên
                # POSIX cờ này KHÔNG cho hai tiến trình cùng nghe một cổng.
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((host, port))
            listener.listen(128)
            return listener
        except OSError:
            listener.close()
    raise RuntimeError(f"Không còn cổng trống gần cổng {preferred}.")


def _reserve_listener(preferred: int):
    """0.0.0.0 khi bật "Cho máy khác truy cập" (Cài đặt), không thì chỉ máy này.
    Mở 0.0.0.0 hỏng (chính sách mạng...) thì lùi về 127.0.0.1 để app vẫn chạy."""
    host = remote_access.listen_host()
    if host != "127.0.0.1":
        try:
            listener = _reserve_backend_socket(preferred, host)
            remote_access.mark_listening(host)
            log(f"[Desktop App] Cho máy khác truy cập: lắng nghe {host}:{listener.getsockname()[1]}")
            return listener
        except Exception as e:
            log(f"[Desktop App] Không mở được {host}, chỉ cho máy này truy cập: {e}")
    listener = _reserve_backend_socket(preferred)
    remote_access.mark_listening("127.0.0.1")
    return listener


def run_backend(listener):
    """Run this window's backend on its already-reserved socket."""
    global _BACKEND_ERROR
    try:
        from apps.web_stream import app
        log(f"[Desktop App] Đang khởi động Backend API tại {BACKEND_URL}...")
        # ws="none": app không dùng WebSocket; tránh uvicorn tự nạp thư viện websockets
        # (bản cài cũ để sót thư mục websockets dở dang, server chết lúc khởi động).
        config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning", ws="none")
        uvicorn.Server(config).run(sockets=[listener])
    except BaseException as e:
        _BACKEND_ERROR = e
        log(f"[Desktop App] Backend dừng do lỗi: {e}")
    finally:
        listener.close()


def wait_for_server(url: str, timeout: float = 30.0, thread=None) -> bool:
    """Đợi backend sẵn sàng trước khi mở cửa sổ Desktop.

    Thoát ngay khi thread backend đã chết, khỏi bắt người dùng ngồi chờ hết `timeout`
    trong trường hợp model nạp lỗi hoặc cổng bị chiếm.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if thread is not None and not thread.is_alive():
            return False
        if _probe_health(url) is not None:
            return thread is None or thread.is_alive()
        time.sleep(0.3)
    return False


import base64


class DesktopApi:
    """Cung cấp các API gốc của hệ điều hành Desktop cho Frontend qua PyWebView."""

    def __init__(self):
        self._window = None
        # File app đã lưu trong phiên này: open_saved chỉ mở những file này, để JS
        # không mở/chạy được đường dẫn tuỳ ý trên máy.
        self._saved_paths: list[str] = []

    def set_window(self, window):
        self._window = window

    def quit_app(self) -> None:
        """Nút "Thoát" ở màn hình điều khoản: người dùng không đồng ý thì đóng app."""
        if self._window is not None:
            self._window.destroy()

    def _ask_save_path(self, filename: str):
        """Hộp thoại Save As gốc của Windows. Trả đường dẫn, hoặc None nếu bấm Huỷ."""
        # Xác định bộ lọc định dạng file
        file_ext = Path(filename).suffix.lower()
        if file_ext == ".mp3":
            file_types = ("Audio MP3 (*.mp3)", "All files (*.*)")
        elif file_ext == ".wav":
            file_types = ("Audio WAV (*.wav)", "All files (*.*)")
        elif file_ext == ".txt":
            file_types = ("Text File (*.txt)", "All files (*.*)")
        elif file_ext == ".zip":
            file_types = ("ZIP (*.zip)", "All files (*.*)")
        else:
            file_types = ("All files (*.*)",)

        # Thư mục lưu người dùng đã chọn trong Cài đặt (mặc định Downloads).
        from apps import save_settings

        settings = save_settings.load()
        folder = save_settings.effective_folder(settings)
        # Tắt "Hỏi mỗi lần lưu": lưu thẳng vào thư mục, không ghi đè file đã có.
        if not settings["ask"]:
            return str(save_settings.unique_path(folder, filename))
        default_dir = str(folder)

        # Mở hộp thoại chọn thư mục & file Save As gốc của Windows
        result = self._window.create_file_dialog(
            dialog_type=webview.FileDialog.SAVE,
            directory=default_dir,
            save_filename=filename,
            file_types=file_types,
        )

        # Nếu người dùng bấm Hủy (Cancel) hoặc đóng hộp thoại
        if not result:
            return None
        return (result if isinstance(result, str) else result[0]) or None

    def save_file(self, filename: str, base64_data: str) -> dict:
        """
        Hiển thị hộp thoại Save As của Windows để người dùng chọn thư mục và đặt tên file,
        sau đó ghi trực tiếp dữ liệu nhị phân vào ổ đĩa.
        """
        try:
            if not self._window:
                return {"success": False, "error": "Cửa sổ chưa được khởi tạo"}
            save_path = self._ask_save_path(filename)
            if not save_path:
                return {"success": False, "cancelled": True}

            # Tách chuỗi Data URL nếu có (data:audio/wav;base64,...)
            if "," in base64_data:
                base64_data = base64_data.split(",", 1)[1]

            file_bytes = base64.b64decode(base64_data)
            with open(save_path, "wb") as f:
                f.write(file_bytes)

            log(f"[Desktop App] Đã lưu file thành công: {save_path}")
            return self._after_save(save_path)
        except Exception as e:
            log(f"[Desktop App] Lỗi khi lưu file: {e}")
            return {"success": False, "error": str(e)}

    def save_history_audio(self, entry_id: str, filename: str, fmt: str = "wav") -> dict:
        """Lưu audio của một mục lịch sử: Python chép (hoặc chuyển sang MP3) thẳng từ
        file trên đĩa. Bản ~2 giờ (~690 MB) đi qua base64 như ``save_file`` sẽ vượt
        giới hạn chuỗi của trình duyệt (~537 triệu ký tự)."""
        try:
            if not self._window:
                return {"success": False, "error": "Cửa sổ chưa được khởi tạo"}
            save_path = self._ask_save_path(filename)
            if not save_path:
                return {"success": False, "cancelled": True}
            from apps import history_store

            out = history_store.export_audio(entry_id, save_path, "mp3" if fmt == "mp3" else "wav")
            log(f"[Desktop App] Đã lưu file thành công: {out}")
            return self._after_save(str(out))
        except Exception as e:
            log(f"[Desktop App] Lỗi khi lưu file: {e}")
            return {"success": False, "error": str(getattr(e, "detail", e))}

    # ---- Sau khi lưu: nhớ đường dẫn, tự mở nếu người dùng bật ----

    def _after_save(self, path: str) -> dict:
        from apps import save_settings

        self._saved_paths = [p for p in self._saved_paths if p != path][-49:] + [path]
        opened = False
        if save_settings.load()["open_after"]:
            try:
                save_settings.open_path(Path(path))
                opened = True
            except Exception as e:
                log(f"[Desktop App] Không mở được file vừa lưu: {e}")
        return {"success": True, "path": path, "name": Path(path).name, "opened": opened}

    def open_saved(self, path: str, reveal: bool = False) -> dict:
        """Nút "Mở file" / "Mở thư mục" trên thông báo đã lưu."""
        from apps import save_settings

        if path not in self._saved_paths or not Path(path).exists():
            return {"success": False, "error": "Không tìm thấy file vừa lưu (có thể đã bị xoá hoặc đổi tên)."}
        try:
            save_settings.open_path(Path(path), reveal=bool(reveal))
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---- Cài đặt lưu file (Cài đặt -> Lưu file) ----

    def get_save_settings(self) -> dict:
        from apps import save_settings

        s = save_settings.load()
        return {**s, "effective_folder": str(save_settings.effective_folder(s)),
                "default_folder": str(save_settings.default_folder())}

    def set_save_settings(self, settings: dict) -> dict:
        from apps import save_settings

        try:
            save_settings.save(settings or {})
            return {"success": True, **self.get_save_settings()}
        except (ValueError, OSError) as e:
            return {"success": False, "error": str(e)}

    def choose_save_folder(self) -> dict:
        """Hộp thoại chọn thư mục gốc của hệ điều hành; chưa lưu, chỉ trả đường dẫn."""
        from apps import save_settings

        if not self._window:
            return {"success": False, "error": "Cửa sổ chưa được khởi tạo"}
        result = self._window.create_file_dialog(
            dialog_type=webview.FileDialog.FOLDER,
            directory=str(save_settings.effective_folder()),
        )
        if not result:
            return {"success": False, "cancelled": True}
        return {"success": True, "folder": result if isinstance(result, str) else result[0]}


def _run_in_browser(reason=None) -> None:
    """Phương án dự phòng: mở giao diện bằng trình duyệt mặc định.

    Dùng khi không dựng được cửa sổ Desktop (thiếu .NET Framework, WebView2, hoặc
    bản đóng gói thiếu file runtime của pythonnet). Backend vẫn phục vụ đầy đủ giao
    diện React tại `/`, nên ứng dụng vẫn chạy được - chỉ mất hộp thoại Save As gốc,
    và frontend tự chuyển sang `showSaveFilePicker` của trình duyệt.
    """
    import webbrowser

    if reason is not None:
        log(f"[Desktop App] Không mở được cửa sổ Desktop: {reason}")
    log(f"[Desktop App] Chuyển sang trình duyệt mặc định: {BACKEND_URL}")

    opened = False
    try:
        opened = bool(webbrowser.open(BACKEND_URL))
    except Exception as e:
        log(f"[Desktop App] Không mở được trình duyệt: {e}")

    if not opened:
        # Hết đường tự động - phải cho người dùng thấy địa chỉ, không được im lặng.
        _show_error(
            "CIT Voice Studio",
            "Không mở được cửa sổ ứng dụng lẫn trình duyệt.\n\n"
            f"Hãy tự mở địa chỉ này bằng trình duyệt:\n{BACKEND_URL}\n\n"
            "Giữ cửa sổ/ứng dụng này chạy trong lúc sử dụng.",
        )

    # Backend chạy trong daemon thread - main thread phải sống thì server mới còn.
    log("[Desktop App] Đóng cửa sổ dòng lệnh này để tắt ứng dụng.")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        log("[Desktop App] Đã dừng.")


_RESTART_WAIT_ENV = "CIT_RESTART_WAIT_PID"


def _restart_app() -> None:
    """Mở một bản app mới rồi thoát bản này (nút "Khởi động lại" trong Cài đặt).

    Bản mới đợi bản cũ thoát hẳn (xem _wait_for_previous_instance) rồi mới giữ cổng,
    nếu không nó thấy cổng cũ còn bận và nhảy sang cổng kế tiếp.
    """
    import subprocess

    log("[Desktop App] Khởi động lại theo yêu cầu từ Cài đặt...")
    # Biến môi trường của bootloader PyInstaller: để nguyên thì bản con tưởng mình là
    # tiến trình con của bản này và dùng lại thư mục giải nén của nó.
    env = {k: v for k, v in os.environ.items() if not k.startswith("_PYI_") and k != "_MEIPASS2"}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    env[_RESTART_WAIT_ENV] = str(os.getpid())
    env.pop(remote_access.LISTEN_ENV, None)
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, *sys.argv[1:]]
        cwd = str(Path(sys.executable).resolve().parent)
    else:
        cmd = [sys.executable, "-m", "apps.desktop_app", *sys.argv[1:]]
        cwd = str(ROOT_DIR)
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        subprocess.Popen(cmd, cwd=cwd, env=env, close_fds=True, creationflags=flags)
    except Exception as e:
        log(f"[Desktop App] Không mở được bản mới, giữ nguyên bản đang chạy: {e}")
        return
    # Thoát ngay cả luồng backend lẫn cửa sổ WebView2. Lịch sử/cài đặt đều đã ghi
    # xuống đĩa theo kiểu atomic nên không mất gì.
    os._exit(0)


def _wait_for_previous_instance(timeout: float = 20.0) -> None:
    pid_text = os.environ.pop(_RESTART_WAIT_ENV, "")
    if not pid_text.isdigit():
        return
    pid = int(pid_text)
    log(f"[Desktop App] Đợi bản trước (PID {pid}) thoát hẳn...")
    if sys.platform == "win32":
        import ctypes

        SYNCHRONIZE = 0x00100000
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if handle:
            kernel32.WaitForSingleObject(handle, int(timeout * 1000))
            kernel32.CloseHandle(handle)
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.2)


def main():
    global PORT, BACKEND_URL, _BACKEND_ERROR

    _wait_for_previous_instance()
    from apps import server_settings
    server_settings.restart_handler = _restart_app

    # A daemon backend belongs to its window; borrowing it breaks on owner exit.
    _BACKEND_ERROR = None
    try:
        listener = _reserve_listener(PORT)
    except Exception as e:
        splash_close()
        _show_error("CIT Voice Studio", f"Không khởi động được: {e}")
        return
    PORT = listener.getsockname()[1]
    BACKEND_URL = f"http://127.0.0.1:{PORT}"
    backend_thread = threading.Thread(target=run_backend, args=(listener,), daemon=True)
    backend_thread.start()

    log("[Desktop App] Đang khởi động và kiểm tra server...")
    if not wait_for_server(BACKEND_URL, timeout=600.0, thread=backend_thread):
        splash_close()
        reason = str(_BACKEND_ERROR) if _BACKEND_ERROR else "Server không phản hồi kịp."
        _show_error(
            "CIT Voice Studio - Không khởi động được",
            "Không mở được server nội bộ.\n\n"
            f"Chi tiết: {reason}\n\n"
            f"Xem nhật ký tại: {LOG_FILE}",
        )
        return

    # 4. Linux: mở bằng trình duyệt. Cửa sổ riêng ở đó cần GTK/WebKit cài đúng trên
    #    máy khách - dễ hỏng mà không thêm tính năng gì. Chạy trong Terminal nên đóng
    #    Terminal (hoặc Ctrl+C) là tắt app.
    #    macOS thì KHÔNG: bản .app mở từ Launchpad không có Terminal, mở bằng trình
    #    duyệt thì app chạy ngầm và người dùng không có cách tắt. Mac dùng cửa sổ riêng
    #    (pywebview + WebKit có sẵn của macOS, PyObjC đóng gói kèm) như Windows; không
    #    nạp được thì vẫn rơi xuống trình duyệt ở bước 4a.
    if sys.platform.startswith("linux"):
        splash_close()
        log("[Desktop App] Giao diện mở trong trình duyệt. Giữ cửa sổ Terminal này "
            "trong lúc dùng; đóng nó hoặc bấm Ctrl+C để tắt ứng dụng.")
        _run_in_browser()
        return

    # 4a. Không nạp được PyWebView (thiếu .NET Framework / pythonnet) → dùng trình duyệt
    if webview is None:
        splash_close()
        _run_in_browser(_WEBVIEW_IMPORT_ERROR)
        return

    # 4b. Có PyWebView nhưng máy thiếu WebView2 Runtime. KHÔNG được mở cửa sổ: pywebview
    #     sẽ lặng lẽ dựng nó bằng engine IE11, và giao diện React hiện ra trắng trơn.
    #     Thà mở trình duyệt - đủ tính năng, và người dùng thấy được thứ gì đó.
    if not webview2_available():
        splash_close()
        _run_in_browser(
            "Máy chưa cài Microsoft Edge WebView2 Runtime nên không dựng được cửa sổ "
            f"ứng dụng. Cài tại: {WEBVIEW2_DOWNLOAD_URL}"
        )
        return

    # 4c. Ghi lại môi trường. Không có mấy dòng này thì sự cố trên máy người dùng là
    #     không thể chẩn đoán - bản --windowed không có console để đọc gì cả.
    try:
        import platform
        log(f"[Chẩn đoán] Windows: {platform.platform()}")
        log(f"[Chẩn đoán] WebView2 có: {webview2_available()}")
        log(f"[Chẩn đoán] pywebview: {getattr(webview, '__version__', '?')}")
        from webview.platforms import winforms as _wf
        log(f"[Chẩn đoán] Engine thực dùng: {getattr(_wf, 'renderer', '?')}"
            f" | is_chromium={getattr(_wf, 'is_chromium', '?')}")
    except Exception as e:
        log(f"[Chẩn đoán] Không đọc được thông tin engine: {e}")
    try:
        import mimetypes
        log("[Chẩn đoán] MIME .js={} .mjs={} .css={}".format(
            mimetypes.guess_type("a.js")[0], mimetypes.guess_type("a.mjs")[0],
            mimetypes.guess_type("a.css")[0]))
    except Exception as e:
        log(f"[Chẩn đoán] Không đọc được kiểu MIME: {e}")
    log(f"[Chẩn đoán] Giao diện lấy từ: {BACKEND_URL}")

    # 5. Tạo đối tượng Desktop API, cửa sổ Desktop Native và chạy vòng lặp giao diện.
    #    Backend WebView2 của PyWebView nằm trong platforms/winforms.py nên vẫn cần
    #    pythonnet - lỗi ở đây không được làm chết ứng dụng.
    try:
        log("[Desktop App] Mở cửa sổ CIT Voice Studio...")
        desktop_api = DesktopApi()
        # Kep cua so vao vung lam viec that. Doc duoc thi tu tinh, khong doc duoc thi
        # de pywebview tu xu (CenterScreen) - van chay, chi la co the hoi lech.
        work = _primary_work_area_logical()
        if work:
            geom = fit_window_to_screen(work)
            log(f"[Chan doan] Vung lam viec (logic): {work[2]}x{work[3]} tai ({work[0]},{work[1]})")
            log(f"[Chan doan] Cua so: {geom['width']}x{geom['height']} tai ({geom['x']},{geom['y']})")
        else:
            geom = {"width": WINDOW_PREFERRED[0], "height": WINDOW_PREFERRED[1],
                    "min_size": WINDOW_MIN}
            log("[Chan doan] Khong doc duoc vung lam viec - dung kich thuoc mac dinh.")
        window = webview.create_window(
            title="CIT Voice Studio - AI Text to Speech",
            url=BACKEND_URL,
            background_color="#f3f8f8",
            hidden=True,
            resizable=True,
            text_select=True,
            js_api=desktop_api,
            **geom,
        )
        desktop_api.set_window(window)
        revealed = threading.Event()

        def reveal_window():
            if revealed.is_set():
                return
            revealed.set()
            splash_close()
            window.show()

        def reveal_fallback():
            # Do not leave a hidden app behind if WebView2 never signals loaded.
            if not window.events.loaded.wait(15):
                log("[Chẩn đoán] WebView2 không báo đã nạp sau 15 giây; hiện cửa sổ để chẩn đoán.")
                reveal_window()

        window.events.loaded += reveal_window
        threading.Thread(target=reveal_fallback, daemon=True).start()
        # CIT_DEBUG=1 bật devtools để xem lỗi JavaScript - cách duy nhất chẩn đoán
        # được tình trạng "cửa sổ mở ra nhưng trắng trơn" trên máy người dùng.
        debug = os.environ.get("CIT_DEBUG", "") not in ("", "0")
        log(f"[Chẩn đoán] Mở cửa sổ (devtools={debug})...")
        # Windows ép WebView2 (xem 4b). macOS: None = backend Cocoa/WebKit mặc định.
        webview.start(gui="edgechromium" if sys.platform == "win32" else None, debug=debug)
        splash_close()
        log("[Chẩn đoán] Cửa sổ đã đóng.")
    except Exception as e:
        splash_close()
        _run_in_browser(e)


if __name__ == "__main__":
    main()

