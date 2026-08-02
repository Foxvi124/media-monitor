# 📰 media-monitor

[![tests](https://github.com/Foxvi124/media-monitor/actions/workflows/tests.yml/badge.svg)](https://github.com/Foxvi124/media-monitor/actions/workflows/tests.yml)
[![digest](https://github.com/Foxvi124/media-monitor/actions/workflows/digest.yml/badge.svg)](https://github.com/Foxvi124/media-monitor/actions/workflows/digest.yml)
[![python](https://img.shields.io/badge/python-3.9%2B-blue)](requirements.txt)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Pemantau media open-source: pantau kata kunci di puluhan feed RSS/Atom dan terima digest berita harian otomatis — gratis, tanpa API key, berjalan sendiri di repo GitHub-mu lewat GitHub Actions.**

Layanan *media monitoring* komersial mahal; alat ini memberikan intinya secara terbuka: kamu tentukan **feed** (media mana saja) dan **topik** (kata kunci apa saja), lalu setiap pagi pukul 05.00 WIB sebuah digest Markdown + HTML muncul di folder [`digests/`](digests/) — dikelompokkan per topik, kata kunci disorot, bebas duplikat antar-hari, lengkap dengan daftar feed yang gagal diambil. Versi 2 menambahkan otak: berita yang sama dari beberapa media otomatis **diklaster jadi satu** (🔥 untuk yang ramai), **tren topik** dibandingkan rata-rata 7 hari (↑ ↓ →), **rekap mingguan** bergrafik dibuat otomatis tiap Senin, dan digest bisa dikirim ke **Telegram atau email**.

Cocok untuk jurnalis yang memantau isu liputan, humas yang memantau pemberitaan institusi, peneliti dan mahasiswa yang mengikuti topik tugas akhir, LSM yang mengawal isu lingkungan, atau siapa pun yang tidak mau ketinggalan berita tentang hal yang penting baginya.

➡️ **Lihat contoh keluarannya:** [`digests/contoh.md`](digests/contoh.md)

*English summary at the bottom.* 🇬🇧

---

## Mulai dalam 5 menit (tanpa install apa pun)

1. **Fork** repo ini ke akunmu (tombol Fork di kanan atas).
2. **Edit [`config.yaml`](config.yaml)** langsung di GitHub: ganti daftar `feeds` dan `topics` sesuai kebutuhanmu, lalu commit.
3. Buka tab **Actions** → pilih workflow **digest** → **Run workflow** untuk mencoba pertama kali. Selesai — digest pertamamu muncul di `digests/latest.md`, dan selanjutnya dibuat otomatis **setiap hari pukul 05.00 WIB** (jadwal bisa diubah di [`.github/workflows/digest.yml`](.github/workflows/digest.yml)).

> Catatan: pada fork, GitHub menonaktifkan workflow terjadwal sampai kamu membukanya sekali lewat tab Actions.

## Jalankan lokal (opsional)

```bash
pip install -r requirements.txt
python run.py                      # baca config.yaml → tulis digests/
python run.py --dry-run            # cetak digest ke layar saja
python run.py --config saya.yaml --output keluaran --state state.json
python run.py --check              # uji kesehatan semua feed di config
python run.py --weekly             # buat rekap mingguan dari history.json
python run.py --import-opml f.opml # ubah OPML (ekspor RSS reader) jadi YAML
python run.py --export-opml f.opml # ekspor daftar feed ke OPML
```

## Konfigurasi

Semua pengaturan ada di satu berkas `config.yaml`:

```yaml
utc_offset_hours: 7    # zona waktu digest (7 = WIB, 8 = WITA, 9 = WIT)
tz_label: WIB
max_age_hours: 36      # abaikan artikel lebih tua dari ini (0 = tanpa batas)
limit_per_topic: 25
snippet_chars: 220

feeds:
  - name: BBC News Indonesia
    url: https://feeds.bbci.co.uk/indonesia/rss.xml

topics:
  - name: Pertambangan & Hilirisasi
    any: [nikel, smelter, hilirisasi]   # cocok bila SALAH SATU muncul
    all: []                             # (opsional) SEMUA harus muncul
    exclude: [zodiak]                   # (opsional) buang bila ini muncul
```

Aturan pencocokan: tidak peka kapital, mendukung **frasa** ("kecerdasan buatan"), dan memakai **batas kata** — kata kunci `nikel` cocok dengan "Nikel," tetapi tidak dengan "nikelin". Pencocokan dilakukan pada judul + ringkasan artikel.

## Cara kerja

`run.py` mengambil semua feed (kegagalan per-feed hanya dicatat, tidak menghentikan proses) → menyaring artikel yang terlalu tua → membuang artikel yang sudah pernah dilaporkan (disimpan di `state.json`, otomatis di-commit oleh workflow) → mencocokkan tiap artikel dengan tiap topik → merender `digests/digest-YYYY-MM-DD.md`, `latest.md`, dan `latest.html` yang rapi dibuka di ponsel. Semuanya pustaka standar Python + PyYAML; tidak ada API key, tidak ada layanan pihak ketiga.

## Fitur lanjutan (v2)

**Klaster lintas media.** Berita yang sama dari beberapa outlet digabung jadi satu entri — sumber lain tercantum sebagai "diberitakan juga oleh …", kata kunci digabung, dan entri yang ramai (≥2 kata kunci atau ≥2 media) diberi tanda 🔥 serta naik ke atas. Ambang kemiripan judul diatur lewat `cluster_threshold` (Jaccard 0–1, bawaan 0.55).

**Tren & rekap mingguan.** Setiap run dicatat ke `history.json`; judul topik di digest harian diberi panah ↑ ↓ → dibandingkan rata-rata 7 hari sebelumnya (aktif setelah riwayat ≥3 hari). Setiap Senin 05.30 WIB workflow **weekly** membuat `digests/mingguan-YYYY-Www.md` berisi tabel perbandingan pekan-ke-pekan, kata kunci terpanas, dan grafik batang SVG yang dirender tanpa dependensi.

**Notifikasi Telegram.** Buat bot lewat [@BotFather](https://t.me/BotFather) → salin token; dapatkan chat ID-mu (mis. lewat @userinfobot). Simpan keduanya di repo → Settings → Secrets and variables → Actions sebagai `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID`, lalu set `notify.telegram: true` di config. Ringkasan digest terkirim tiap pagi; tanpa secret, langkah ini dilewati dengan catatan di log.

**Notifikasi email.** Set secrets `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, lalu `notify.email.enabled: true` dan isi `to:`. Email berisi versi HTML digest lengkap.

**Kesehatan feed.** Feed yang gagal ≥3 run beruntun ditandai 💀 "diduga mati" di footer digest — beda dari kegagalan sesaat (⚠), jadi kamu tahu persis URL mana yang perlu diganti.

**OPML & JSON.** Pindahkan langganan dari RSS reader mana pun lewat `--import-opml` (menghasilkan potongan YAML siap tempel) atau bagikan daftar feed-mu lewat `--export-opml`. Setiap run juga menulis `digests/latest.json` terstruktur untuk diolah program lain.

## Keterbatasan (jujur)

- **URL RSS media sering berpindah atau dimatikan.** Daftar bawaan di `config.yaml` adalah titik awal, bukan kebenaran abadi — feed yang gagal selalu tercantum di bagian bawah setiap digest supaya mudah kamu perbaiki.
- Digest hanya memuat **judul + ringkasan + tautan** ke sumber asli, bukan isi penuh artikel — menghormati hak situs sumber dan mendorong pembaca berkunjung langsung.
- Pencocokan bersifat **literal per kata kunci**, bukan pemahaman semantik: "emas" tidak akan menangkap "logam mulia".
- Ini alat komunitas untuk kebutuhan pribadi/riset, bukan pengganti layanan pemantauan media profesional dengan arsip dan analitik.

## Pengembangan

```bash
pip install -r requirements.txt pytest
pytest        # 30 tes: parser, matcher, klaster, tren, notifikasi, OPML,
              # state, digest, dan dua uji end-to-end offline
```

Struktur: `monitor/feeds.py` (ambil + parse), `monitor/matcher.py` (topik & sorot), `monitor/cluster.py` (klaster lintas media), `monitor/trends.py` (riwayat, tren, rekap + SVG), `monitor/notify.py` (Telegram/email), `monitor/opml.py` (impor/ekspor), `monitor/digest.py` (state + render), `monitor/cli.py` (alur utama). Kontribusi diterima — feed baru yang terverifikasi, perbaikan parser, atau fitur (mis. kirim digest ke email/Telegram) silakan lewat pull request.

## Lisensi

[MIT](LICENSE) © 2026

---

## 🇬🇧 English summary

**media-monitor** is an open-source, zero-API-key media monitoring tool: define your RSS/Atom feeds and keyword topics in one `config.yaml`, and GitHub Actions delivers a daily Markdown + HTML digest into `digests/` — grouped by topic, keywords highlighted, deduplicated across days, with failed feeds listed honestly in the footer. Fork → edit `config.yaml` → enable the **digest** workflow; or run locally with `python run.py`. Matching is case-insensitive, phrase-aware, and word-boundary safe (`any` / `all` / `exclude` per topic). v2 adds cross-outlet story clustering with 🔥 hot-marking, 7-day trend arrows per topic, an automated weekly recap with a dependency-free SVG chart, optional Telegram/email notifications via GitHub Secrets, per-feed health tracking (💀 after 3 consecutive failures), OPML import/export, and a machine-readable `latest.json`. Pure standard-library Python + PyYAML, 30 passing tests including two offline end-to-end runs over fixture feeds. Default feeds/topics are Indonesian-media-oriented but everything is configurable. Limitations are stated plainly in the section above: feed URLs rot, matching is literal, and digests carry titles + summaries only, linking readers to the original sources.
