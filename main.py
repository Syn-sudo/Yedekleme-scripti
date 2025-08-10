import os
import time
import zipfile
import threading
from queue import Queue
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import pystray
from PIL import Image

# -------- Ayarlar --------
WATCH_FOLDER = r"\Yedekler"         # İzlenecek klasör yolu (buraya eklenen dosyalar yüklenecek)
CREDENTIALS_FILE = "credentials.json"  # Google Drive kimlik dosyası
ICON_PATH = r"\logo.ico"            # Tray (sistem tepsisi) ikonunun dosya yolu
TRAY_NAME = "Yedekleme"             # Tray ikonu ismi
DEBOUNCE_SECONDS = 3                # Aynı dosya tekrar işlenmesin diye bekleme süresi (saniye)

# -------- Google Drive Bağlantısı --------
def drive_auth():
    """
    Google Drive'a bağlanır ve kimlik doğrulamasını yapar.
    credentials.json dosyası varsa onu kullanır, yoksa tarayıcıdan giriş ister.
    """
    gauth = GoogleAuth()
    gauth.LoadCredentialsFile(CREDENTIALS_FILE)
    if gauth.credentials is None:
        gauth.LocalWebserverAuth()  # İlk kez giriş yapılacaksa tarayıcıyı açar
    elif gauth.access_token_expired:
        gauth.Refresh()              # Oturum süresi dolmuşsa yeniler
    else:
        gauth.Authorize()            # Oturum aktifse direkt kullanılır
    gauth.SaveCredentialsFile(CREDENTIALS_FILE)
    return GoogleDrive(gauth)

def upload_file(drive, title, file_path, retry=3):
    """
    Belirtilen dosyayı Google Drive'a yükler.
    """
    print(f"[BİLGİ] Yükleniyor: {title}")
    gfile_metadata = {'title': title}
    for attempt in range(1, retry+1):
        try:
            gfile = drive.CreateFile(gfile_metadata)
            gfile.SetContentFile(file_path)
            gfile.Upload()
            print(f"[BAŞARILI] Yüklendi: {title}")
            return True
        except Exception as e:
            print(f"[HATA] Yükleme hatası (Deneme {attempt}): {e}")
            time.sleep(2)
    return False

def zip_and_upload_folder(drive, folder_path):
    """
    Bir klasörü ZIP dosyasına dönüştürür ve Google Drive'a yükler.
    """
    try:
        base_name = os.path.basename(folder_path.rstrip(os.sep))
        timestamp = int(time.time())
        zip_filename = f"{base_name}_{timestamp}.zip"
        zip_path = os.path.join(WATCH_FOLDER, zip_filename)

        # Klasörü ZIP'e ekle
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, folder_path)
                    zipf.write(full_path, arcname)

        time.sleep(0.5)
        upload_file(drive, zip_filename, zip_path)

    except Exception as e:
        print(f"[HATA] Klasör işlenirken hata oluştu: {e}")

def process_file(drive, file_path):
    """
    Tek bir dosyayı Google Drive'a yükler.
    """
    try:
        filename = os.path.basename(file_path)
        upload_file(drive, filename, file_path)
    except Exception as e:
        print(f"[HATA] Dosya işlenirken hata oluştu: {e}")

def process_path(drive, path):
    """
    Gelen yolun dosya mı klasör mü olduğunu kontrol eder
    ve uygun yükleme fonksiyonunu çağırır.
    """
    print(f"[BİLGİ] İşleniyor: {path}")
    if os.path.isdir(path):
        zip_and_upload_folder(drive, path)
    else:
        process_file(drive, path)

# -------- Dosya İzleyici --------
class ChangeHandler(FileSystemEventHandler):
    """
    Watchdog ile izlenen klasörde yeni dosya/klasör oluştuğunda tetiklenir.
    Aynı dosyanın kısa süre içinde tekrar işlenmesini önlemek için zaman kontrolü yapar.
    """
    def __init__(self, queue):
        self.queue = queue
        self.last_processed = {}

    def on_created(self, event):
        path = event.src_path
        now = time.time()
        # Kısa sürede tekrar işlenmesini engelle
        if path in self.last_processed and (now - self.last_processed[path] < DEBOUNCE_SECONDS):
            return
        self.last_processed[path] = now
        self.queue.put(path)
        # Eski kayıtları temizle
        keys_to_delete = [k for k, v in self.last_processed.items() if now - v > DEBOUNCE_SECONDS * 10]
        for k in keys_to_delete:
            del self.last_processed[k]

def worker(drive, queue):
    """
    Kuyruğa gelen dosya/klasörleri sırayla işler.
    """
    while True:
        path = queue.get()
        if path is None:
            break
        process_path(drive, path)
        queue.task_done()

def process_existing(drive, queue):
    """
    Program ilk açıldığında izlenecek klasörde halihazırda var olan dosya/klasörleri işler.
    """
    print("[BİLGİ] Var olan dosya ve klasörler işleniyor...")
    for item in os.listdir(WATCH_FOLDER):
        full_path = os.path.join(WATCH_FOLDER, item)
        if os.path.exists(full_path):
            queue.put(full_path)

def run_watcher():
    """
    Google Drive bağlantısını kurar, izleyiciyi başlatır
    ve klasördeki değişiklikleri sürekli takip eder.
    """
    print("[BİLGİ] Google Drive bağlantısı kuruluyor...")
    drive = drive_auth()

    q = Queue()
    worker_thread = threading.Thread(target=worker, args=(drive, q), daemon=True)
    worker_thread.start()

    process_existing(drive, q)

    event_handler = ChangeHandler(q)
    observer = Observer()
    observer.schedule(event_handler, path=WATCH_FOLDER, recursive=True)
    observer.start()

    print(f"[BİLGİ] '{WATCH_FOLDER}' klasörü izleniyor...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[BİLGİ] Program durduruluyor...")
        observer.stop()

    observer.join()
    q.put(None)
    worker_thread.join()
    print("[BİLGİ] Program kapandı.")

def on_quit(icon, item):
    """
    Tray menüsünden 'Çıkış' seçildiğinde programı kapatır.
    """
    icon.stop()
    os._exit(0)

def main():
    """
    Tray ikonu başlatılır, dosya izleme işlemi ayrı bir thread üzerinde çalışır.
    """
    try:
        icon_image = Image.open(ICON_PATH)
    except Exception as e:
        print(f"[HATA] İkon dosyası yüklenemedi: {e}")
        return

    print("[BİLGİ] İkon yüklendi.")

    # Tray ikonu oluştur
    icon = pystray.Icon(
        TRAY_NAME,  # Tray ID
        icon_image, # İkon resmi
        TRAY_NAME,  # Tooltip ismi
        menu=pystray.Menu(
            pystray.MenuItem("Çıkış", on_quit)
        )
    )

    # Dosya izleyici ayrı thread'de çalışır
    watcher_thread = threading.Thread(target=run_watcher, daemon=True)
    watcher_thread.start()

    print("[BİLGİ] Tray ikonu çalıştırılıyor...")
    icon.run()

if __name__ == "__main__":
    main()
