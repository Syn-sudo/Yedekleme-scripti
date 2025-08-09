# Yedekleme-scripti
## Bu proje, belirlediğiniz bir klasörü otomatik olarak izler, içine eklenen dosya veya klasörleri zipleyerek Google Drive hesabınıza yükler ve ardından yerel dosyaları siler. Arka planda çalışan, kullanımı kolay bir yedekleme çözümüdür.

---

## Özellikler

* İzlenen klasöre eklenen tüm dosya ve klasörleri otomatik algılar.  
* Klasörleri zip dosyasına dönüştürür.  
* Google Drive hesabınıza güvenli şekilde yükler.  
* Yedeklenen dosyaları yerelden otomatik siler.  
* Sistem tepsisinde (tray) çalışan arayüz ile kolay kontrol sağlar.  
* Dosya kilitlenmeleri ve yükleme hatalarında otomatik yeniden deneme mekanizması sunar.  

---

## Gereksinimler

* Python 3.7 veya üzeri  
* Google hesabı (Drive erişimi için)  
* İnternet bağlantısı (ilk yetkilendirme ve dosya yükleme için)  

---

## Google API Ayarları

Google Drive API erişimi için:

1. [Google Cloud Console](https://console.cloud.google.com/) sitesine giriş yapın.  
2. Yeni bir proje oluşturun.  
3. **API’ler ve Hizmetler > Kitaplık** bölümünden **Google Drive API**’yi etkinleştirin.  
4. **Kimlik Bilgileri** sekmesine gidin.  
5. **Kimlik bilgisi oluştur** → **OAuth istemci kimliği** seçeneğini seçin.  
6. Uygulama türü olarak **Masaüstü uygulaması**’nı seçin.  
7. Oluşturduğunuz istemcinin JSON dosyasını indirip, proje klasörüne `client_secrets.json` olarak kaydedin.  

---

## Kurulum ve Başlangıç

### 1. Gerekli Kütüphanelerin Yüklenmesi

Proje klasörünüzde aşağıdaki komutu çalıştırarak tüm bağımlılıkları yükleyin:

Komut satırında proje klasörüne gidin ve aşağıdaki komutu çalıştırın:

pip install -r requirements.txt

## .exe Dosyasını Oluşturma
Komut satırında proje klasörüne gidin ve aşağıdaki komutu çalıştırın:

pyinstaller --onefile --noconsole --name İstediğinizDosyaAdi dosyanizinadi.py
Bu komut, uygulamanızı tek bir .exe dosyası haline getirir ve sistem tepsisinde sessizce çalışmasını sağlar.

## .exe Dosyasını Bulma
Komut tamamlandıktan sonra proje klasörünüzde dist adlı bir klasör oluşacaktır. .exe dosyanız bu klasörün içinde yer alır.

## Uygulamayı Otomatik Başlatmaya Ayarlama
Windows + R tuşlarına aynı anda basın.

Açılan pencereye shell:startup yazıp Enter’a basın.

Açılan klasöre, dist klasöründen oluşturduğunuz .exe dosyasını sürükleyip bırakın.

## Kullanım
Bilgisayarınız her açıldığında uygulama otomatik olarak başlayacak ve belirlediğiniz klasörü izleyerek yedekleme işlemlerini gerçekleştirecektir.

İlk çalıştırmada Google Drive’a giriş yapmanız istenecek.

Sonrasında uygulama arka planda sessizce çalışmaya devam edecektir.
