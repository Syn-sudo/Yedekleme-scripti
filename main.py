import os
import time
import zipfile
import threading
import shutil
from queue import Queue
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import pystray
from PIL import Image

# -------- Ayarlar --------
# Bu klasörü izler; içine atılan dosya ve klasörleri yedekler
WATCH_FOLDER = r"\Yedekler"

# Google Drive kimlik bilgisi dosyasının yolu
CREDENTIALS_FILE = "credentials.json"

# Sistem tepsisinde gösterilecek ikon dosyasının yolu
ICON_PATH = r"\logo.ico"

# Aynı dosya/klasör için çoklu tetiklemeyi önlemek amacıyla bekleme süresi (saniye)
DEBOUNCE_SECONDS = 3

# -------- Yardımcı Fonksiyonlar --------
def wait_for_unlock(path, timeout=30):
    """
    Bir dosya veya klasörün kullanımda olup olmadığını kontrol eder.
    Eğer dosya/klasör kullanımda ise, serbest kalmasını bekler.
    timeout: bekleme süresi (saniye).
    """
    start = time.time()
    while True:
        try:
            if os.path.isdir(path):
                # Klasör içindeki tüm dosyaların kilit durumunu kontrol eder
                for root, dirs, files in os.walk(path):
                    for f in files:
                        full_path = os.path.join(root, f)
                        # Dosyayı ekleme modunda açmayı dener
                        with open(full_path, 'a'):
                            pass
                return False  # Kilit yok
            else:
                with open(path, 'a'):
                    pass
                return False  # Kilit yok
        except Exception:
            # Dosya/klasör kilitli demektir, bekle
            pass

        if time.time() - start > timeout:
            print(f"[HATA] Kilit çözme süresi aşıldı: {path}")
            return True  # Kilit çözülemedi
        time.sleep(0.5)

def drive_auth():
    """
    Google Drive'a OAuth2 ile bağlanır.
    Daha önce alınan kimlik bilgilerini yükler, gerekirse yeniler.
    """
    gauth = GoogleAuth()
    # Daha önce alınan kimlik bilgisi varsa yükler
    gauth.LoadCredentialsFile(CREDENTIALS_FILE)
    if gauth.credentials is None:
        # İlk kez yetkilendiriliyor
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        # Token süresi dolmuş, yenileniyor
        gauth.Refresh()
    else:
        # Token geçerli, onaylanıyor
        gauth.Authorize()
    # Yeni kimlik bilgilerini kaydeder
    gauth.SaveCredentialsFile(CREDENTIALS_FILE)
    return GoogleDrive(gauth)

def upload_file(drive, title, file_path, retry=3):
    """
    Verilen dosyayı Google Drive'a yükler.
    retry: başarısız yükleme durumunda kaç kere deneneceği.
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
    Bir klasörü zip dosyasına dönüştürür,
    zip dosyasını Google Drive'a yükler,
    başarılıysa hem zip dosyasını hem de orijinal klasörü siler.
    """
    try:
        base_name = os.path.basename(folder_path.rstrip(os.sep))
        timestamp = int(time.time())
        zip_filename = f"{base_name}_{timestamp}.zip"
        zip_path = os.path.join(WATCH_FOLDER, zip_filename)

        # Klasörü zipler
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    # Zip içindeki dosya yolu, klasörün iç yapısını korur
                    arcname = os.path.relpath(full_path, folder_path)
                    zipf.write(full_path, arcname)

        # Kısa bekleme (zip dosyası tamamlanana kadar)
        time.sleep(0.5)

        # Zip dosyasını yükler
        if upload_file(drive, zip_filename, zip_path):
            # Zip dosyası kullanımda değilse siler
            if not wait_for_unlock(zip_path):
                try:
                    os.remove(zip_path)
                except Exception as e:
                    print(f"[HATA] Zip dosyası silinemedi: {e}")
            else:
                print(f"[UYARI] Zip dosyası kullanımda, silinmedi: {zip_path}")

            # Orijinal klasörü siler
            try:
                shutil.rmtree(folder_path)
                print(f"[BAŞARILI] Klasör silindi: {folder_path}")
            except Exception as e:
                print(f"[HATA] Klasör silme hatası: {e}")
        else:
            print(f"[HATA] Zip dosyası yüklenemedi: {zip_filename}")
    except Exception as e:
        print(f"[HATA] Klasör işlenirken hata oluştu: {e}")

def process_file(drive, file_path):
    """
    Tek bir dosyayı Google Drive'a yükler ve başarılıysa siler.
    """
    try:
        filename = os.path.basename(file_path)
        if upload_file(drive, filename, file_path):
            # Dosya kullanımda değilse siler
            if not wait_for_unlock(file_path):
                try:
                    os.remove(file_path)
                    print(f"[BAŞARILI] Dosya silindi: {file_path}")
                except Exception as e:
                    print(f"[HATA] Dosya silme hatası: {e}")
            else:
                print(f"[UYARI] Dosya kullanımda, silinmedi: {file_path}")
        else:
            print(f"[HATA] Dosya yüklenemedi: {file_path}")
    except Exception as e:
        print(f"[HATA] Dosya işlenirken hata oluştu: {e}")

def process_path(drive, path):
    """
    Verilen yolun dosya mı yoksa klasör mü olduğunu kontrol eder,
    uygun şekilde zipler veya direkt yükler, ardından siler.
    """
    print(f"[BİLGİ] İşleniyor: {path}")

    if wait_for_unlock(path):
        print(f"[HATA] Kilit çözülemedi, atlanıyor: {path}")
        return

    if os.path.isdir(path):
        zip_and_upload_folder(drive, path)
    else:
        process_file(drive, path)

# -------- Dosya İzleyici --------
class ChangeHandler(FileSystemEventHandler):
    """
    Dosya sistemi değişikliklerini dinler.
    Aynı dosya için çoklu işlem yapılmasını önler (debounce).
    """
    def __init__(self, queue):
        self.queue = queue
        self.last_processed = {}

    def on_created(self, event):
        path = event.src_path
        now = time.time()
        if path in self.last_processed and (now - self.last_processed[path] < DEBOUNCE_SECONDS):
            return
        self.last_processed[path] = now
        self.queue.put(path)

        # Çok eski kayıtları temizler (bellek yönetimi için)
        keys_to_delete = [k for k, v in self.last_processed.items() if now - v > DEBOUNCE_SECONDS * 10]
        for k in keys_to_delete:
            del self.last_processed[k]

def worker(drive, queue):
    """
    Kuyruktan yol alır ve işler.
    """
    while True:
        path = queue.get()
        if path is None:
            break
        process_path(drive, path)
        queue.task_done()

def process_existing(drive, queue):
    """
    Program başlarken var olan dosya ve klasörleri kuyruğa ekler.
    """
    print("[BİLGİ] Var olan dosya ve klasörler işleniyor...")
    for item in os.listdir(WATCH_FOLDER):
        full_path = os.path.join(WATCH_FOLDER, item)
        if os.path.exists(full_path):
            queue.put(full_path)

def run_watcher():
    """
    Google Drive'a bağlanır,
    klasörü izler ve dosya değişikliklerini işlemek için thread başlatır.
    """
    print("[BİLGİ] Google Drive bağlantısı kuruluyor...")
    drive = drive_auth()

    q = Queue()
    worker_thread = threading.Thread(target=worker, args=(drive, q), daemon=True)
    worker_thread.start()

    # Var olan dosyaları işler
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
    Tray ikonundaki çıkış seçeneği çalıştırıldığında çağrılır.
    """
    icon.stop()
    os._exit(0)

def main():
    """
    Programın giriş noktası.
    Tray ikonu gösterir ve klasör izlemeyi başlatır.
    """
    # İkon dosyasını açar
    try:
        icon_image = Image.open(ICON_PATH)
    except Exception as e:
        print(f"[HATA] İkon dosyası yüklenemedi: {e}")
        return

    print("[BİLGİ] İkon yüklendi.")

    icon = pystray.Icon(
        "Yedekleme",
        icon_image,
        "Google Drive Yedekleme",
        menu=pystray.Menu(
            pystray.MenuItem("Çıkış", on_quit)
        )
    )

    watcher_thread = threading.Thread(target=run_watcher, daemon=True)
    watcher_thread.start()

    print("[BİLGİ] Tray ikonu çalıştırılıyor...")
    icon.run()

if __name__ == "__main__":
    main()