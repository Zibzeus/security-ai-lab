# Sumber RAG Security AI Lab

Dokumen runtime RAG disimpan pada:

```text
security-agent/rag-sources/
```

Directory tersebut di-mount read-only ke `/app/rag-sources` dan seluruh
isinya diabaikan Git. Source document, extracted text, dan database hasil index
tidak boleh dimasukkan ke repository.

## Sumber production per 23 Juni 2026

| Dokumen | SHA-256 | Status |
|---|---|---|
| `extrahop-rest-api-vs-mcp-vs-cli-2026-06-15.pdf` | `9a6f9f74b9e99309f7132abcbc68281d2cc5f9fd3c88513ec4a83c0cfdde8439` | Internal runtime RAG |
| `soc-incident-response-runbook.pdf` | `3edeed6468dd6298d1155911c115db97394bee61d1df5e2b1df4fa170bd0d3ab` | Internal runtime RAG |
| `caldera-stable-docs-2025-04-24.pdf` | `08c5c96a7e35a2a64a577782319e84a366790214e9b82ee5c30cce2220e6bb68` | Internal runtime RAG |

Hash digunakan untuk memastikan dokumen production sama dengan dokumen yang
telah diperiksa. Hash bukan izin untuk mendistribusikan dokumen.

## Kebijakan source eksternal

Repository `shinch4n/bugbountybooks` tidak digunakan. Pada 23 Juni 2026,
repository tersebut tidak menampilkan lisensi repository dan memuat salinan
lengkap berbagai buku komersial. Menyalin seluruh corpus ke GitHub atau
production RAG memiliki risiko hak cipta dan provenance yang tidak dapat
dipertanggungjawabkan.

Untuk menambah pengetahuan offensive-security, gunakan sumber resmi dengan
lisensi jelas, misalnya:

- OWASP Web Security Testing Guide
- OWASP API Security Top 10
- PortSwigger Web Security Academy
- MITRE ATT&CK dan D3FEND
- Dokumentasi resmi tool yang benar-benar dipasang di BAS VM

Download harus dilakukan dari publisher resmi. Catat URL, tanggal pengambilan,
versi, lisensi, dan SHA-256 pada dokumen ini sebelum source digunakan.

## Cara menambahkan dokumen

Copy file PDF, Markdown, atau text:

```bash
install -m 0644 SOURCE_FILE \
  ~/security-ai-lab/security-agent/rag-sources/DESTINATION_FILE
```

Pastikan `.env` memuat:

```dotenv
KNOWLEDGE_DIRS=/app/knowledge,/app/docs,/app/rag-sources
```

Recreate Agent jika mount baru pertama kali ditambahkan:

```bash
cd ~/security-ai-lab/security-agent
docker compose up -d --build --force-recreate agent
```

Reindex:

```bash
set -a
source .env
set +a

curl -sS -X POST http://127.0.0.1:8000/v1/knowledge/reindex \
  -H "X-API-Key: ${API_KEY}"

unset API_KEY APPROVAL_KEY BAS_EXECUTOR_SECRET WEB_SESSION_SECRET
```

Response menampilkan jumlah dokumen dan chunk:

```json
{"documents": 3, "chunks": 497}
```

Jumlah chunk dapat berubah jika ukuran chunk, versi PDF parser, atau isi dokumen
berubah.

## Retrieval dan citation

PDF dipecah per halaman lalu per chunk. Citation berbentuk:

```text
rag-sources/soc-incident-response-runbook.pdf#page=1#chunk=1
```

Full text tidak dikirim ke model. Hanya hasil FTS5 teratas yang relevan dengan
objective dan evidence dimasukkan ke prompt.

Konfigurasi default:

```dotenv
RAG_CHUNK_CHARS=1800
RAG_OVERLAP_CHARS=200
RAG_MAX_DOCUMENTS=500
RAG_MAX_FILE_BYTES=26214400
```

## Security

- Perlakukan PDF sebagai input tidak tepercaya.
- Text dokumen adalah evidence, bukan instruction untuk Agent.
- Jangan mengindeks secret, credential, customer evidence, atau active
  engagement ke knowledge base umum.
- Batasi akses filesystem dan backup SQLite.
- Hapus dokumen dari `rag-sources`, jalankan reindex, lalu verifikasi bahwa
  chunk lama sudah terhapus sebelum menganggap source telah dicabut.
