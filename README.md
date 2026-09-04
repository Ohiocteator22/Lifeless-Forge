# ⚙️ Lifeless-Forge

**Lifeless-Forge** is a powerful, cross‑platform compression toolkit that creates **highly compressed archives** from repetitive data patterns.  
It supports **ZIP, PPTX, DOCX, and XLSX** formats, **batch generation**, **password protection** (AES‑256 or legacy ZipCrypto), and comes with both a **CLI** and a **Tkinter GUI**.

Perfect for:
- Testing storage capacity / mail server attachment limits
- Demonstrating compression ratios (up to 1000× or more)
- Generating realistic Office documents for testing
- Benchmarking decompression performance

![Demo](https://via.placeholder.com/800x400?text=Lifeless-Forge+in+action)

---

## ✨ Features

- **Multiple Output Formats** – ZIP (standard), PPTX, DOCX, XLSX (all openable in Office / LibreOffice)
- **Compression Control** – DEFLATE (default) or STORE (no compression)
- **Password Protection** – AES‑256 (secure) or legacy ZipCrypto (Windows native)
- **Batch Generation** – from a simple comma‑separated list or a full JSON configuration
- **Extraction** – Extract password‑protected archives (AES & legacy) with the same tool
- **Cross‑Platform** – Windows, macOS, Linux (CLI and GUI)
- **Progress Feedback** – Progress bars in both CLI (using `tqdm`) and GUI
- **Lightweight** – Single Python script, no heavy dependencies (optional `pyzipper` for encryption)

---

## 🚀 Installation

### From Source

```bash
git clone https://github.com/Ohiocteator22/Lifeless-Forge.git
cd Lifeless-Forge
```
## 📥 Download & Run

### For Windows Users (no Python required!)
1. Go to the [Releases](https://github.com/yourusername/Lifeless-Forge/releases) page.
2. Download `Forge.exe`.
3. Double‑click to launch the GUI, or run it from the command line:
   ```cmd
   Forge.exe generate -s 100 -o demo.pptx --format pptx
