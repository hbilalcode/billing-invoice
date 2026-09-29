# 💊 Asfandyar Medicos — Pharmacy POS System

A modern, offline desktop Point-of-Sale (POS) system built with **Python** and **PyQt6** for pharmacies and medical stores. It handles medicine inventory, invoicing, thermal receipt printing (80mm), customer records, and full sales history — all stored locally in an SQLite database.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/PyQt6-6.x-green?logo=qt&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-lightblue?logo=sqlite&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📋 Table of Contents

- [Features](#-features)
- [Screenshots](#-screenshots)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Running the App](#-running-the-app)
- [Building a Standalone `.exe`](#-building-a-standalone-exe)
- [Custom Logo / Icon](#-custom-logo--icon)
- [Project Structure](#-project-structure)
- [Database Schema](#-database-schema)
- [Usage Guide](#-usage-guide)
- [Troubleshooting](#-troubleshooting)
- [Backup & Data Safety](#-backup--data-safety)
- [License](#-license)
- [Author](#-author)

---

## ✨ Features

- 🧾 **Fast Invoicing** — Search medicines, add to cart, print thermal receipts (80mm)
- 💰 **Editable Prices & Quantities** — Override price per invoice, adjust qty inline
- 📦 **Inventory Management** — Add, edit, delete, bulk-delete, and export CSV
- 🔍 **Live Search** — Instant medicine lookup with stock & price preview
- 🕓 **Invoice History** — View, edit, reprint, or delete past invoices (auto-restores stock on delete)
- 📊 **Dashboard** — Today's sales, invoice count, low-stock alerts, total medicines
- 🖨️ **Thermal Printing** — Optimized for 80mm thermal printers (also prints to A4/PDF)
- 🏷️ **Category Abbreviations** — Tab, Cap, Syp, Inj for compact receipts
- 💾 **100% Offline** — No internet required, all data in a local SQLite file
- 🎨 **Modern UI** — Clean, professional interface with a sidebar navigation

---


---

## 🧰 Requirements

- **Python** 3.10 or higher ([Download](https://www.python.org/downloads/))
- **PyQt6** (installed via pip)
- **PyInstaller** (only for building the `.exe`)
- **Windows 10/11** (tested), Linux/macOS also supported with minor changes

---

## 🚀 Installation

### 1. Clone or Download the Repository

```bash
git clone https://github.com/YOUR_USERNAME/asfandyar-medicos-pos.git
cd asfandyar-medicos-pos
