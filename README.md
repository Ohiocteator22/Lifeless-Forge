# ⚙️ Lifeless-Forge

**Lifeless-Forge** is a **cross‑platform compression/decompression toolkit** with both a **CLI** and a **modern Tkinter GUI**.  
It supports **DEFLATE (ZIP)**, **LZMA (XZ)**, **BROTLI (BR)**, ZL4, and **Zstandard** algorithms, can generate test data with custom patterns, compress real files/folders, handle **password protection** (AES‑256 or legacy ZipCrypto), and offers **batch processing** and **Windows Explorer integration**.

Perfect for:
- Testing storage limits & mail server attachment caps
- Demonstrating extreme compression ratios (up to 32,000× on repetitive data)
- Generating realistic Office documents (PPTX, DOCX, XLSX) for testing
- Benchmarking compression performance

---

## ✨ Features

- **Five compression algorithms** – DEFLATE (ZIP), LZMA (XZ), Zstandard (Zstd), Brotli (br), LZ4
- **Multiple output formats** – ZIP, PPTX, DOCX, XLSX, TAR, TAR.XZ, TAR.ZST, .br
- **Password protection** – AES‑256 (secure) or legacy ZipCrypto (Windows native)
- **Batch generation** – from comma‑separated sizes or JSON configuration
- **Universal extraction** – supports ZIP, XZ, Zstd, TAR, TAR.XZ, TAR.ZST, .br and Office formats
- **Real‑file/folder compression** – compress existing files while preserving folder structure
- **Pattern‑based test generation** – create large repetitive files with a single character
- **CLI & GUI** – full command‑line support plus a user‑friendly Tkinter interface
- **Dark/Light mode** – automatically follows system theme; user preference saved
- **Windows Explorer integration** – right‑click “Forge” submenu (ZIP, XZ, ZST, Extract)
- **Cross‑platform** – Windows, macOS, Linux (GUI requires a display)
- **Lightweight & modular** – no heavy dependencies (optional extras for encryption, Zstd, GUI, progress)

---

## 🚀 Installation

### From Source (Development)

```bash
git clone https://github.com/Ohiocteator22/Lifeless-Forge.git
cd Lifeless-Forge
python -m venv .venv
source .venv/bin/activate      # On Windows: .venv\Scripts\activate
pip install -e .                # installs core (no optional dependencies)
