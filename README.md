# 📁 File Resizer Application (Python GUI)

A desktop application built with **Python** and **PyQt6** that allows users to resize **images (JPEG/PNG)** and **PDFs** to a specific target size in kilobytes (KB).

This tool ensures that files are compressed efficiently while retaining maximum quality.

---

## ✨ Features

* **Image Resizing**

  * Compresses and rescales images to reach a target KB size.
  * Supports optional aspect ratio locking.

* **PDF Resizing (Two-Pass Strategy)**

  * **Non-Destructive Pass:** Optimizes and compresses images within PDF documents.
  * **Destructive Fallback:** If the target size isn’t met, rasterizes pages into images and applies a **binary search** on JPEG quality (30–99) to find the best possible quality below the target size.

* **Asynchronous Processing**

  * Runs resizing tasks in a separate **QThread** to keep the GUI responsive.

---

## 🛠️ Prerequisites

* Python **3.8+**
* Recommended: Use a virtual environment to isolate dependencies

---

## 📦 Installation & Setup

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/file-resizer-project.git
   cd file-resizer-project
   ```

2. **Create a Virtual Environment (Recommended)**

   ```bash
   python -m venv venv
   ```

   Activate it:

   * Windows (Command Prompt):

     ```bash
     venv\Scripts\activate
     ```
   * macOS/Linux:

     ```bash
     source venv/bin/activate
     ```

3. **Install Dependencies**

   ```bash
   pip install PyQt6 Pillow PyMuPDF
   ```

---

## 📂 Project Structure

```
/file-resizer-project/
├── file_resizer_app.py     # Main GUI application
├── file_resizer_backend.py # Core resizing functions
└── README.md               # Project documentation
```

---

## 🚀 How to Run

1. Activate your virtual environment (if not already active).

2. Run the main application:

   ```bash
   python file_resizer_app.py
   ```

3. The GUI window will open.

   * Select a file type (**Image** or **PDF**)
   * Click **Browse Files** to load a file
   * Enter the **Target Size (KB)**
   * Click **Resize**
   * Once done, click **Download** to save the resized file

---

## 🔎 Core Resizing Logic (Technical Details)

### 🖼️ Image Resizing (`resize_image`)

* Starts at **JPEG quality 95**.
* If size is too large → reduce quality in steps of **5**.
* If quality drops below **60**, begins scaling down dimensions by **10% steps** until the target size is reached.

### 📑 PDF Resizing (`resize_pdf` / `_rasterize_to_target`)

* **Pass 1 – Optimization**:
  Compresses existing images and saves with `garbage=4, deflate=True, clean=True`.

* **Pass 2 – Rasterization with Binary Search**:

  * Converts each page into images (scale factor **0.8**).
  * Applies **binary search on JPEG quality (30–99)**.
  * Finds the **maximum quality** possible while staying below the target KB size.
