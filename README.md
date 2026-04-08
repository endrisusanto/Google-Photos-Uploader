# 📷 Google Photos Uploader (Unlimited)

Proyek ini berbasis pada [google_photos_mobile_client](https://github.com/xob0t/google_photos_mobile_client) yang memungkinkan Anda untuk **memantau folder** (termasuk share SMB/NAS) dan **mengunggah foto ke Google Photos secara otomatis** tanpa mengurangi kuota penyimpanan, menggunakan kontainer Docker yang ringan.

---

## 🚀 Fitur Utama

- ✅ **Penyimpanan Tanpa Batas**: Mengunggah foto dalam kualitas asli tanpa memakan kuota storage Google (menggunakan identitas perangkat Pixel).
- 🔁 **Otomatisasi**: Memantau folder secara real-time dan langsung mengunggah file baru.
- 🗑️ **Auto-Clean**: Menghapus file lokal secara otomatis setelah berhasil terunggah (cocok untuk server dengan kapasitas terbatas).
- 🖥️ **Dashboard Real-time**: Pantau status unggahan, kecepatan, dan log melalui antarmuka web yang modern.
- 📁 **Fleksibel**: Bekerja dengan folder lokal maupun mount network (SMB/NAS).
- 🐳 **Dockerized**: Berjalan di dalam kontainer Docker minimalis.

---

## 📦 Kebutuhan Sistem

- Docker dan Docker Compose yang sudah terinstal.
- Folder berisi foto (atau mount SMB share).
- Kode otentikasi `AUTH_DATA` (lihat bagian cara mendapatkan kunci di bawah).

---

## ⚙️ Konfigurasi Docker Compose

Gunakan konfigurasi `docker-compose.yml` berikut:

```yaml
services:
  gphotos-uploader:
    build: .
    container_name: gphotos-uploader
    restart: unless-stopped
    environment:
      - WATCHED_FOLDER=/data
      - AUTH_DATA=ISI_DENGAN_AUTH_DATA_ANDA
    volumes:
      - /jalur/ke/foto/anda:/data:z
      - ./uploader.db:/app/uploader.db:z # Opsional: jika ingin database persisten
    ports:
      - "8080:8080"
```

Ganti `/jalur/ke/foto/anda` dengan lokasi folder foto Anda di komputer host.

---

## ▶️ Cara Memulai

1. Buka terminal dan masuk ke folder proyek.
2. Jalankan kontainer:
   ```bash
   docker-compose up -d --build
   ```
3. Buka Dashboard di browser:
   `http://localhost:8080`
4. Cek log secara langsung:
   ```bash
   docker-compose logs -f
   ```

---

## 🔑 Cara Mendapatkan `AUTH_DATA`

Anda hanya perlu melakukan ini **satu kali** untuk mendapatkan kunci enkripsi permanen.

### ✅ Opsi 1 – Menggunakan ReVanced (Tanpa Root)

1. Instal Google Photos ReVanced di Android Anda:
   - Instal [GmsCore](https://github.com/ReVanced/GmsCore/releases).
   - Instal APK Google Photos yang sudah dipatch.
2. Hubungkan perangkat ke PC melalui ADB.
3. Jalankan perintah ini di terminal:
   - **Windows:** `adb logcat | FINDSTR "auth%2Fphotos.native"`
   - **Linux/macOS:** `adb logcat | grep "auth%2Fphotos.native"`
4. Buka aplikasi Google Photos ReVanced dan login.
5. Salin baris yang muncul mulai dari `androidId=...` hingga akhir. Itulah `AUTH_DATA` Anda! 🎉

---

## 🔄 Pembaruan

Untuk memperbarui aplikasi ke versi terbaru:

```bash
git pull
docker-compose up -d --build
```

---

## 💡 Catatan
- Aplikasi ini akan **menghapus** file di folder lokal setelah berhasil diunggah ke Google Photos. Pastikan Anda memiliki backup jika diperlukan.
- Jika menggunakan SMB share, pastikan izin (permission) user kontainer sudah benar untuk membaca dan menghapus file.
- Proyek ini adalah implementasi praktis dari riset [google_photos_mobile_client](https://github.com/xob0t/google_photos_mobile_client).

---