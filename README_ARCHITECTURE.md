# 🏛️ Hansard Scraper - Arsitektur Sistem

## 📋 Ringkasan

Script ini mengambil data **Hansard** (transkrip sidang parlemen) dari API Parlemen UK menggunakan **3-step process**:

1. **Ambil TOC (Table of Contents)** → dapat semua `fragment_uid`
2. **Ambil semua fragments** → dapat konten lengkap per fragment  
3. **Gabungkan** → merge konten ke struktur tree branches

---

## 🔄 Flow Diagram

```
URL Hansard
    ↓
[extract_doc_ids_from_url]
    ↓
Document IDs (HANSARD-1323...)
    ↓
[fetch_table_of_contents] ← /daily/outline/DOCID
    ↓
branches (tree struktur) + fragment_uids (dict)
    ↓
[fetch_all_fragments] ← /daily/fragment/FRAGMENTUID (paralel)
    ↓
content_map (dict: path → text)
    ↓
[merge_content_to_branches]
    ↓
branches dengan "full_text"
    ↓
[build_full_text]
    ↓
JSON output file
```

---

## 📁 Struktur Data

### 1. **Tree Branches** (dari `fetch_table_of_contents`)

```python
{
    "id": "HANSARD-1323-fragment-1",
    "fragment_uid": "HANSARD-1323-fragment-1",
    "path": "Commons Chamber/Questions/Education/...",
    "level": 3,
    "title": "School Funding",
    "type": "SubDebate",
    "full_text": ""  # ← awalnya kosong, diisi oleh merge_content_to_branches
}
```

### 2. **Fragment UIDs** (dari `fetch_table_of_contents`)

```python
{
    "Commons Chamber/Questions": "HANSARD-1323-fragment-1",
    "Commons Chamber/Questions/Education": "HANSARD-1323-fragment-2",
    # ... dll untuk semua branches yang punya fragment
}
```

### 3. **Content Map** (dari `fetch_all_fragments`)

```python
{
    "Commons Chamber/Questions/Education": "Full text from API...",
    "Commons Chamber/Bills/Healthcare Bill": "Full text from API...",
    # ... dll
}
```

---

## 🔑 Fungsi Kunci

### `fetch_table_of_contents(doc_id: str)`

**Input:** Document ID (contoh: `HANSARD-1323879322-160369`)

**Output:** 
- `branches`: List of dict (tree structure)
- `fragment_uids`: Dict mapping path → fragment_uid

**Endpoint:** `GET /daily/outline/{doc_id}`

**Apa yang dilakukan:**
1. Ambil XML outline dari API
2. Traverse semua `<proceeding>` nodes secara rekursif
3. Build tree structure dengan `path` (breadcrumb)
4. Kumpulkan `fragment_uid` untuk setiap node yang punya

---

### `fetch_all_fragments(fragment_uids: Dict[str, str])`

**Input:** Dictionary `{path: fragment_uid, ...}`

**Output:** Dictionary `{path: full_text, ...}`

**Endpoint:** `GET /daily/fragment/{fragment_uid}` (dipanggil **paralel** dengan ThreadPoolExecutor)

**Apa yang dilakukan:**
1. Untuk setiap fragment_uid, ambil konten dari API
2. Parse XML `<fragment.text>` → ambil semua `<p>` paragraphs
3. Gabungkan teks jadi satu string
4. Return mapping `path → full_text`

**⚠️ PENTING:** 
- Endpoint `/daily/fragment/{fragment_uid}` mengembalikan **HANYA 1 fragment saja**
- Untuk mendapatkan **SEMUA konten**, kita harus panggil endpoint ini **untuk setiap fragment_uid**
- Oleh karena itu, kita menggunakan **ThreadPoolExecutor** untuk paralel requests (lebih cepat)

---

### `merge_content_to_branches(branches, content_map)`

**Input:**
- `branches`: Tree structure (masih belum ada text)
- `content_map`: Dict dari `fetch_all_fragments`

**Output:** `branches` yang sudah ada field `"full_text"`

**Apa yang dilakukan:**
1. Loop setiap branch
2. Cari `content_map[branch["path"]]`
3. Jika ada, tambahkan ke `branch["full_text"]`
4. Return branches yang sudah lengkap

---

### `build_full_text(result: Dict)`

**Input:** Full result dictionary dengan `tree_branches`

**Output:** String gabungan semua teks

**Apa yang dilakukan:**
1. Sort branches by `path` (urut dari atas ke bawah)
2. Untuk setiap branch, tambahkan:
   - Header dengan level indentation
   - Full text (jika ada)
3. Return sebagai satu string besar

---

## 🚀 Cara Pakai

### Quick Start

```bash
python hansard.py
```

Input manual URL, atau edit di code:

```python
# Di hansard.py, fungsi scrape_hansard()
url = "https://hansard.parliament.uk/Commons/2024-12-09"
result = scrape_hansard(url)
```

### Output

File `hansard_scraped.json`:

```json
{
  "url": "https://hansard.parliament.uk/Commons/2024-12-09",
  "date": "2024-12-09",
  "doc_ids": ["HANSARD-1323..."],
  "tree_branches": [
    {
      "id": "...",
      "path": "Commons Chamber/Questions/Education",
      "title": "School Funding",
      "full_text": "Mr Speaker: The member for..."
    }
  ],
  "full_text": "Commons Chamber\\n  Questions\\n    Education\\n      School Funding\\n..."
}
```

---

## 🔧 Troubleshooting

### ❓ Kenapa `full_text` kosong?

**Kemungkinan penyebab:**
1. `fragment_uid` tidak ada di TOC
2. Fragment tidak punya konten (misal: hanya header)
3. API error saat fetch fragment

**Cara debug:**
- Cek output log: "✅ Teks untuk X branches berhasil diambil"
- Cek `content_map` di `merge_content_to_branches`
- Lihat apakah `fragment_uids` dict terisi

---

### ❓ Kenapa tidak semua sections muncul?

**Kemungkinan penyebab:**
1. Hanya 1 document ID yang diproses
2. Beberapa sections tidak punya `fragment_uid`

**Cara debug:**
- Cek `doc_ids` yang ditemukan dari URL
- Lihat TOC untuk memastikan semua sections ada

---

### ❓ Kenapa scraping lambat?

**Solusi:**
- Sudah pakai **ThreadPoolExecutor** untuk paralel fetch
- Adjust `max_workers` di `fetch_all_fragments()` (default: 10)

```python
with ThreadPoolExecutor(max_workers=20) as executor:
    # ...
```

⚠️ Hati-hati: terlalu banyak workers bisa kena rate limit!

---

## 📝 Changelog

### v3.0 (Current)
- ✅ Gunakan `fetch_all_fragments` untuk ambil SEMUA konten
- ✅ Hapus fungsi `fetch_content` yang misleading
- ✅ Paralel fetching dengan ThreadPoolExecutor
- ✅ Merge konten ke tree branches dengan path matching

### v2.0
- ❌ Gunakan `fetch_content` (DEPRECATED - hanya ambil 1 fragment!)

### v1.0
- 🏗️ Basic scraping dengan BeautifulSoup

---

## 🎯 Best Practices

1. **Selalu cek log output** untuk memastikan semua fragments berhasil diambil
2. **Gunakan path matching** untuk merge konten yang tepat
3. **Handle errors** untuk setiap API call (network bisa gagal)
4. **Save intermediate results** (TOC, content_map) untuk debugging
5. **Respect rate limits** - jangan terlalu aggressive dengan paralel requests

---

## 📚 API Reference

### Endpoints yang digunakan:

1. **Table of Contents:**
   ```
   GET https://hansard-api.parliament.uk/daily/outline/{doc_id}
   ```

2. **Fragment Content:**
   ```
   GET https://hansard-api.parliament.uk/daily/fragment/{fragment_uid}
   ```

3. **Full Document (untuk backward compatibility):**
   ```
   GET https://hansard-api.parliament.uk/daily/fragment/{doc_id}
   ```

---

**Maintainer:** Your Name  
**Last Updated:** 2024-12-09  
**Version:** 3.0
