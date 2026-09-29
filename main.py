import sys
import os
import sqlite3
import datetime
import csv
import logging
import traceback
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QMessageBox, QDialog, QFormLayout, QSpinBox, QFrame,
    QHeaderView, QFileDialog, QStackedWidget, QTextEdit, QAbstractItemView,
    QListWidget, QListWidgetItem, QDateEdit, QTimeEdit, QScrollArea
)
from PyQt6.QtCore import Qt, QDate, QTime, QSizeF, QMarginsF, QEvent, QTimer
from PyQt6.QtGui import QFont, QTextDocument, QPageSize, QPageLayout, QColor, QIcon
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

DB_NAME = "pharmacy_pos.db"

CATEGORY_ABBR = {
    "Tablet": "Tab",
    "Capsule": "Cap",
    "Syrup": "Syp",
    "Injection": "Inj",
    "Other": "Oth"
}

# Result code for InvoiceDialog "Edit" action
EDIT_RESULT = 2


def cat_abbr(cat):
    if not cat:
        return ""
    return CATEGORY_ABBR.get(cat, cat[:3])


# ---------- Logging ----------
def _log_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


LOG_PATH = os.path.join(_log_dir(), "pharmacy_pos.log")
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)


def log_exc(context=""):
    logging.error("%s\n%s", context, traceback.format_exc())


# ---------- Resource Path Helper (for PyInstaller) ----------
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ---------- Database ----------
def get_db_path():
    if getattr(sys, 'frozen', False):
        db_dir = os.path.dirname(sys.executable)
    else:
        db_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(db_dir, DB_NAME)


def get_connection():
    """Centralized connection with foreign keys enforced."""
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS medicines (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        category TEXT, price INTEGER NOT NULL, stock INTEGER NOT NULL,
        active INTEGER NOT NULL DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT UNIQUE,
        customer_name TEXT, date TEXT, time TEXT, subtotal INTEGER,
        discount INTEGER, grand_total INTEGER, cash_paid INTEGER, change_amount INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS invoice_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_id INTEGER,
        medicine_name TEXT, qty INTEGER, price INTEGER, amount INTEGER,
        category TEXT,
        FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE)''')
    conn.commit()

    # Migrations for older DBs
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(invoice_items)")
    cols = [row[1] for row in cur.fetchall()]
    if "category" not in cols:
        cur.execute("ALTER TABLE invoice_items ADD COLUMN category TEXT")
    cur.execute("PRAGMA table_info(medicines)")
    mcols = [row[1] for row in cur.fetchall()]
    if "active" not in mcols:
        cur.execute("ALTER TABLE medicines ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
    conn.commit()
    conn.close()


def next_receipt_no(cur):
    """Generate a unique receipt number, even within same second."""
    base = datetime.datetime.now().strftime('%y%m%d%H%M%S%f')  # includes microseconds
    rno = f"INV-{base}"
    # Safety check against collision (extremely unlikely with microseconds)
    for _ in range(5):
        cur.execute("SELECT 1 FROM invoices WHERE receipt_no=?", (rno,))
        if cur.fetchone() is None:
            return rno
        rno = f"INV-{datetime.datetime.now().strftime('%y%m%d%H%M%S%f')}"
    # Fallback
    return f"INV-{datetime.datetime.now().strftime('%y%m%d%H%M%S')}-{os.getpid()}"


# ---------- Style ----------
STYLESHEET = """
QWidget {
    background-color: #F7F9FC;
    color: #2C3E50;
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 14px;
}
QFrame#Sidebar { background-color: #FFFFFF; border-right: 1px solid #E4E8EE; }
QLabel#Brand { font-size: 17px; font-weight: 700; color: #1B2A41; }
QLabel#BrandSub { font-size: 11px; color: #94A3B8; }
QPushButton#SideBtn {
    background-color: transparent; color: #475569; text-align: left;
    padding: 12px 20px; border: none; border-radius: 8px;
    font-size: 14px; font-weight: 500;
}
QPushButton#SideBtn:hover { background-color: #EEF2F7; color: #1B2A41; }
QPushButton#SideBtn[active="true"] { background-color: #EEF2F7; color: #1B2A41; font-weight: 600; }
QLabel#PageTitle { font-size: 22px; font-weight: 700; color: #1B2A41; }
QLabel#PageSub { font-size: 13px; color: #94A3B8; }
QLabel#SectionLabel { color: #64748B; font-size: 12px; font-weight: 600; }
QLabel#StatValue { font-size: 28px; font-weight: 700; color: #1B2A41; }
QLabel#StatTitle { color: #64748B; font-size: 12px; font-weight: 600; }
QFrame#Panel, QFrame#StatCard { background-color: #FFFFFF; border: 1px solid #E4E8EE; border-radius: 10px; }
QLineEdit, QComboBox, QSpinBox, QDateEdit, QTimeEdit {
    padding: 10px 12px; border: 1px solid #D6DEE7; border-radius: 6px;
    background-color: #FFFFFF; font-size: 14px; color: #2C3E50;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
QDateEdit:focus, QTimeEdit:focus { border: 1px solid #3B82F6; }
QPushButton {
    background-color: #3B82F6; color: white; border: none;
    padding: 10px 18px; border-radius: 6px; font-size: 14px; font-weight: 500;
}
QPushButton:hover { background-color: #2563EB; }
QPushButton#Success { background-color: #10B981; }
QPushButton#Success:hover { background-color: #059669; }
QPushButton#Warning { background-color: #F59E0B; }
QPushButton#Warning:hover { background-color: #D97706; }
QPushButton#Danger { background-color: #EF4444; }
QPushButton#Danger:hover { background-color: #DC2626; }
QPushButton#Neutral { background-color: #94A3B8; }
QPushButton#Neutral:hover { background-color: #64748B; }
QTableWidget {
    background-color: #FFFFFF; alternate-background-color: #FBFCFE;
    border: 1px solid #E4E8EE; border-radius: 8px;
    gridline-color: transparent; font-size: 13px;
    selection-background-color: #DBEAFE; selection-color: #1B2A41;
}
QTableWidget::item { padding: 8px 10px; border: none; }
QHeaderView::section {
    background-color: #F7F9FC; color: #64748B;
    padding: 10px 8px; border: none; border-bottom: 1px solid #E4E8EE;
    font-size: 11px; font-weight: 600;
}
QTextEdit {
    background-color: #FFFFFF; border: 1px solid #E4E8EE; border-radius: 8px;
    padding: 16px; font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px; color: #1B2A41;
}
QListWidget {
    background-color: #FFFFFF; border: 1px solid #D6DEE7; border-radius: 6px;
    padding: 4px; font-size: 13px; outline: none;
}
QListWidget::item { padding: 8px 10px; border-radius: 4px; }
QListWidget::item:hover { background-color: #EEF2F7; }
QListWidget::item:selected { background-color: #DBEAFE; color: #1B2A41; }
QScrollBar:vertical { border: none; background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: #CBD5E1; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #94A3B8; }
QStatusBar {
    background-color: #FFFFFF; color: #64748B;
    border-top: 1px solid #E4E8EE; padding-left: 12px;
}
"""


# ---------- Medicine Dialog ----------
class MedicineDialog(QDialog):
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.data = data  # either None (add) or dict (edit)
        self.setWindowTitle("Edit Medicine" if data else "Add Medicine")
        self.setFixedSize(420, 400)
        self.setStyleSheet("QDialog { background-color: #FFFFFF; }")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(14)

        title = QLabel("Edit Medicine" if self.data else "Add New Medicine")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #1B2A41;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Panadol 500mg")
        self.cat_input = QComboBox()
        self.cat_input.addItems(["Tablet", "Syrup", "Injection", "Capsule", "Other"])
        # Allow price=0 explicitly for free samples. Validation done on save.
        self.price_input = QSpinBox()
        self.price_input.setRange(0, 9999999)
        self.price_input.setSpecialValueText(" ")
        self.stock_input = QSpinBox()
        self.stock_input.setRange(0, 999999)
        form.addRow("Name", self.name_input)
        form.addRow("Category", self.cat_input)
        form.addRow("Price", self.price_input)
        form.addRow("Stock", self.stock_input)
        layout.addLayout(form)

        if self.data:
            self.name_input.setText(self.data.get("name", ""))
            self.cat_input.setCurrentText(self.data.get("category") or "Tablet")
            self.price_input.setValue(int(self.data.get("price", 0)))
            self.stock_input.setValue(int(self.data.get("stock", 0)))

        layout.addStretch()
        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("Neutral")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("Success")
        save.clicked.connect(self.save_data)
        btns.addStretch()
        btns.addWidget(cancel)
        btns.addWidget(save)
        layout.addLayout(btns)

    def save_data(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Medicine name is required.")
            return
        price = int(self.price_input.value())
        stock = int(self.stock_input.value())
        category = self.cat_input.currentText()
        try:
            conn = get_connection()
            cur = conn.cursor()
            if self.data and self.data.get("id"):
                cur.execute(
                    "UPDATE medicines SET name=?, category=?, price=?, stock=? WHERE id=?",
                    (name, category, price, stock, self.data["id"]),
                )
            else:
                cur.execute(
                    "INSERT INTO medicines (name, category, price, stock, active) VALUES (?,?,?,?,1)",
                    (name, category, price, stock),
                )
            conn.commit()
            conn.close()
            self.accept()
        except Exception as e:
            log_exc("MedicineDialog.save_data")
            QMessageBox.critical(self, "Error", str(e))


# ---------- Price Edit Dialog ----------
class PriceEditDialog(QDialog):
    def __init__(self, parent, name, current_price):
        super().__init__(parent)
        self.setWindowTitle("Edit Price")
        self.setFixedSize(320, 200)
        self.setStyleSheet("QDialog { background-color: #FFFFFF; }")
        v = QVBoxLayout(self)
        v.setContentsMargins(25, 25, 25, 25)
        v.setSpacing(12)
        lbl = QLabel(f"New price for {name}")
        lbl.setStyleSheet("font-weight: 600; font-size: 14px;")
        v.addWidget(lbl)
        self.price_input = QSpinBox()
        self.price_input.setRange(0, 9999999)
        self.price_input.setValue(max(0, int(current_price)))
        self.price_input.setStyleSheet("font-size: 16px; padding: 10px;")
        v.addWidget(self.price_input)
        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("Neutral")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Update Price")
        ok.setObjectName("Success")
        ok.clicked.connect(self.accept)
        btns.addStretch()
        btns.addWidget(cancel)
        btns.addWidget(ok)
        v.addLayout(btns)

    def value(self):
        return int(self.price_input.value())


# ---------- Invoice Dialog (History) ----------
class InvoiceDialog(QDialog):
    def __init__(self, parent=None, invoice_id=None):
        super().__init__(parent)
        self.invoice_id = invoice_id
        self.inv = None
        self.items = []
        self.setWindowTitle(f"Invoice {invoice_id}")
        self.setFixedSize(760, 640)
        self.setStyleSheet("QDialog { background-color: #FFFFFF; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(14)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,))
        self.inv = cur.fetchone()
        cur.execute(
            "SELECT medicine_name, qty, price, amount, category FROM invoice_items WHERE invoice_id=?",
            (invoice_id,),
        )
        self.items = cur.fetchall()
        conn.close()

        if not self.inv:
            QMessageBox.critical(self, "Error", "Invoice not found.")
            self.reject()
            return

        header = QLabel(f"Invoice {self.inv[1]}")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #1B2A41;")
        layout.addWidget(header)

        info = QLabel(
            f"Customer: {self.inv[2] or 'Walk-in'}    Date: {self.inv[3]} {self.inv[4]}"
        )
        info.setStyleSheet("color: #94A3B8; font-size: 13px;")
        layout.addWidget(info)

        table = QTableWidget(len(self.items), 6)
        table.setHorizontalHeaderLabels(["S#", "Type", "Product", "Qty", "Price", "Amount"])
        th = table.horizontalHeader()
        th.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for i in [0, 1, 3, 4, 5]:
            th.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        for i, item in enumerate(self.items, 1):
            it_s = QTableWidgetItem(str(i))
            it_s.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_t = QTableWidgetItem(cat_abbr(item[4]))
            it_t.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_n = QTableWidgetItem(item[0])
            it_q = QTableWidgetItem(str(item[1]))
            it_q.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_p = QTableWidgetItem(f"{int(item[2])}")
            it_p.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            it_a = QTableWidgetItem(f"{int(item[3])}")
            it_a.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            table.setItem(i - 1, 0, it_s)
            table.setItem(i - 1, 1, it_t)
            table.setItem(i - 1, 2, it_n)
            table.setItem(i - 1, 3, it_q)
            table.setItem(i - 1, 4, it_p)
            table.setItem(i - 1, 5, it_a)
        layout.addWidget(table)

        totals = QLabel(
            f"Subtotal: Rs. {int(self.inv[5])}     Discount: Rs. {int(self.inv[6])}     "
            f"Grand Total: Rs. {int(self.inv[7])}     Change: Rs. {int(self.inv[9])}"
        )
        totals.setStyleSheet(
            "font-size: 13px; font-weight: 600; padding: 12px; "
            "background: #F7F9FC; border-radius: 6px; color: #1B2A41;"
        )
        layout.addWidget(totals)

        btns = QHBoxLayout()
        edit = QPushButton("Edit Invoice")
        edit.setObjectName("Warning")
        edit.clicked.connect(self._edit)
        reprint = QPushButton("Reprint")
        reprint.setObjectName("Success")
        reprint.clicked.connect(self._reprint)
        delete = QPushButton("Delete")
        delete.setObjectName("Danger")
        delete.clicked.connect(self._delete)
        close = QPushButton("Close")
        close.setObjectName("Neutral")
        close.clicked.connect(self.reject)
        btns.addWidget(edit)
        btns.addStretch()
        btns.addWidget(reprint)
        btns.addWidget(delete)
        btns.addWidget(close)
        layout.addLayout(btns)

    def _reprint(self):
        dlg = PrintPreviewDialog(self, self.inv, self.items)
        dlg.exec()

    def _edit(self):
        self.done(EDIT_RESULT)

    def _delete(self):
        if QMessageBox.question(
            self, "Delete", "Restore stock and delete this invoice?"
        ) == QMessageBox.StandardButton.Yes:
            try:
                conn = get_connection()
                cur = conn.cursor()
                for item in self.items:
                    cur.execute(
                        "UPDATE medicines SET stock = stock + ? WHERE name = ?",
                        (item[1], item[0]),
                    )
                # ON DELETE CASCADE now works because PRAGMA foreign_keys=ON
                cur.execute("DELETE FROM invoices WHERE id=?", (self.invoice_id,))
                conn.commit()
                conn.close()
                QMessageBox.information(
                    self, "Deleted", "Invoice deleted. Stock restored."
                )
                self.accept()
            except Exception as e:
                log_exc("InvoiceDialog._delete")
                QMessageBox.critical(self, "Error", str(e))


# ---------- Thermal Receipt Text ----------
def build_receipt_text(inv, items):
    # inv is a 10-tuple: (id, receipt_no, customer, date, time, subtotal, discount, grand, cash, change)
    rno, cust, date, time, subtotal, discount, grand, cash, change = (
        inv[1], inv[2], inv[3], inv[4], inv[5], inv[6], inv[7], inv[8], inv[9]
    )
    L = []
    L.append("        ASFANDYAR MEDICOS")
    L.append("        Chemist & Druggist")
    L.append("      BK&RK Hospital Batkhela")
    L.append("         LC/No # 227/RS")
    L.append("      Ph: +92-3449833266")
    L.append("=" * 42)
    L.append(f"RCPT: {rno}")
    L.append(f"DATE: {date} {time}")
    L.append(f"CUST: {cust}")
    L.append("=" * 42)
    L.append(f"{'S#':<3}{'T':<4}{'PRODUCT':<17}{'QTY':>4}{'PRICE':>6}{'AMT':>8}")
    L.append("-" * 42)
    if items:
        for i, it in enumerate(items, 1):
            name = it[0]
            qty = it[1]
            price = it[2]
            amount = it[3]
            cat = cat_abbr(it[4] if len(it) > 4 else "")
            if len(name) > 16:
                name = name[:15] + "."
            L.append(f"{i:<3}{cat:<4}{name:<17}{qty:>4}{int(price):>6}{int(amount):>8}")
    else:
        L.append("  (no items)")
    L.append("-" * 42)
    L.append(f"{'Subtotal:':<30}{('Rs.' + str(int(subtotal))):>12}")
    L.append(f"{'Discount:':<30}{('Rs.' + str(int(discount))):>12}")
    L.append("=" * 42)
    L.append(f"{'GRAND TOTAL:':<30}{('Rs.' + str(int(grand))):>12}")
    L.append("=" * 42)
    if int(cash) > 0:
        L.append(f"{'Cash:':<30}{('Rs.' + str(int(cash))):>12}")
        L.append(f"{'Change:':<30}{('Rs.' + str(int(change))):>12}")
    else:
        L.append(f"{'Cash:':<30}{'—':>12}")
        L.append(f"{'Change:':<30}{'—':>12}")
    L.append("=" * 42)
    L.append("      Thank you for your visit!")
    L.append("           Stay Healthy!")
    L.append("=" * 42)
    return "\n".join(L)


# ---------- Print Preview Dialog ----------
class PrintPreviewDialog(QDialog):
    def __init__(self, parent, inv, items):
        super().__init__(parent)
        self.inv = inv
        self.items = items
        self.setWindowTitle("Invoice Print Preview")
        self.setMinimumSize(620, 780)
        self.setStyleSheet("QDialog { background-color: #F4F4F4; }")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        top_bar = QFrame()
        top_bar.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border: 1px solid #DDDDDD; border-radius: 8px; }"
        )
        tb = QHBoxLayout(top_bar)
        tb.setContentsMargins(14, 10, 14, 10)
        tb.setSpacing(10)

        title = QLabel("Invoice Print Preview")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #000000; border: none;")
        tb.addWidget(title)
        tb.addStretch()

        print_btn = QPushButton("Print / Save")
        print_btn.setMinimumHeight(40)
        print_btn.setStyleSheet(
            "background-color: #10B981; color: white; "
            "font-size: 13px; font-weight: 700; "
            "border-radius: 8px; padding: 8px 20px;"
        )
        print_btn.clicked.connect(self._print)
        tb.addWidget(print_btn)

        close_btn = QPushButton("Close")
        close_btn.setMinimumHeight(40)
        close_btn.setStyleSheet(
            "background-color: #94A3B8; color: white; "
            "font-size: 13px; font-weight: 700; "
            "border-radius: 8px; padding: 8px 18px;"
        )
        close_btn.clicked.connect(self.reject)
        tb.addWidget(close_btn)

        outer.addWidget(top_bar)

        self.receipt_text = build_receipt_text(inv, items)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #BBBBBB; background: #DDDDDD; }")

        paper = QFrame()
        paper.setStyleSheet("background-color: #FFFFFF; border: none;")
        pl = QVBoxLayout(paper)
        pl.setContentsMargins(25, 25, 25, 25)
        pl.setSpacing(0)

        display_html = self._html_preview_from_receipt(self.receipt_text)
        label = QLabel(display_html)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setStyleSheet(
            "font-family: 'Courier New', monospace; font-size: 12px; color: #000000; "
            "background-color: #FFFFFF; padding: 0px;"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        pl.addWidget(label)

        scroll.setWidget(paper)
        outer.addWidget(scroll, 1)

    def _html_preview_from_receipt(self, receipt_text):
        lines = receipt_text.split("\n")
        out = []
        for ln in lines:
            stripped = ln.strip()
            if (
                stripped.startswith("ASFANDYAR MEDICOS")
                or stripped == "Chemist & Druggist"
                or stripped.startswith("GRAND TOTAL")
                or stripped.startswith("S#")
                or stripped.startswith("RCPT:")
                or stripped.startswith("DATE:")
                or stripped.startswith("CUST:")
            ):
                escaped = (
                    ln.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                )
                out.append(f"<b>{escaped}</b>")
            else:
                escaped = (
                    ln.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                )
                out.append(escaped)
        return "<br>".join(l.replace(" ", "&nbsp;") for l in out)

    def _print(self):
        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            if not printer.isValid():
                QMessageBox.critical(
                    self,
                    "Print Error",
                    "No valid printer is available on this system.",
                )
                return
            page_size = QPageSize(
                QSizeF(80, 297),
                QPageSize.Unit.Millimeter,
                "Thermal80",
                QPageSize.SizeMatchPolicy.ExactMatch,
            )
            printer.setPageSize(page_size)
            printer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)

            doc = QTextDocument()
            doc.setDefaultFont(QFont("Courier New", 9))
            doc.setPlainText(self.receipt_text)

            dlg = QPrintDialog(printer, self)
            dlg.setWindowTitle("Select Printer")
            if dlg.exec() == QDialog.DialogCode.Accepted:
                doc.print(printer)
                QMessageBox.information(self, "Sent", "Invoice sent to printer.")
        except Exception as e:
            log_exc("PrintPreviewDialog._print")
            QMessageBox.critical(self, "Print Error", str(e))


# ---------- Search Input (Inline Results — Focus-Safe) ----------
class SearchInput(QWidget):
    """Inline search: results appear directly below the input in the same
    layout. The QLineEdit keeps keyboard focus so the user can type
    continuously without interruption."""

    def __init__(self, on_select_callback, parent=None):
        super().__init__(parent)
        self.on_select = on_select_callback
        self.results = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Type medicine name...")
        self.input.textChanged.connect(self.on_text_changed)
        self.input.returnPressed.connect(self.select_first)
        self.input.installEventFilter(self)
        layout.addWidget(self.input)

        self.results_list = QListWidget()
        self.results_list.setMaximumHeight(220)
        self.results_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.results_list.itemClicked.connect(self.on_item_clicked)
        self.results_list.hide()
        layout.addWidget(self.results_list)

    def eventFilter(self, obj, event):
        if obj is self.input and event.type() == QEvent.Type.FocusOut:
            QTimer.singleShot(150, self._maybe_hide_list)
        if obj is self.input and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.input.clear()
                self.results_list.hide()
                return True
        return super().eventFilter(obj, event)

    def _maybe_hide_list(self):
        if not self.results_list.underMouse():
            self.results_list.hide()

    def on_text_changed(self, text):
        text = text.strip()
        if not text:
            self.results_list.hide()
            return
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT id, name, price, stock, category FROM medicines "
                "WHERE active=1 AND name LIKE ? ORDER BY name LIMIT 10",
                (f"%{text}%",),
            )
            rows = cur.fetchall()
            conn.close()
        except Exception:
            log_exc("SearchInput.on_text_changed")
            rows = []
        self.results = rows
        self.results_list.clear()
        if not rows:
            self.results_list.hide()
            return
        for r in rows:
            abbr = cat_abbr(r[4])
            display = f"{r[1]}  ({abbr})    Rs. {int(r[2])}    Stock: {r[3]}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, r)
            self.results_list.addItem(item)
        self.results_list.show()
        # Keep focus on the input so typing continues
        self.input.setFocus()

    def select_first(self):
        if self.results:
            self.emit_selection(self.results[0])

    def on_item_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.emit_selection(data)

    def emit_selection(self, data):
        self.results_list.hide()
        self.input.clear()
        self.input.setFocus()
        self.on_select(data)


# =========================================================
# MAIN WINDOW
# =========================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Asfandyar Medicos")
        self.setMinimumSize(1180, 760)
        self.resize(1350, 850)
        self.setStyleSheet(STYLESHEET)
        self.cart = []
        self.editing_invoice_id = None

        icon_path = resource_path("logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setup_ui()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(16, 24, 16, 24)
        sb.setSpacing(6)
        brand = QLabel("Asfandyar Medicos")
        brand.setObjectName("Brand")
        sb.addWidget(brand)
        brand_sub = QLabel("Premium Pharmacy")
        brand_sub.setObjectName("BrandSub")
        sb.addWidget(brand_sub)
        sb.addSpacing(24)

        self.nav_btns = {}
        for key, label in [
            ("home", "Dashboard"),
            ("invoice", "New Invoice"),
            ("inventory", "Medicines"),
            ("history", "History"),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("SideBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self.show_page(k))
            sb.addWidget(btn)
            self.nav_btns[key] = btn
        sb.addStretch()
        exit_btn = QPushButton("Exit")
        exit_btn.setObjectName("SideBtn")
        exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exit_btn.clicked.connect(self.close)
        sb.addWidget(exit_btn)
        root.addWidget(sidebar)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.build_home())
        self.stack.addWidget(self.build_invoice_page())
        self.stack.addWidget(self.build_inventory_page())
        self.stack.addWidget(self.build_history_page())
        root.addWidget(self.stack, 1)

        self.status = self.statusBar()
        self.status.showMessage("Ready")
        self.show_page("home")

    def show_page(self, key):
        idx = {"home": 0, "invoice": 1, "inventory": 2, "history": 3}[key]
        self.stack.setCurrentIndex(idx)
        for k, btn in self.nav_btns.items():
            btn.setProperty("active", "true" if k == key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if key == "home":
            self.refresh_home()
        elif key == "inventory":
            self.load_inventory()
        elif key == "history":
            self.load_history()

    # =========================================================
    # HOME
    # =========================================================
    def build_home(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(20)
        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")
        sub = QLabel("Overview of your pharmacy performance")
        sub.setObjectName("PageSub")
        layout.addWidget(title)
        layout.addWidget(sub)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)
        self.card_sales = self._make_stat_card("Today's Sales", "Rs. 0")
        self.card_invoices = self._make_stat_card("Invoices Today", "0")
        self.card_low = self._make_stat_card("Low Stock Items", "0")
        self.card_total_meds = self._make_stat_card("Total Medicines", "0")
        for c in [self.card_sales, self.card_invoices, self.card_low, self.card_total_meds]:
            cards_row.addWidget(c)
        layout.addLayout(cards_row)

        qa_label = QLabel("Quick Actions")
        qa_label.setObjectName("SectionLabel")
        layout.addWidget(qa_label)
        qa_row = QHBoxLayout()
        qa_row.setSpacing(12)
        new_inv = QPushButton("New Invoice")
        new_inv.setObjectName("Success")
        new_inv.setMinimumHeight(48)
        new_inv.setCursor(Qt.CursorShape.PointingHandCursor)
        new_inv.clicked.connect(lambda: self.show_page("invoice"))
        add_med = QPushButton("Add Medicine")
        add_med.setMinimumHeight(48)
        add_med.setCursor(Qt.CursorShape.PointingHandCursor)
        add_med.clicked.connect(self._quick_add_medicine)
        view_hist = QPushButton("View History")
        view_hist.setObjectName("Warning")
        view_hist.setMinimumHeight(48)
        view_hist.setCursor(Qt.CursorShape.PointingHandCursor)
        view_hist.clicked.connect(lambda: self.show_page("history"))
        qa_row.addWidget(new_inv)
        qa_row.addWidget(add_med)
        qa_row.addWidget(view_hist)
        layout.addLayout(qa_row)

        recent_label = QLabel("Recent Invoices")
        recent_label.setObjectName("SectionLabel")
        layout.addWidget(recent_label)
        self.recent_table = QTableWidget(0, 4)
        self.recent_table.setHorizontalHeaderLabels(["Receipt", "Customer", "Date", "Total"])
        self.recent_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.recent_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.doubleClicked.connect(lambda: self.show_page("history"))
        layout.addWidget(self.recent_table, 1)
        return page

    def _make_stat_card(self, title, value):
        card = QFrame()
        card.setObjectName("StatCard")
        card.setMinimumHeight(100)
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(6)
        t = QLabel(title)
        t.setObjectName("StatTitle")
        val = QLabel(value)
        val.setObjectName("StatValue")
        card.value_label = val
        v.addWidget(t)
        v.addWidget(val)
        v.addStretch()
        return card

    def _quick_add_medicine(self):
        dlg = MedicineDialog(self, None)
        if dlg.exec():
            self.refresh_home()
            self.status.showMessage("Medicine added", 3000)

    def refresh_home(self):
        try:
            conn = get_connection()
            cur = conn.cursor()
            today = datetime.date.today().strftime("%Y-%m-%d")
            cur.execute(
                "SELECT SUM(grand_total), COUNT(id) FROM invoices WHERE date=?",
                (today,),
            )
            res = cur.fetchone()
            sales = res[0] if res[0] else 0
            inv = res[1] if res[1] else 0
            cur.execute(
                "SELECT COUNT(id) FROM medicines WHERE active=1 AND stock < 10"
            )
            low = cur.fetchone()[0]
            cur.execute("SELECT COUNT(id) FROM medicines WHERE active=1")
            total_meds = cur.fetchone()[0]
            self.card_sales.value_label.setText(f"Rs. {int(sales)}")
            self.card_invoices.value_label.setText(str(inv))
            self.card_low.value_label.setText(str(low))
            self.card_total_meds.value_label.setText(str(total_meds))
            cur.execute(
                "SELECT receipt_no, customer_name, date, grand_total FROM invoices "
                "ORDER BY id DESC LIMIT 10"
            )
            rows = cur.fetchall()
            conn.close()
            self.recent_table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                self.recent_table.setItem(i, 0, QTableWidgetItem(r[0]))
                self.recent_table.setItem(i, 1, QTableWidgetItem(r[1] or "Walk-in"))
                self.recent_table.setItem(i, 2, QTableWidgetItem(r[2]))
                self.recent_table.setItem(i, 3, QTableWidgetItem(f"Rs. {int(r[3])}"))
        except Exception:
            log_exc("MainWindow.refresh_home")

    # =========================================================
    # INVOICE PAGE
    # =========================================================
    def build_invoice_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(16)

        header_row = QHBoxLayout()
        header_col = QVBoxLayout()
        self.invoice_title = QLabel("New Invoice")
        self.invoice_title.setObjectName("PageTitle")
        self.invoice_sub = QLabel(
            "Search medicines, adjust quantity or price, and print your invoice"
        )
        self.invoice_sub.setObjectName("PageSub")
        header_col.addWidget(self.invoice_title)
        header_col.addWidget(self.invoice_sub)
        header_row.addLayout(header_col)
        header_row.addStretch()
        self.cancel_edit_btn = QPushButton("Cancel Edit")
        self.cancel_edit_btn.setObjectName("Danger")
        self.cancel_edit_btn.clicked.connect(self.cancel_edit_mode)
        self.cancel_edit_btn.setVisible(False)
        header_row.addWidget(self.cancel_edit_btn)
        layout.addLayout(header_row)

        content = QHBoxLayout()
        content.setSpacing(16)

        # LEFT
        left = QFrame()
        left.setObjectName("Panel")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(20, 20, 20, 20)
        lv.setSpacing(12)
        lbl = QLabel("Search Medicine")
        lbl.setObjectName("SectionLabel")
        lv.addWidget(lbl)
        self.search_widget = SearchInput(self._add_from_search)
        lv.addWidget(self.search_widget)

        lbl2 = QLabel(
            "Cart — double-click Rate to edit price, double-click a row to edit quantity"
        )
        lbl2.setObjectName("SectionLabel")
        lv.addWidget(lbl2)

        self.cart_table = QTableWidget(0, 5)
        self.cart_table.setHorizontalHeaderLabels(
            ["Medicine", "Rate (Rs)", "Qty", "Amount (Rs)", ""]
        )
        hv = self.cart_table.horizontalHeader()
        hv.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in [1, 2, 3, 4]:
            hv.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        self.cart_table.setColumnWidth(1, 100)
        self.cart_table.setColumnWidth(2, 55)
        self.cart_table.setColumnWidth(3, 110)
        self.cart_table.setColumnWidth(4, 50)
        self.cart_table.verticalHeader().setVisible(False)
        self.cart_table.verticalHeader().setDefaultSectionSize(48)
        self.cart_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.cart_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.cart_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.cart_table.setShowGrid(False)
        self.cart_table.setAlternatingRowColors(True)
        self.cart_table.doubleClicked.connect(self._on_cart_double_click)
        self.cart_table.setStyleSheet("""
            QTableWidget { background-color: #FFFFFF; alternate-background-color: #FBFCFE;
                border: 1px solid #E4E8EE; border-radius: 8px; gridline-color: transparent;
                font-size: 13px; selection-background-color: #DBEAFE; selection-color: #1B2A41; }
            QTableWidget::item { padding: 6px 10px; border: none; }
            QHeaderView::section { background-color: #F7F9FC; color: #64748B;
                padding: 10px 8px; border: none; border-bottom: 1px solid #E4E8EE;
                font-size: 11px; font-weight: 600; }
        """)
        lv.addWidget(self.cart_table, 1)

        qty_row = QHBoxLayout()
        qty_row.setSpacing(8)
        b_plus = QPushButton("+ Quantity")
        b_plus.setObjectName("Success")
        b_plus.clicked.connect(self.increase_qty)
        b_minus = QPushButton("- Quantity")
        b_minus.setObjectName("Warning")
        b_minus.clicked.connect(self.decrease_qty)
        b_edit_price = QPushButton("Edit Price")
        b_edit_price.setObjectName("Warning")
        b_edit_price.clicked.connect(self.edit_price_selected)
        b_clear = QPushButton("Clear Cart")
        b_clear.setObjectName("Neutral")
        b_clear.clicked.connect(self.clear_cart)
        qty_row.addWidget(b_plus)
        qty_row.addWidget(b_minus)
        qty_row.addWidget(b_edit_price)
        qty_row.addStretch()
        qty_row.addWidget(b_clear)
        lv.addLayout(qty_row)
        content.addWidget(left, 3)

        # RIGHT
        right = QFrame()
        right.setObjectName("Panel")
        rv = QVBoxLayout(right)
        rv.setContentsMargins(20, 20, 20, 20)
        rv.setSpacing(12)
        lbl3 = QLabel("Thermal Preview (80mm)")
        lbl3.setObjectName("SectionLabel")
        rv.addWidget(lbl3)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        rv.addWidget(self.preview, 1)
        lbl4 = QLabel("Invoice Details")
        lbl4.setObjectName("SectionLabel")
        rv.addWidget(lbl4)

        form = QGridLayout()
        form.setSpacing(10)
        form.addWidget(QLabel("Customer"), 0, 0)
        self.customer_input = QLineEdit()
        self.customer_input.setPlaceholderText("Customer name")
        self.customer_input.textChanged.connect(self.update_preview)
        form.addWidget(self.customer_input, 0, 1)

        form.addWidget(QLabel("Invoice Date"), 0, 2)
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setDisplayFormat("dd-MMM-yyyy")
        self.date_input.dateChanged.connect(self.update_preview)
        form.addWidget(self.date_input, 0, 3)

        form.addWidget(QLabel("Time"), 1, 2)
        self.time_input = QTimeEdit()
        self.time_input.setTime(QTime.currentTime())
        self.time_input.setDisplayFormat("HH:mm")
        self.time_input.timeChanged.connect(self.update_preview)
        form.addWidget(self.time_input, 1, 3)

        form.addWidget(QLabel("Discount"), 1, 0)
        self.discount_input = QSpinBox()
        self.discount_input.setRange(0, 9999999)
        self.discount_input.setSpecialValueText(" ")
        self.discount_input.valueChanged.connect(self.update_preview)
        form.addWidget(self.discount_input, 1, 1)

        form.addWidget(QLabel("Cash Paid"), 2, 0)
        self.cash_input = QSpinBox()
        self.cash_input.setRange(0, 9999999)
        self.cash_input.setSpecialValueText(" ")
        self.cash_input.valueChanged.connect(self.update_preview)
        form.addWidget(self.cash_input, 2, 1)
        rv.addLayout(form)

        action_row = QHBoxLayout()
        self.print_save_btn = QPushButton("Print / Save Invoice")
        self.print_save_btn.setObjectName("Success")
        self.print_save_btn.setMinimumHeight(48)
        self.print_save_btn.setStyleSheet(
            "background-color: #10B981; color: white; "
            "font-size: 15px; font-weight: 600; border-radius: 8px;"
        )
        self.print_save_btn.clicked.connect(self.print_save_invoice)
        action_row.addWidget(self.print_save_btn)
        rv.addLayout(action_row)
        content.addWidget(right, 4)
        layout.addLayout(content)
        return page

    def _add_from_search(self, med_row):
        med_id, name, price, stock, category = med_row
        self.add_to_cart(med_id, name, int(price), stock, category)

    def _cart_has(self, med_id):
        for it in self.cart:
            if it["id"] == med_id:
                return it
        return None

    def add_to_cart(self, med_id, name, price, stock, category=""):
        # If editing an invoice, add back the qty already committed to this
        # invoice so the user can adjust up to original + current stock.
        if self.editing_invoice_id:
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute(
                    """SELECT ii.qty FROM invoice_items ii
                       WHERE ii.invoice_id=? AND ii.medicine_name=?""",
                    (self.editing_invoice_id, name),
                )
                row = cur.fetchone()
                conn.close()
                if row:
                    stock += row[0]
            except Exception:
                log_exc("MainWindow.add_to_cart (edit restore)")

        existing = self._cart_has(med_id)
        if existing:
            if existing["qty"] < stock:
                existing["qty"] += 1
                existing["amount"] = existing["qty"] * existing["price"]
            else:
                QMessageBox.warning(
                    self, "Stock", f"Only {stock} available."
                )
            self.refresh_cart()
            return

        self.cart.append({
            "id": med_id,
            "name": name,
            "price": int(price),
            "qty": 1,
            "amount": int(price),
            "stock": stock,
            "category": category or "",
        })
        self.refresh_cart()

    def refresh_cart(self):
        self.cart_table.setRowCount(len(self.cart))
        self.cart_table.verticalHeader().setDefaultSectionSize(48)
        for i, item in enumerate(self.cart):
            name_item = QTableWidgetItem(item["name"])
            name_item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            self.cart_table.setItem(i, 0, name_item)

            rate_item = QTableWidgetItem(f"{int(item['price'])}")
            rate_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.cart_table.setItem(i, 1, rate_item)

            qty_item = QTableWidgetItem(str(item["qty"]))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cart_table.setItem(i, 2, qty_item)

            amt_item = QTableWidgetItem(f"{int(item['amount'])}")
            amt_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            f = QFont()
            f.setBold(True)
            amt_item.setFont(f)
            self.cart_table.setItem(i, 3, amt_item)

            btn = QPushButton("✕")
            btn.setFixedSize(28, 28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton { background-color: #FEE2E2; color: #DC2626; font-weight: 700;
                    font-size: 14px; border-radius: 14px; border: none; padding: 0px; }
                QPushButton:hover { background-color: #EF4444; color: white; }
            """)
            btn.clicked.connect(lambda checked, it=item: self.remove_specific(it))
            self.cart_table.setCellWidget(i, 4, btn)
        self.update_preview()

    def _on_cart_double_click(self, index):
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self.cart):
            return
        item = self.cart[row]
        if col == 1:
            dlg = PriceEditDialog(self, item["name"], item["price"])
            if dlg.exec():
                item["price"] = dlg.value()
                item["amount"] = item["qty"] * item["price"]
                self.refresh_cart()
        else:
            self.edit_qty_dialog_for_row(row)

    def edit_price_selected(self):
        row = self.cart_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select", "Select an item first.")
            return
        item = self.cart[row]
        dlg = PriceEditDialog(self, item["name"], item["price"])
        if dlg.exec():
            item["price"] = dlg.value()
            item["amount"] = item["qty"] * item["price"]
            self.refresh_cart()

    def remove_specific(self, item):
        self.cart = [i for i in self.cart if i["id"] != item["id"]]
        self.refresh_cart()

    def increase_qty(self):
        row = self.cart_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select", "Select an item first.")
            return
        item = self.cart[row]
        if item["qty"] < item["stock"]:
            item["qty"] += 1
            item["amount"] = item["qty"] * item["price"]
        else:
            QMessageBox.warning(self, "Stock", f"Max {item['stock']}.")
        self.refresh_cart()

    def decrease_qty(self):
        row = self.cart_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select", "Select an item first.")
            return
        item = self.cart[row]
        if item["qty"] > 1:
            item["qty"] -= 1
            item["amount"] = item["qty"] * item["price"]
        else:
            self.cart.remove(item)
        self.refresh_cart()

    def edit_qty_dialog_for_row(self, row):
        if row < 0 or row >= len(self.cart):
            return
        item = self.cart[row]
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Quantity")
        dlg.setFixedSize(280, 170)
        dlg.setStyleSheet("QDialog { background-color: #FFFFFF; }")
        v = QVBoxLayout(dlg)
        lbl = QLabel(f"Quantity for {item['name']}")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-weight: 600;")
        v.addWidget(lbl)
        spin = QSpinBox()
        spin.setRange(0, item["stock"])
        spin.setValue(item["qty"])
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.setStyleSheet("font-size: 18px; padding: 8px;")
        v.addWidget(spin)
        ok = QPushButton("Update")
        ok.setObjectName("Success")
        ok.clicked.connect(dlg.accept)
        v.addWidget(ok)
        if dlg.exec():
            q = spin.value()
            if q == 0:
                self.cart.pop(row)
            else:
                item["qty"] = q
                item["amount"] = q * item["price"]
            self.refresh_cart()

    def clear_cart(self):
        if self.cart and QMessageBox.question(
            self, "Clear", "Remove all items?"
        ) == QMessageBox.StandardButton.Yes:
            self.cart.clear()
            self.discount_input.setValue(0)
            self.cash_input.setValue(0)
            self.customer_input.clear()
            self.date_input.setDate(QDate.currentDate())
            self.time_input.setTime(QTime.currentTime())
            self.refresh_cart()

    def _build_current_receipt_text(self):
        subtotal = sum(i["amount"] for i in self.cart)
        discount = self.discount_input.value()
        grand = subtotal - discount
        cash = self.cash_input.value()
        change = cash - grand if cash >= grand else 0
        rno = "PREVIEW"
        cust = self.customer_input.text().strip() or "Walk-in"
        date_str = self.date_input.date().toString("dd-MMM-yyyy")
        time_str = self.time_input.time().toString("HH:mm")
        items = [
            (it["name"], it["qty"], int(it["price"]), int(it["amount"]), it.get("category", ""))
            for it in self.cart
        ]
        inv_like = (
            0, rno, cust, date_str, time_str, int(subtotal), int(discount),
            int(grand), int(cash), int(change),
        )
        return build_receipt_text(inv_like, items)

    def update_preview(self):
        self.preview.setPlainText(self._build_current_receipt_text())

    def print_save_invoice(self):
        if not self.cart:
            QMessageBox.warning(self, "Empty", "Cart is empty.")
            return
        subtotal = sum(i["amount"] for i in self.cart)
        discount = self.discount_input.value()
        grand = subtotal - discount
        if grand < 0:
            QMessageBox.critical(self, "Error", "Discount cannot exceed subtotal.")
            return
        cash = self.cash_input.value() if self.cash_input.value() > 0 else grand
        if cash < grand:
            QMessageBox.critical(self, "Error", "Cash paid is less than total.")
            return
        cust = self.customer_input.text().strip() or "Walk-in Customer"
        date_str = self.date_input.date().toString("dd-MMM-yyyy")
        time_str = self.time_input.time().toString("HH:mm")
        try:
            conn = get_connection()
            cur = conn.cursor()

            if self.editing_invoice_id:
                # Restore old stock first
                cur.execute(
                    "SELECT medicine_name, qty FROM invoice_items WHERE invoice_id=?",
                    (self.editing_invoice_id,),
                )
                for name, qty in cur.fetchall():
                    cur.execute(
                        "UPDATE medicines SET stock = stock + ? WHERE name = ?",
                        (qty, name),
                    )
                cur.execute(
                    """UPDATE invoices SET customer_name=?, date=?, time=?,
                       subtotal=?, discount=?, grand_total=?, cash_paid=?, change_amount=?
                       WHERE id=?""",
                    (
                        cust, date_str, time_str, int(subtotal), int(discount),
                        int(grand), int(cash), int(cash - grand), self.editing_invoice_id,
                    ),
                )
                inv_id = self.editing_invoice_id
                cur.execute(
                    "DELETE FROM invoice_items WHERE invoice_id=?", (inv_id,)
                )
                for item in self.cart:
                    # Guarded decrement: never let stock go negative
                    cur.execute(
                        "UPDATE medicines SET stock = stock - ? WHERE id=? AND stock >= ?",
                        (item["qty"], item["id"], item["qty"]),
                    )
                    if cur.rowcount == 0:
                        raise ValueError(
                            f"Insufficient stock for '{item['name']}'. "
                            f"Another invoice may have consumed it."
                        )
                    cur.execute(
                        """INSERT INTO invoice_items
                           (invoice_id, medicine_name, qty, price, amount, category)
                           VALUES (?,?,?,?,?,?)""",
                        (
                            inv_id, item["name"], item["qty"],
                            int(item["price"]), int(item["amount"]),
                            item.get("category", ""),
                        ),
                    )
                conn.commit()
                conn.close()
            else:
                rno = next_receipt_no(cur)
                cur.execute(
                    """INSERT INTO invoices (receipt_no, customer_name, date, time,
                       subtotal, discount, grand_total, cash_paid, change_amount)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        rno, cust, date_str, time_str, int(subtotal), int(discount),
                        int(grand), int(cash), int(cash - grand),
                    ),
                )
                inv_id = cur.lastrowid
                for item in self.cart:
                    cur.execute(
                        "UPDATE medicines SET stock = stock - ? WHERE id=? AND stock >= ?",
                        (item["qty"], item["id"], item["qty"]),
                    )
                    if cur.rowcount == 0:
                        raise ValueError(
                            f"Insufficient stock for '{item['name']}'. "
                            f"Another invoice may have consumed it."
                        )
                    cur.execute(
                        """INSERT INTO invoice_items
                           (invoice_id, medicine_name, qty, price, amount, category)
                           VALUES (?,?,?,?,?,?)""",
                        (
                            inv_id, item["name"], item["qty"],
                            int(item["price"]), int(item["amount"]),
                            item.get("category", ""),
                        ),
                    )
                conn.commit()
                conn.close()

            # Reload saved invoice for preview
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM invoices WHERE id=?", (inv_id,))
            inv = cur.fetchone()
            cur.execute(
                "SELECT medicine_name, qty, price, amount, category "
                "FROM invoice_items WHERE invoice_id=?",
                (inv_id,),
            )
            items = cur.fetchall()
            conn.close()

            preview_dlg = PrintPreviewDialog(self, inv, items)
            preview_dlg.exec()
            self._reset_invoice_form()
        except Exception as e:
            log_exc("MainWindow.print_save_invoice")
            QMessageBox.critical(self, "Error", str(e))

    def _reset_invoice_form(self):
        self.cart = []
        self.refresh_cart()
        self.editing_invoice_id = None
        self.cancel_edit_btn.setVisible(False)
        self.customer_input.clear()
        self.discount_input.setValue(0)
        self.cash_input.setValue(0)
        self.date_input.setDate(QDate.currentDate())
        self.time_input.setTime(QTime.currentTime())
        self.invoice_title.setText("New Invoice")
        self.invoice_sub.setText(
            "Search medicines, adjust quantity or price, and print your invoice"
        )

    def load_invoice_for_edit(self, invoice_id):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,))
            inv = cur.fetchone()
            cur.execute(
                "SELECT medicine_name, qty, price, amount, category "
                "FROM invoice_items WHERE invoice_id=?",
                (invoice_id,),
            )
            items = cur.fetchall()

            if not inv:
                conn.close()
                return

            self.editing_invoice_id = invoice_id
            self.cart = []
            for name, qty, price, amount, category in items:
                cur.execute(
                    "SELECT id, stock, category FROM medicines WHERE name=? AND active=1",
                    (name,),
                )
                row = cur.fetchone()
                if row:
                    med_id, stock, med_cat = row
                else:
                    med_id, stock, med_cat = -1, qty, None
                stock = stock + qty  # allow re-adding original qty
                if not category and med_cat:
                    category = med_cat
                self.cart.append({
                    "id": med_id,
                    "name": name,
                    "price": int(price),
                    "qty": qty,
                    "amount": int(amount),
                    "stock": stock,
                    "category": category or "",
                })
            conn.close()

            self.customer_input.setText(inv[2] if inv[2] else "")
            try:
                d = datetime.datetime.strptime(inv[3], "%d-%b-%Y")
                self.date_input.setDate(QDate(d.year, d.month, d.day))
            except Exception:
                try:
                    d = datetime.datetime.strptime(inv[3], "%Y-%m-%d")
                    self.date_input.setDate(QDate(d.year, d.month, d.day))
                except Exception:
                    self.date_input.setDate(QDate.currentDate())
            try:
                t = datetime.datetime.strptime(inv[4], "%H:%M")
                self.time_input.setTime(QTime(t.hour, t.minute))
            except Exception:
                self.time_input.setTime(QTime.currentTime())
            self.discount_input.setValue(int(inv[6]))
            self.cash_input.setValue(int(inv[8]))
            self.refresh_cart()
            self.cancel_edit_btn.setVisible(True)
            self.invoice_title.setText(f"Editing Invoice {inv[1]}")
            self.invoice_sub.setText(
                "Edit items, prices, quantities, or customer info and click Print / Save to update"
            )
            self.show_page("invoice")
        except Exception:
            log_exc("MainWindow.load_invoice_for_edit")
            QMessageBox.critical(self, "Error", "Failed to load invoice. See log for details.")

    def cancel_edit_mode(self):
        if QMessageBox.question(
            self, "Cancel", "Discard changes to this invoice?"
        ) == QMessageBox.StandardButton.Yes:
            self._reset_invoice_form()

    # =========================================================
    # INVENTORY PAGE
    # =========================================================
    def build_inventory_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(16)
        title = QLabel("Manage Medicines")
        title.setObjectName("PageTitle")
        sub = QLabel("Add, edit, delete, and export your medicine inventory")
        sub.setObjectName("PageSub")
        layout.addWidget(title)
        layout.addWidget(sub)

        toolbar = QFrame()
        toolbar.setObjectName("Panel")
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(16, 12, 16, 12)
        tl.setSpacing(10)
        self.inv_search = QLineEdit()
        self.inv_search.setPlaceholderText("Search medicine by name...")
        self.inv_search.setMinimumWidth(320)
        self.inv_search.textChanged.connect(self.load_inventory)
        tl.addWidget(self.inv_search)
        tl.addStretch()
        add_btn = QPushButton("Add Medicine")
        add_btn.setObjectName("Success")
        add_btn.clicked.connect(self.add_medicine)
        export_btn = QPushButton("Export CSV")
        export_btn.setObjectName("Warning")
        export_btn.clicked.connect(self.export_csv)
        bulk_btn = QPushButton("Delete Selected")
        bulk_btn.setObjectName("Danger")
        bulk_btn.clicked.connect(self.bulk_delete)
        tl.addWidget(add_btn)
        tl.addWidget(export_btn)
        tl.addWidget(bulk_btn)
        layout.addWidget(toolbar)

        self.inv_table = QTableWidget(0, 5)
        self.inv_table.setHorizontalHeaderLabels(
            ["ID", "Name", "Category", "Price (Rs)", "Stock"]
        )
        self.inv_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.inv_table.verticalHeader().setVisible(False)
        self.inv_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.inv_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.inv_table.setAlternatingRowColors(True)
        self.inv_table.doubleClicked.connect(self.edit_medicine)
        layout.addWidget(self.inv_table, 1)
        return page

    def load_inventory(self):
        self.inv_table.setRowCount(0)
        try:
            conn = get_connection()
            cur = conn.cursor()
            q = "SELECT id, name, category, price, stock FROM medicines WHERE active=1"
            p = []
            if self.inv_search.text().strip():
                q += " AND name LIKE ?"
                p.append(f"%{self.inv_search.text()}%")
            cur.execute(q + " ORDER BY name", p)
            rows = cur.fetchall()
            conn.close()
            self.inv_table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                self.inv_table.setItem(i, 0, QTableWidgetItem(str(r[0])))
                self.inv_table.setItem(i, 1, QTableWidgetItem(r[1]))
                self.inv_table.setItem(i, 2, QTableWidgetItem(r[2] or ""))
                self.inv_table.setItem(i, 3, QTableWidgetItem(f"{int(r[3])}"))
                self.inv_table.setItem(i, 4, QTableWidgetItem(str(r[4])))
        except Exception:
            log_exc("MainWindow.load_inventory")

    def add_medicine(self):
        dlg = MedicineDialog(self, None)
        if dlg.exec():
            self.load_inventory()
            self.status.showMessage("Medicine added", 3000)

    def edit_medicine(self):
        row = self.inv_table.currentRow()
        if row < 0:
            return
        med_id = int(self.inv_table.item(row, 0).text())
        # Re-query so we always have authoritative data
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT id, name, category, price, stock FROM medicines WHERE id=?",
                (med_id,),
            )
            row_data = cur.fetchone()
            conn.close()
        except Exception:
            log_exc("MainWindow.edit_medicine load")
            return
        if not row_data:
            QMessageBox.warning(self, "Not Found", "This medicine no longer exists.")
            self.load_inventory()
            return
        data = {
            "id": row_data[0],
            "name": row_data[1],
            "category": row_data[2],
            "price": row_data[3],
            "stock": row_data[4],
        }
        dlg = MedicineDialog(self, data)
        if dlg.exec():
            self.load_inventory()
            self.status.showMessage("Medicine updated", 3000)

    def bulk_delete(self):
        rows = set(idx.row() for idx in self.inv_table.selectedIndexes())
        if not rows:
            QMessageBox.information(self, "Info", "Select items first.")
            return
        # Warn if any of these have appeared in invoices
        med_ids = [int(self.inv_table.item(r, 0).text()) for r in rows]
        placeholders = ",".join("?" for _ in med_ids)
        used_names = set()
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                f"SELECT name FROM medicines WHERE id IN ({placeholders})", med_ids
            )
            names = [n[0] for n in cur.fetchall()]
            if names:
                nm_ph = ",".join("?" for _ in names)
                cur.execute(
                    f"SELECT DISTINCT medicine_name FROM invoice_items "
                    f"WHERE medicine_name IN ({nm_ph})",
                    names,
                )
                used_names = {r[0] for r in cur.fetchall()}
            conn.close()
        except Exception:
            log_exc("MainWindow.bulk_delete pre-check")

        msg = f"Delete {len(rows)} items?"
        if used_names:
            msg += (
                f"\n\n⚠ These have appeared in past invoices: "
                f"{', '.join(sorted(used_names))}"
                f"\nThey will be hidden from inventory but invoice history is preserved."
            )
        if QMessageBox.question(self, "Confirm", msg) != QMessageBox.StandardButton.Yes:
            return
        try:
            conn = get_connection()
            cur = conn.cursor()
            for mid in med_ids:
                # Soft delete: mark inactive so invoice history stays intact
                cur.execute("UPDATE medicines SET active=0 WHERE id=?", (mid,))
            conn.commit()
            conn.close()
            self.load_inventory()
            self.status.showMessage(f"Deactivated {len(med_ids)} items", 3000)
        except Exception:
            log_exc("MainWindow.bulk_delete")
            QMessageBox.critical(self, "Error", "Could not delete items. See log.")

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "medicines.csv", "CSV Files (*.csv)"
        )
        if path:
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, name, category, price, stock FROM medicines WHERE active=1"
                )
                rows = cur.fetchall()
                conn.close()
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["ID", "Name", "Category", "Price", "Stock"])
                    w.writerows(rows)
                QMessageBox.information(self, "Success", "Exported successfully.")
            except Exception as e:
                log_exc("MainWindow.export_csv")
                QMessageBox.critical(self, "Error", str(e))

    # =========================================================
    # HISTORY PAGE
    # =========================================================
    def build_history_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(16)
        title = QLabel("Invoice History")
        title.setObjectName("PageTitle")
        sub = QLabel("Search, view, edit, reprint, or delete past invoices")
        sub.setObjectName("PageSub")
        layout.addWidget(title)
        layout.addWidget(sub)

        toolbar = QFrame()
        toolbar.setObjectName("Panel")
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(16, 12, 16, 12)
        tl.setSpacing(10)
        self.hist_search = QLineEdit()
        self.hist_search.setPlaceholderText("Search by customer or receipt number...")
        self.hist_search.setMinimumWidth(360)
        self.hist_search.textChanged.connect(self.load_history)
        tl.addWidget(self.hist_search)
        tl.addStretch()
        manage_btn = QPushButton("View / Edit / Reprint / Delete")
        manage_btn.clicked.connect(self.open_invoice_dialog)
        tl.addWidget(manage_btn)
        layout.addWidget(toolbar)

        self.hist_table = QTableWidget(0, 6)
        self.hist_table.setHorizontalHeaderLabels(
            ["ID", "Receipt", "Customer", "Date", "Time", "Total"]
        )
        self.hist_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.hist_table.verticalHeader().setVisible(False)
        self.hist_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.hist_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.hist_table.setAlternatingRowColors(True)
        self.hist_table.doubleClicked.connect(self.open_invoice_dialog)
        layout.addWidget(self.hist_table, 1)
        return page

    def load_history(self):
        self.hist_table.setRowCount(0)
        try:
            conn = get_connection()
            cur = conn.cursor()
            q = (
                "SELECT id, receipt_no, customer_name, date, time, grand_total "
                "FROM invoices WHERE 1=1"
            )
            p = []
            if self.hist_search.text().strip():
                q += " AND (customer_name LIKE ? OR receipt_no LIKE ?)"
                p.extend(
                    [f"%{self.hist_search.text()}%", f"%{self.hist_search.text()}%"]
                )
            cur.execute(q + " ORDER BY id DESC", p)
            rows = cur.fetchall()
            conn.close()
            self.hist_table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                self.hist_table.setItem(i, 0, QTableWidgetItem(str(r[0])))
                self.hist_table.setItem(i, 1, QTableWidgetItem(r[1]))
                self.hist_table.setItem(i, 2, QTableWidgetItem(r[2] or "Walk-in"))
                self.hist_table.setItem(i, 3, QTableWidgetItem(r[3]))
                self.hist_table.setItem(i, 4, QTableWidgetItem(r[4]))
                self.hist_table.setItem(i, 5, QTableWidgetItem(f"Rs. {int(r[5])}"))
        except Exception:
            log_exc("MainWindow.load_history")

    def open_invoice_dialog(self):
        row = self.hist_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Info", "Select an invoice first.")
            return
        inv_id = self.hist_table.item(row, 0).text()
        dlg = InvoiceDialog(self, inv_id)
        result = dlg.exec()
        if result == EDIT_RESULT:
            self.load_invoice_for_edit(int(inv_id))
        if result:
            self.load_history()
            self.load_inventory()
            self.refresh_home()


# =========================================================
if __name__ == "__main__":
    init_db()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    icon_path = resource_path("logo.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
