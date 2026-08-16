# RFC-005: AI/ML Demand Forecasting

- **Status:** Proposed
- **Owner:** AI/ML and Backend

## Request Contract

Backend memanggil `POST /forecast` dengan field berikut:

- `forecastDate` (opsional): cutoff Daily Sales, yaitu tanggal penjualan terakhir yang boleh digunakan untuk training dan feature forecast. Nama field dipertahankan sebagai wire contract; jika tidak diberikan, ML menggunakan tanggal Daily Sales terbaru yang tersedia.
- `modelVersion` (opsional): versi model untuk metadata hasil ML; default `hgb-v1`.
- `eligiblePairs` (opsional): daftar object `{ branchId, flowerId }` dengan ID integer positif untuk membatasi pasangan branch-flower yang diproses. Input yang invalid, kosong, atau tidak cocok dengan pasangan yang tersedia dapat ditolak ML dengan HTTP `422`.

ML tidak menerima `planningDate` atau `planningHorizon` dari frontend maupun backend. Data training dan feature forecast menggunakan Daily Sales hanya sampai cutoff yang dipilih. Berbeda dari data tersebut, pemeriksaan minimum history global ketika `eligiblePairs` tidak diberikan saat ini menghitung seluruh tanggal Daily Sales distinct yang tersedia tanpa membatasinya ke cutoff. Jika `eligiblePairs` diberikan, pemeriksaan minimum history global tersebut tidak dijalankan.

## Response Contract

Response memuat `cutoffDate`, `forecastMethod`, `modelVersion`, dan `results`. Setiap item `results` memuat `branchId`, `flowerId`, `branchName`, `flowerName`, `forecastDate`, `horizon`, `forecastDemand`, `forecastMethod`, `modelVersion`, dan `generatedAt`.

ML selalu menghasilkan horizon 1, 2, dan 3. Untuk setiap hasil, `forecastDate = cutoffDate + horizon` hari:

| Cutoff | Horizon | Forecast date |
|---|---:|---|
| 12 Agustus | 1 | 13 Agustus |
| 12 Agustus | 2 | 14 Agustus |
| 12 Agustus | 3 | 15 Agustus |

## Responsibility Boundary

Backend memilih cutoff dan memilih hasil yang `forecastDate`-nya sama dengan `planningDate`. Backend juga menangani validasi planning date, aturan tanggal Asia/Jakarta, duplicate plan, unavailability atau failure layanan ML, validasi response ML, persistence, dan distribution workflow.

ML hanya menghasilkan forecast. ML tidak menghitung valid planning date, tidak memeriksa duplicate plan, tidak mendukung horizon di atas 3, dan tidak mengubah inventory atau membuat distribution plan/order.

## Model and Fallback

Model MVP harus ringan, misalnya regression atau Random Forest. Di dalam layanan ML, request tanpa `eligiblePairs` menggunakan baseline seven-day moving average jika minimum history global tidak terpenuhi; ML juga menggunakan baseline jika training gagal dengan error data training. Baseline dari ML ditandai dengan `forecastMethod: BASELINE` dan `modelVersion: baseline-v1` pada response dan setiap item hasil. Backend menangani unavailability atau failure layanan ML dengan fallback backend dan tetap memvalidasi response sebelum menggunakannya. Failure ML tidak boleh mengganggu transaksi inventory.

## Versioning

Artifact berada di lokasi terkontrol. `forecastMethod`, `modelVersion`, dan `generatedAt` disimpan bersama setiap hasil forecast agar dapat diaudit.
