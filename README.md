# Secure AI Document Assistant 🚀

A secure, multimodal AI-powered document and image assistant built with **Flask** and the **Google GenAI SDK**. This application allows users to upload text files, PDFs, and images, and query them safely with robust, enterprise-grade safety guardrails.

---

## 🛡️ Security & Content Safety Policy

This application incorporates multi-layered security filters to ensure ethical and safe usage:
* **Local Pre-screening:** Scans inputs locally using regex patterns to instantly block text involving illegal acts, fraud, self-harm, hate speech, explicit content, or child exploitation (CSAM).
* **Multimodal Safety:** Image and visual uploads are inspected via Gemini's native vision classifiers.
* **Strict Thresholds:** Configured with maximum-strictness safety settings (`BLOCK_LOW_AND_ABOVE`) and system instructions to firmly reject prohibited material.

> **Important Notice:** This tool is designed strictly for valid, legal document analysis. Any attempt to use this application for illegal activities is strictly prohibited.

---

## ⚙️ Tech Stack
* **Backend:** Python, Flask
* **AI Engine:** Google GenAI SDK (`gemini-3.8-flash`, `gemini-2.0-flash`, `gemini-1.5-flash`)
* **Parsing:** `PyPDF2`

---

## 📥 Installation & Setup

To run this project locally, you must provide **your own Gemini API key**. 

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/srinjoyghosh2004/AI-Document-Assistant.git](https://github.com/srinjoyghosh2004/AI-Document-Assistant.git)
   cd AI-Document-Assistant
