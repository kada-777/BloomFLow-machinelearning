# RFC-001: BloomFlow System Architecture

- **Status:** Proposed
- **Owner:** Engineering

## Decision

BloomFlow terdiri dari React/Vite frontend, Express.js backend, layanan AI/ML FastAPI, dan PostgreSQL. Frontend berkomunikasi dengan backend melalui HTTPS/REST; backend adalah satu-satunya orchestration dan validation layer untuk database serta layanan AI/ML.

## Responsibilities

- Frontend menampilkan halaman, mengumpulkan input, dan menampilkan error; validasi di frontend bukan otoritas bisnis.
- Backend menangani JWT, role/branch scope, business rule, transaksi, FIFO, validasi planning date dan duplicate plan, pemilihan cutoff Daily Sales, validasi output AI/ML, serta pemilihan hasil forecast yang tanggalnya cocok dengan `planningDate`.
- AI/ML menerima cutoff melalui field request `forecastDate`, menggunakan Daily Sales sampai cutoff tersebut, dan mengembalikan horizon tetap 1-3; AI/ML tidak boleh mengubah stok, membuat movement, atau mengeksekusi workflow.
- PostgreSQL menjaga data, constraint, locking, dan atomic transaction.

## Deployment and Failure Handling

Frontend dapat di-host di Vercel; backend dan AI/ML service di Render; database di managed PostgreSQL. Layanan ML menghasilkan baseline ketika minimum-history gate yang berlaku tidak terpenuhi atau training gagal karena data training. Backend mengembalikan error API yang konsisten, mencatat operasi/audit error tanpa token atau password, memvalidasi response ML, dan menggunakan fallback backend bila layanan ML unavailable atau gagal.

## Transaction Principle

Setiap operasi perubahan stok bersifat atomik. Backend mengunci baris stok yang relevan, memvalidasi ulang setelah lock, menyimpan perubahan stok dan inventory movement dalam transaksi yang sama, lalu rollback seluruh operasi bila satu langkah gagal.
