import os
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

CATEGORIES = ["In bạt", "Decal", "PP", "Khác"]
DB_PATH = "print_manager.db"


class FileDatabase:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.init_db()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    path TEXT NOT NULL UNIQUE,
                    size INTEGER DEFAULT 0,
                    modified_at TEXT NOT NULL,
                    notes TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def upsert_file(self, name, category, path, size, modified_at, notes="", status="active"):
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO files (name, category, path, size, modified_at, notes, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    name = excluded.name,
                    category = excluded.category,
                    size = excluded.size,
                    modified_at = excluded.modified_at,
                    notes = excluded.notes,
                    status = excluded.status
                """,
                (name, category, path, size, modified_at, notes, status),
            )

    def mark_deleted(self, path):
        with self.connect() as conn:
            conn.execute(
                "UPDATE files SET status = 'deleted' WHERE path = ?",
                (path,),
            )

    def fetch_all(self):
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM files ORDER BY category, name"
            ).fetchall()

    def log_alert(self, alert_type, message):
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO alerts (type, message) VALUES (?, ?)",
                (alert_type, message),
            )

    def fetch_alerts(self, limit=20):
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def reset_deleted(self):
        with self.connect() as conn:
            conn.execute(
                "UPDATE files SET status = 'active' WHERE status = 'deleted'"
            )


def format_size(size):
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    idx = 0
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1
    return f"{value:.1f} {units[idx]}" if idx else f"{int(value)} B"


class PrintFileManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🐱 Kitty Print Manager")
        self.root.geometry("1200x760")
        self.root.minsize(980, 620)

        self.db = FileDatabase()
        self.selected_folder = tk.StringVar(value="")
        self.auto_scan_var = tk.BooleanVar(value=True)
        self.scan_interval = 10000

        self.root.configure(bg="#fff3f8")
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Header.TLabel", background="#ffd1dc", foreground="#5c2a3d", font=("Segoe UI", 16, "bold"))
        self.style.configure("Pink.TButton", background="#ff8fb1", foreground="#fff", font=("Segoe UI", 10, "bold"))
        self.style.map("Pink.TButton", background=[("active", "#ff6f9d")])
        self.style.configure("Treeview", rowheight=28, font=("Segoe UI", 10))
        self.style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        self.build_ui()
        self.load_seed_data()
        self.refresh_table()
        self.refresh_alerts()
        self.schedule_auto_scan()

    def build_ui(self):
        container = tk.Frame(self.root, bg="#fff3f8", padx=18, pady=18)
        container.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(container, bg="#ffd9e8", padx=14, pady=14, bd=1, relief=tk.SOLID)
        header.pack(fill=tk.X)

        title = ttk.Label(header, text="🐱 Kitty Print Manager", style="Header.TLabel")
        title.pack(anchor="w")

        subtitle = tk.Label(
            header,
            text="Quản lý file in ấn • theo dõi thay đổi • cảnh báo khi xóa/sửa file",
            bg="#ffd9e8",
            fg="#5c2a3d",
            font=("Segoe UI", 11),
        )
        subtitle.pack(anchor="w", pady=(6, 0))

        toolbar = tk.Frame(container, bg="#fff3f8", pady=12)
        toolbar.pack(fill=tk.X)

        folder_label = tk.Label(toolbar, text="Folder cần rà soát:", bg="#fff3f8", fg="#5b2d45", font=("Segoe UI", 10, "bold"))
        folder_label.pack(side=tk.LEFT)

        folder_entry = tk.Entry(toolbar, textvariable=self.selected_folder, width=52, font=("Segoe UI", 10))
        folder_entry.pack(side=tk.LEFT, padx=(8, 10))

        browse_btn = ttk.Button(toolbar, text="Chọn folder", command=self.choose_folder, style="Pink.TButton")
        browse_btn.pack(side=tk.LEFT, padx=(0, 8))

        scan_btn = ttk.Button(toolbar, text="Quét ngay", command=self.scan_selected_folder, style="Pink.TButton")
        scan_btn.pack(side=tk.LEFT, padx=(0, 8))

        add_demo_btn = ttk.Button(toolbar, text="Thêm file mẫu", command=self.add_demo_file, style="Pink.TButton")
        add_demo_btn.pack(side=tk.LEFT)

        auto_check = tk.Checkbutton(
            toolbar,
            text="Tự rà soát",
            variable=self.auto_scan_var,
            bg="#fff3f8",
            fg="#5b2d45",
            font=("Segoe UI", 10, "bold"),
            selectcolor="#ffd1dc",
        )
        auto_check.pack(side=tk.RIGHT, padx=(8, 0))

        main_area = tk.Frame(container, bg="#fff3f8")
        main_area.pack(fill=tk.BOTH, expand=True)

        left_panel = tk.Frame(main_area, bg="#fff3f8")
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        table_title = tk.Label(left_panel, text="Danh sách file", bg="#fff3f8", fg="#5b2d45", font=("Segoe UI", 12, "bold"))
        table_title.pack(anchor="w", pady=(0, 8))

        columns = ("name", "category", "path", "size", "modified", "status")
        self.tree = ttk.Treeview(left_panel, columns=columns, show="headings", height=18)
        self.tree.heading("name", text="Tên file")
        self.tree.heading("category", text="Hạng mục")
        self.tree.heading("path", text="Đường dẫn")
        self.tree.heading("size", text="Kích thước")
        self.tree.heading("modified", text="Cập nhật")
        self.tree.heading("status", text="Trạng thái")

        self.tree.column("name", width=180, anchor="w")
        self.tree.column("category", width=120, anchor="center")
        self.tree.column("path", width=420, anchor="w")
        self.tree.column("size", width=110, anchor="center")
        self.tree.column("modified", width=170, anchor="center")
        self.tree.column("status", width=120, anchor="center")

        self.tree.pack(fill=tk.BOTH, expand=True)

        right_panel = tk.Frame(main_area, width=320, bg="#fff3f8")
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))

        alert_title = tk.Label(right_panel, text="Thông báo mới", bg="#fff3f8", fg="#5b2d45", font=("Segoe UI", 12, "bold"))
        alert_title.pack(anchor="w", pady=(8, 6))

        self.alert_box = tk.Text(right_panel, height=15, wrap=tk.WORD, bg="#fffafc", fg="#5c2a3d", padx=8, pady=8, font=("Segoe UI", 10))
        self.alert_box.pack(fill=tk.BOTH, expand=True)
        self.alert_box.config(state=tk.DISABLED)

        footer = tk.Frame(container, bg="#fff3f8", pady=(14, 0))
        footer.pack(fill=tk.X)

        self.status_var = tk.StringVar(value="Sẵn sàng")
        status_bar = tk.Label(footer, textvariable=self.status_var, bg="#ffe0eb", fg="#5c2a3d", anchor="w", padx=12, pady=8, font=("Segoe UI", 10, "bold"))
        status_bar.pack(fill=tk.X)

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Chọn folder để rà soát")
        if folder:
            self.selected_folder.set(folder)
            self.status_var.set(f"Đã chọn folder: {folder}")

    def add_demo_file(self):
        demo_files = [
            ("Bạt-Bien-Hoa-01.pdf", "In bạt", "D:/demo/in_bat/Bạt-Bien-Hoa-01.pdf", "Mẫu file in bạt"),
            ("Decal-tường-02.png", "Decal", "D:/demo/decal/Decal-tường-02.png", "Mẫu decal"),
            ("PP-Hotline-03.ai", "PP", "D:/demo/pp/PP-Hotline-03.ai", "Mẫu file PP"),
        ]
        for name, category, path, notes in demo_files:
            size = 1024 + len(name) * 12
            modified = datetime.now().isoformat(timespec="seconds")
            self.db.upsert_file(name, category, path, size, modified, notes)
        self.db.log_alert("info", "Đã thêm các file mẫu để test chức năng quản lý.")
        self.status_var.set("Đã thêm file mẫu demo")
        self.refresh_table()
        self.refresh_alerts()

    def load_seed_data(self):
        rows = self.db.fetch_all()
        if rows:
            return
        sample_rows = [
            ("Bạt-cửa-hàng-01.pdf", "In bạt", "C:/PrintFiles/InBạt/Bạt-cửa-hàng-01.pdf", 95000, datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "Mẫu file sản phẩm"),
            ("Decal-cửa-rẻ-01.png", "Decal", "C:/PrintFiles/Decal/Decal-cửa-rẻ-01.png", 320000, datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "File decal"),
            ("PP-landing-01.ai", "PP", "C:/PrintFiles/PP/PP-landing-01.ai", 540000, datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "File PP"),
        ]
        for name, category, path, size, modified, notes in sample_rows:
            self.db.upsert_file(name, category, path, size, modified, notes)

    def refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        rows = self.db.fetch_all()
        if not rows:
            self.status_var.set("Chưa có file nào trong hệ thống")
            return

        for row in rows:
            status = row["status"]
            display_status = "Normal" if status == "active" else "Đã xóa/không còn tồn tại"
            self.tree.insert(
                "",
                tk.END,
                values=(
                    row["name"],
                    row["category"],
                    row["path"],
                    format_size(row["size"]),
                    row["modified_at"],
                    display_status,
                ),
            )

    def refresh_alerts(self):
        self.alert_box.config(state=tk.NORMAL)
        self.alert_box.delete("1.0", tk.END)
        alerts = self.db.fetch_alerts(limit=20)
        if not alerts:
            self.alert_box.insert(tk.END, "Không có cảnh báo nào.\n")
        else:
            for item in alerts:
                ts = item["created_at"]
                self.alert_box.insert(tk.END, f"[{ts}] {item['type']}\n{item['message']}\n\n")
        self.alert_box.config(state=tk.DISABLED)

    def scan_selected_folder(self):
        folder = self.selected_folder.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("Folder không hợp lệ", "Vui lòng chọn thư mục có thật để rà soát.")
            self.status_var.set("Folder chưa được chọn hợp lệ")
            return

        detected_new = 0
        detected_updated = 0
        detected_deleted = 0

        current_paths = {}
        for root, _, files in os.walk(folder):
            for file_name in files:
                file_path = os.path.abspath(os.path.join(root, file_name))
                try:
                    stat = os.stat(file_path)
                except OSError:
                    continue
                current_paths[file_path] = {
                    "name": file_name,
                    "category": self.guess_category(file_name),
                    "path": file_path,
                    "size": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%dT%H:%M:%S"),
                    "notes": "Tự động quét từ folder",
                }

        existing_rows = self.db.fetch_all()
        existing_by_path = {row["path"]: row for row in existing_rows}

        for path, meta in current_paths.items():
            if path not in existing_by_path:
                self.db.upsert_file(
                    meta["name"],
                    meta["category"],
                    meta["path"],
                    meta["size"],
                    meta["modified_at"],
                    meta["notes"],
                    "active",
                )
                self.db.log_alert("new", f"File mới phát hiện: {meta['name']} ({meta['category']})")
                detected_new += 1
            else:
                existing = existing_by_path[path]
                if existing["size"] != meta["size"] or existing["modified_at"] != meta["modified_at"]:
                    self.db.upsert_file(
                        meta["name"],
                        meta["category"],
                        meta["path"],
                        meta["size"],
                        meta["modified_at"],
                        meta["notes"],
                        "active",
                    )
                    self.db.log_alert("updated", f"File bị chỉnh sửa: {meta['name']} ({meta['category']})")
                    detected_updated += 1

        for path, row in existing_by_path.items():
            if path not in current_paths and row["status"] != "deleted":
                self.db.mark_deleted(path)
                self.db.log_alert("deleted", f"File bị xóa khỏi folder: {row['name']}")
                detected_deleted += 1

        self.refresh_table()
        self.refresh_alerts()

        if detected_new or detected_updated or detected_deleted:
            summary = []
            if detected_new:
                summary.append(f"mới: {detected_new}")
            if detected_updated:
                summary.append(f"sửa: {detected_updated}")
            if detected_deleted:
                summary.append(f"xóa: {detected_deleted}")
            messagebox.showinfo("Thông báo rà soát", "Phát hiện thay đổi: " + ", ".join(summary))
            self.status_var.set(f"Hoàn tất quét folder. {', '.join(summary)}")
        else:
            self.status_var.set("Quét xong. Không có thay đổi nào.")

    def guess_category(self, filename):
        name = filename.lower()
        if "bạt" in name or name.endswith((".pdf", ".ai", ".eps")) and "bat" in name:
            return "In bạt"
        if "decal" in name:
            return "Decal"
        if "pp" in name or "poly" in name:
            return "PP"
        return "Khác"

    def schedule_auto_scan(self):
        if self.auto_scan_var.get():
            self.scan_selected_folder()
        self.root.after(self.scan_interval, self.schedule_auto_scan)


if __name__ == "__main__":
    root = tk.Tk()
    app = PrintFileManagerApp(root)
    root.mainloop()

