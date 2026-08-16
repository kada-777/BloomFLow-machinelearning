# RFC-005: AI/ML Demand Forecasting

- **Status:** Proposed
- **Owner:** AI/ML and Backend

## Request Contract

Backend memanggil `POST /forecast`. Field request `forecastDate` dipertahankan sebagai nama wire contract, tetapi nilainya adalah cutoff Daily Sales: tanggal penjualan terakhir yang boleh digunakan oleh pipeline untuk forecast run tersebut. Jika field tidak diberikan, ML menggunakan tanggal Daily Sales terbaru yang tersedia.

ML tidak menerima `planningDate` atau `planningHorizon` dari frontend maupun backend. Data training dan feature forecast dibatasi sampai cutoff yang dipilih.

## Response Contract

Response memuat `cutoffDate`, `forecastMethod`, `modelVersion`, dan `results`. Setiap item `results` memuat `branchId`, `flowerId`, `branchName`, `flowerName`, `forecastDate`, `horizon`, `forecastDemand`, `forecastMethod`, `modelVersion`, dan `generatedAt`.

ML selalu menghasilkan horizon 1, 2, dan 3. Untuk setiap hasil, `forecastDate = cutoffDate + horizon` hari:

| Cutoff | Horizon | Forecast date |
|---|---:|---|
| 12 Agustus | 1 | 13 Agustus |
| 12 Agustus | 2 | 14 Agustus |
| 12 Agustus | 3 | 15 Agustus |

## Responsibility Boundary

Backend memilih cutoff dan memilih hasil yang `forecastDate`-nya sama dengan `planningDate`. Backend juga menangani validasi planning date, aturan tanggal Asia/Jakarta, duplicate plan, validasi response ML, persistence, dan distribution workflow.

ML hanya menghasilkan forecast. ML tidak menghitung valid planning date, tidak memeriksa duplicate plan, tidak mendukung horizon di atas 3, dan tidak mengubah inventory atau membuat distribution plan/order.

## Model and Fallback

Model MVP harus ringan, misalnya regression atau Random Forest. Jika history kurang, artifact tidak tersedia, atau service gagal, fallback menggunakan baseline seven-day moving average. Fallback ditandai dengan `forecastMethod: BASELINE` dan `modelVersion: baseline-v1` pada response dan setiap item hasil; jika service gagal, backend menangani fallback tersebut. AI/ML failure tidak boleh mengganggu transaksi inventory.

## Versioning

Artifact berada di lokasi terkontrol. `forecastMethod`, `modelVersion`, dan `generatedAt` disimpan bersama setiap hasil forecast agar dapat diaudit.
