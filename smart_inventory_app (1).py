import csv
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "inventory.db"
RECEIPT_DIR = APP_DIR / "receipts"


class InventoryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart Inventory & Order Management System")
        self.root.geometry("1100x700")
        self.root.minsize(900, 600)
        self.selected_product_id = None
        self.cart = []

        self.setup_style()
        self.setup_database()
        self.build_ui()
        self.refresh_all()

    def setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", padding=6)
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Metric.TLabel", font=("Segoe UI", 14, "bold"))

    def connect(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def setup_database(self):
        with self.connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    price REAL NOT NULL CHECK(price >= 0),
                    stock INTEGER NOT NULL CHECK(stock >= 0),
                    min_stock INTEGER NOT NULL DEFAULT 5 CHECK(min_stock >= 0),
                    sku TEXT NOT NULL DEFAULT '',
                    supplier TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sale_time TEXT NOT NULL,
                    subtotal REAL NOT NULL,
                    discount REAL NOT NULL,
                    tax REAL NOT NULL,
                    total REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sale_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sale_id INTEGER NOT NULL REFERENCES sales(id),
                    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
                    product_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price REAL NOT NULL,
                    line_total REAL NOT NULL
                );
            """)
            self.migrate_database_schema(con)

    def migrate_database_schema(self, con):
        product_columns = {row[1] for row in con.execute("PRAGMA table_info(products)").fetchall()}
        if "sku" not in product_columns:
            con.execute("ALTER TABLE products ADD COLUMN sku TEXT NOT NULL DEFAULT ''")
        if "supplier" not in product_columns:
            con.execute("ALTER TABLE products ADD COLUMN supplier TEXT NOT NULL DEFAULT ''")

    def build_ui(self):
        header = ttk.Frame(self.root, padding=(16, 12))
        header.pack(fill="x")
        ttk.Label(header, text="Smart Inventory", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Inventory • Orders • Reports").pack(side="right")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.dashboard_tab = ttk.Frame(self.notebook, padding=12)
        self.products_tab = ttk.Frame(self.notebook, padding=12)
        self.stock_tab = ttk.Frame(self.notebook, padding=12)
        self.checkout_tab = ttk.Frame(self.notebook, padding=12)
        self.reports_tab = ttk.Frame(self.notebook, padding=12)

        self.notebook.add(self.dashboard_tab, text="Dashboard")
        self.notebook.add(self.products_tab, text="Products")
        self.notebook.add(self.stock_tab, text="Stock Entry")
        self.notebook.add(self.checkout_tab, text="Checkout")
        self.notebook.add(self.reports_tab, text="Sales Reports")

        self.build_dashboard()
        self.build_products()
        self.build_stock()
        self.build_checkout()
        self.build_reports()

    def build_dashboard(self):
        ttk.Label(self.dashboard_tab, text="Overview", style="Title.TLabel").pack(anchor="w", pady=(0, 12))
        metrics = ttk.Frame(self.dashboard_tab)
        metrics.pack(fill="x", pady=(0, 16))
        self.metric_products = self.metric_card(metrics, "Products", 0)
        self.metric_sales = self.metric_card(metrics, "Today's sales", 1)
        self.metric_low = self.metric_card(metrics, "Low-stock items", 2)
        self.metric_value = self.metric_card(metrics, "Inventory value", 3)

        self.dashboard_summary = ttk.Label(self.dashboard_tab, text="", wraplength=900, justify="left")
        self.dashboard_summary.pack(anchor="w", pady=(0, 12))

        ttk.Label(self.dashboard_tab, text="Items needing attention", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.low_tree = self.make_tree(
            self.dashboard_tab,
            ("id", "name", "stock", "min_stock"),
            ("ID", "Product", "Current stock", "Minimum stock"),
            (70, 360, 150, 150)
        )
        ttk.Button(self.dashboard_tab, text="Refresh dashboard", command=self.refresh_all).pack(anchor="e", pady=10)

    def metric_card(self, parent, label, column):
        card = ttk.LabelFrame(parent, text=label, padding=16)
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
        parent.columnconfigure(column, weight=1)
        value = ttk.Label(card, text="0", style="Metric.TLabel")
        value.pack(anchor="w")
        return value

    def build_products(self):
        ttk.Label(self.products_tab, text="Product Management", style="Title.TLabel").pack(anchor="w", pady=(0, 10))

        form = ttk.LabelFrame(self.products_tab, text="Product details", padding=10)
        form.pack(fill="x", pady=(0, 10))
        self.p_name = tk.StringVar()
        self.p_category = tk.StringVar()
        self.p_price = tk.StringVar()
        self.p_stock = tk.StringVar()
        self.p_min = tk.StringVar(value="5")
        self.p_sku = tk.StringVar()
        self.p_supplier = tk.StringVar()

        fields = [
            ("Product name", self.p_name),
            ("Category", self.p_category),
            ("SKU", self.p_sku),
            ("Supplier", self.p_supplier),
            ("Unit price (₹)", self.p_price),
            ("Stock quantity", self.p_stock),
            ("Minimum stock", self.p_min),
        ]
        for col, (label, var) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=0, column=col, sticky="w", padx=5, pady=(0, 4))
            ttk.Entry(form, textvariable=var, width=19).grid(row=1, column=col, sticky="ew", padx=5)
            form.columnconfigure(col, weight=1)

        buttons = ttk.Frame(self.products_tab)
        buttons.pack(fill="x", pady=(0, 10))
        ttk.Button(buttons, text="Add product", command=self.add_product).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Update selected", command=self.update_product).pack(side="left", padx=6)
        ttk.Button(buttons, text="Delete selected", command=self.delete_product).pack(side="left", padx=6)
        ttk.Button(buttons, text="Clear form", command=self.clear_product_form).pack(side="left", padx=6)

        search_row = ttk.Frame(self.products_tab)
        search_row.pack(fill="x", pady=(0, 6))
        ttk.Label(search_row, text="Search:").pack(side="left")
        self.product_search = tk.StringVar()
        search_entry = ttk.Entry(search_row, textvariable=self.product_search, width=35)
        search_entry.pack(side="left", padx=8)
        search_entry.bind("<KeyRelease>", lambda _event: self.refresh_products())
        ttk.Label(search_row, text="Select a row to edit it.").pack(side="right")

        self.products_tree = self.make_tree(
            self.products_tab,
            ("id", "name", "category", "sku", "supplier", "price", "stock", "min_stock"),
            ("ID", "Product", "Category", "SKU", "Supplier", "Price (₹)", "Stock", "Minimum"),
            (55, 220, 150, 130, 170, 100, 80, 90)
        )
        self.products_tree.bind("<<TreeviewSelect>>", self.on_product_select)

    def build_stock(self):
        ttk.Label(self.stock_tab, text="Stock Entry", style="Title.TLabel").pack(anchor="w", pady=(0, 12))
        ttk.Label(
            self.stock_tab,
            text="Record stock received from a supplier. This increases the available quantity."
        ).pack(anchor="w", pady=(0, 16))

        form = ttk.LabelFrame(self.stock_tab, text="Restock product", padding=14)
        form.pack(fill="x", anchor="n")
        ttk.Label(form, text="Product").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.stock_product = tk.StringVar()
        self.stock_combo = ttk.Combobox(form, textvariable=self.stock_product, state="readonly", width=42)
        self.stock_combo.grid(row=1, column=0, padx=5, pady=5, sticky="w")

        ttk.Label(form, text="Quantity received").grid(row=0, column=1, sticky="w", padx=5, pady=5)
        self.stock_quantity = tk.StringVar()
        ttk.Entry(form, textvariable=self.stock_quantity, width=18).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(form, text="Add stock", command=self.add_stock).grid(row=1, column=2, padx=12, pady=5)

        ttk.Label(
            self.stock_tab,
            text="Tip: Customer purchases are recorded from the Checkout tab, where stock is reduced automatically.",
            wraplength=800
        ).pack(anchor="w", pady=18)

    def build_checkout(self):
        ttk.Label(self.checkout_tab, text="Checkout & Billing", style="Title.TLabel").pack(anchor="w", pady=(0, 10))
        top = ttk.Frame(self.checkout_tab)
        top.pack(fill="x", pady=(0, 8))

        ttk.Label(top, text="Product").grid(row=0, column=0, sticky="w")
        self.checkout_product = tk.StringVar()
        self.checkout_combo = ttk.Combobox(top, textvariable=self.checkout_product, state="readonly", width=42)
        self.checkout_combo.grid(row=1, column=0, padx=(0, 12), pady=4, sticky="w")

        ttk.Label(top, text="Quantity").grid(row=0, column=1, sticky="w")
        self.checkout_quantity = tk.StringVar(value="1")
        ttk.Entry(top, textvariable=self.checkout_quantity, width=10).grid(row=1, column=1, padx=(0, 12), pady=4)

        ttk.Button(top, text="Add to bill", command=self.add_to_cart).grid(row=1, column=2, padx=4)
        ttk.Button(top, text="Remove selected", command=self.remove_cart_item).grid(row=1, column=3, padx=4)

        self.cart_tree = self.make_tree(
            self.checkout_tab,
            ("id", "name", "quantity", "price", "total"),
            ("Product ID", "Product", "Quantity", "Unit price (₹)", "Line total (₹)"),
            (90, 330, 100, 150, 150)
        )
        self.cart_tree.pack(fill="both", expand=True, pady=(0, 10))

        totals = ttk.Frame(self.checkout_tab)
        totals.pack(fill="x")
        self.discount_var = tk.StringVar(value="0")
        self.tax_var = tk.StringVar(value="0")
        ttk.Label(totals, text="Discount (₹):").pack(side="left")
        discount_entry = ttk.Entry(totals, textvariable=self.discount_var, width=10)
        discount_entry.pack(side="left", padx=5)
        ttk.Label(totals, text="Tax (%):").pack(side="left", padx=(12, 0))
        tax_entry = ttk.Entry(totals, textvariable=self.tax_var, width=8)
        tax_entry.pack(side="left", padx=5)
        discount_entry.bind("<KeyRelease>", lambda _event: self.refresh_cart())
        tax_entry.bind("<KeyRelease>", lambda _event: self.refresh_cart())
        self.total_label = ttk.Label(totals, text="Total: ₹0.00", style="Metric.TLabel")
        self.total_label.pack(side="right", padx=10)
        ttk.Button(self.checkout_tab, text="Complete sale & save receipt", command=self.complete_sale).pack(anchor="e", pady=10)

    def build_reports(self):
        ttk.Label(self.reports_tab, text="Sales Reports", style="Title.TLabel").pack(anchor="w", pady=(0, 12))
        self.report_summary = ttk.Label(self.reports_tab, text="")
        self.report_summary.pack(anchor="w", pady=(0, 12))

        ttk.Label(self.reports_tab, text="Recent sales", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.sales_tree = self.make_tree(
            self.reports_tab,
            ("id", "time", "subtotal", "discount", "tax", "total"),
            ("Sale ID", "Date and time", "Subtotal (₹)", "Discount (₹)", "Tax (₹)", "Total (₹)"),
            (70, 220, 130, 120, 100, 130)
        )
        ttk.Label(self.reports_tab, text="Best-selling products", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(16, 4))
        self.best_tree = self.make_tree(
            self.reports_tab,
            ("name", "quantity", "revenue"),
            ("Product", "Units sold", "Sales value (₹)"),
            (350, 150, 180)
        )
        button_row = ttk.Frame(self.reports_tab)
        button_row.pack(fill="x", pady=(8, 0))
        ttk.Button(button_row, text="Refresh reports", command=self.refresh_reports).pack(side="right")
        ttk.Button(button_row, text="Export sales CSV", command=self.export_sales_csv).pack(side="right", padx=(0, 8))

    def make_tree(self, parent, columns, headings, widths):
        wrapper = ttk.Frame(parent)
        wrapper.pack(fill="both", expand=True)
        tree = ttk.Treeview(wrapper, columns=columns, show="headings", selectmode="browse")
        yscroll = ttk.Scrollbar(wrapper, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(wrapper, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        wrapper.rowconfigure(0, weight=1)
        wrapper.columnconfigure(0, weight=1)
        for col, heading, width in zip(columns, headings, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=width, minwidth=55, anchor="w")
        return tree

    @staticmethod
    def money(value):
        return f"{value:,.2f}"

    def validate_product_form(self):
        name = self.p_name.get().strip()
        category = self.p_category.get().strip()
        sku = self.p_sku.get().strip()
        supplier = self.p_supplier.get().strip()
        if not name:
            raise ValueError("Enter a product name.")
        try:
            price = float(self.p_price.get())
            stock = int(self.p_stock.get())
            min_stock = int(self.p_min.get())
        except ValueError:
            raise ValueError("Price must be numeric; stock and minimum stock must be whole numbers.")
        if price < 0 or stock < 0 or min_stock < 0:
            raise ValueError("Price and stock quantities cannot be negative.")
        return name, category, price, stock, min_stock, sku, supplier

    def add_product(self):
        try:
            values = self.validate_product_form()
            with self.connect() as con:
                con.execute(
                    "INSERT INTO products(name, category, price, stock, min_stock, sku, supplier) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    values
                )
            self.clear_product_form()
            self.refresh_all()
            messagebox.showinfo("Success", "Product added successfully.")
        except ValueError as exc:
            messagebox.showerror("Check product details", str(exc))
        except sqlite3.Error as exc:
            messagebox.showerror("Database error", str(exc))

    def update_product(self):
        if not self.selected_product_id:
            messagebox.showwarning("Select a product", "Select a product from the list first.")
            return
        try:
            name, category, price, stock, min_stock, sku, supplier = self.validate_product_form()
            with self.connect() as con:
                con.execute(
                    """UPDATE products SET name=?, category=?, price=?, stock=?, min_stock=?, sku=?, supplier=?
                       WHERE id=?""",
                    (name, category, price, stock, min_stock, sku, supplier, self.selected_product_id)
                )
            self.clear_product_form()
            self.refresh_all()
            messagebox.showinfo("Success", "Product updated successfully.")
        except ValueError as exc:
            messagebox.showerror("Check product details", str(exc))
        except sqlite3.Error as exc:
            messagebox.showerror("Database error", str(exc))

    def delete_product(self):
        if not self.selected_product_id:
            messagebox.showwarning("Select a product", "Select a product from the list first.")
            return
        if not messagebox.askyesno("Confirm delete", "Delete the selected product? Past sales will remain in reports."):
            return
        with self.connect() as con:
            con.execute("DELETE FROM products WHERE id=?", (self.selected_product_id,))
        self.clear_product_form()
        self.refresh_all()

    def clear_product_form(self):
        self.selected_product_id = None
        self.p_name.set("")
        self.p_category.set("")
        self.p_price.set("")
        self.p_stock.set("")
        self.p_min.set("5")
        self.p_sku.set("")
        self.p_supplier.set("")
        if hasattr(self, "products_tree"):
            for item in self.products_tree.selection():
                self.products_tree.selection_remove(item)

    def on_product_select(self, _event=None):
        selection = self.products_tree.selection()
        if not selection:
            return
        values = self.products_tree.item(selection[0], "values")
        self.selected_product_id = int(values[0])
        with self.connect() as con:
            product = con.execute("SELECT * FROM products WHERE id=?", (self.selected_product_id,)).fetchone()
        if product:
            self.p_name.set(product["name"])
            self.p_category.set(product["category"])
            self.p_price.set(str(product["price"]))
            self.p_stock.set(str(product["stock"]))
            self.p_min.set(str(product["min_stock"]))
            self.p_sku.set(product["sku"])
            self.p_supplier.set(product["supplier"])

    def add_stock(self):
        choice = self.stock_product.get()
        if not choice:
            messagebox.showwarning("Select a product", "Choose a product to restock.")
            return
        try:
            quantity = int(self.stock_quantity.get())
            if quantity <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid quantity", "Enter a whole number greater than zero.")
            return
        product_id = int(choice.split(" — ", 1)[0])
        with self.connect() as con:
            con.execute("UPDATE products SET stock = stock + ? WHERE id=?", (quantity, product_id))
        self.stock_quantity.set("")
        self.refresh_all()
        messagebox.showinfo("Stock updated", f"Added {quantity} unit(s) to stock.")

    def add_to_cart(self):
        choice = self.checkout_product.get()
        if not choice:
            messagebox.showwarning("Select a product", "Choose a product first.")
            return
        try:
            quantity = int(self.checkout_quantity.get())
            if quantity <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid quantity", "Quantity must be a whole number greater than zero.")
            return
        product_id = int(choice.split(" — ", 1)[0])
        with self.connect() as con:
            product = con.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if not product:
            messagebox.showerror("Product unavailable", "This product no longer exists.")
            return
        already_in_cart = sum(item["quantity"] for item in self.cart if item["id"] == product_id)
        if already_in_cart + quantity > product["stock"]:
            messagebox.showerror("Insufficient stock", f"Only {product['stock'] - already_in_cart} unit(s) available to add.")
            return

        existing = next((item for item in self.cart if item["id"] == product_id), None)
        if existing:
            existing["quantity"] += quantity
        else:
            self.cart.append({
                "id": product_id,
                "name": product["name"],
                "quantity": quantity,
                "price": float(product["price"])
            })
        self.refresh_cart()

    def remove_cart_item(self):
        selection = self.cart_tree.selection()
        if not selection:
            messagebox.showwarning("Select an item", "Select a bill item to remove.")
            return
        product_id = int(self.cart_tree.item(selection[0], "values")[0])
        self.cart = [item for item in self.cart if item["id"] != product_id]
        self.refresh_cart()

    def calculate_totals(self):
        subtotal = sum(item["quantity"] * item["price"] for item in self.cart)
        try:
            discount = float(self.discount_var.get() or 0)
            tax_rate = float(self.tax_var.get() or 0)
            if discount < 0 or tax_rate < 0 or tax_rate > 100:
                raise ValueError
        except ValueError:
            return subtotal, 0.0, 0.0, subtotal
        discount = min(discount, subtotal)
        taxable = subtotal - discount
        tax = taxable * tax_rate / 100
        return subtotal, discount, tax, taxable + tax

    def refresh_cart(self):
        if not hasattr(self, "cart_tree"):
            return
        self.cart_tree.delete(*self.cart_tree.get_children())
        for item in self.cart:
            line_total = item["quantity"] * item["price"]
            self.cart_tree.insert("", "end", values=(
                item["id"], item["name"], item["quantity"],
                self.money(item["price"]), self.money(line_total)
            ))
        subtotal, discount, tax, total = self.calculate_totals()
        self.total_label.config(text=f"Total: ₹{self.money(total)}")
        return subtotal, discount, tax, total

    def complete_sale(self):
        if not self.cart:
            messagebox.showwarning("Empty bill", "Add at least one product to the bill.")
            return
        try:
            subtotal, discount, tax, total = self.calculate_totals()
            if float(self.tax_var.get() or 0) > 100 or float(self.tax_var.get() or 0) < 0:
                raise ValueError
            if float(self.discount_var.get() or 0) < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid discount or tax", "Discount must be non-negative and tax must be between 0 and 100.")
            return

        sale_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self.connect() as con:
                for item in self.cart:
                    product = con.execute("SELECT stock FROM products WHERE id=?", (item["id"],)).fetchone()
                    if not product or product["stock"] < item["quantity"]:
                        raise ValueError(f"Not enough stock for {item['name']}. Refresh the bill and try again.")

                cursor = con.execute(
                    "INSERT INTO sales(sale_time, subtotal, discount, tax, total) VALUES (?, ?, ?, ?, ?)",
                    (sale_time, subtotal, discount, tax, total)
                )
                sale_id = cursor.lastrowid
                for item in self.cart:
                    line_total = item["quantity"] * item["price"]
                    con.execute(
                        """INSERT INTO sale_items(sale_id, product_id, product_name, quantity, unit_price, line_total)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (sale_id, item["id"], item["name"], item["quantity"], item["price"], line_total)
                    )
                    con.execute(
                        "UPDATE products SET stock = stock - ? WHERE id=?",
                        (item["quantity"], item["id"])
                    )

            receipt_path = self.save_receipt(sale_id, sale_time, subtotal, discount, tax, total)
            self.cart.clear()
            self.discount_var.set("0")
            self.tax_var.set("0")
            self.refresh_all()
            self.refresh_cart()
            messagebox.showinfo("Sale completed", f"Sale #{sale_id} saved.\nReceipt: {receipt_path}")
        except (sqlite3.Error, OSError, ValueError) as exc:
            messagebox.showerror("Sale could not be completed", str(exc))

    def save_receipt(self, sale_id, sale_time, subtotal, discount, tax, total):
        RECEIPT_DIR.mkdir(exist_ok=True)
        path = RECEIPT_DIR / f"receipt_{sale_id}.txt"
        lines = [
            "SMART INVENTORY — CUSTOMER RECEIPT",
            "=" * 38,
            f"Receipt no.: {sale_id}",
            f"Date: {sale_time}",
            "-" * 38,
        ]
        for item in self.cart:
            amount = item["quantity"] * item["price"]
            lines.append(f"{item['name']} x {item['quantity']}")
            lines.append(f"  ₹{self.money(item['price'])} each = ₹{self.money(amount)}")
        lines.extend([
            "-" * 38,
            f"Subtotal:  ₹{self.money(subtotal)}",
            f"Discount:  ₹{self.money(discount)}",
            f"Tax:       ₹{self.money(tax)}",
            f"TOTAL:     ₹{self.money(total)}",
            "=" * 38,
            "Thank you!"
        ])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def refresh_products(self):
        if not hasattr(self, "products_tree"):
            return
        query = self.product_search.get().strip()
        self.products_tree.delete(*self.products_tree.get_children())
        with self.connect() as con:
            rows = con.execute(
                """SELECT * FROM products
                   WHERE name LIKE ? OR category LIKE ? OR sku LIKE ? OR supplier LIKE ? OR CAST(id AS TEXT) LIKE ?
                   ORDER BY name""",
                (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%")
            ).fetchall()
        for row in rows:
            self.products_tree.insert("", "end", values=(
                row["id"], row["name"], row["category"], row["sku"], row["supplier"],
                self.money(row["price"]), row["stock"], row["min_stock"]
            ))

    def refresh_combos(self):
        with self.connect() as con:
            rows = con.execute("SELECT id, name, stock FROM products ORDER BY name").fetchall()
        values = [f"{row['id']} — {row['name']} (stock: {row['stock']})" for row in rows]
        self.stock_combo["values"] = values
        self.checkout_combo["values"] = values
        if self.stock_product.get() not in values:
            self.stock_product.set("")
        if self.checkout_product.get() not in values:
            self.checkout_product.set("")

    def refresh_dashboard(self):
        today = datetime.now().strftime("%Y-%m-%d")
        with self.connect() as con:
            product_count = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            today_sales = con.execute(
                "SELECT COALESCE(SUM(total), 0) FROM sales WHERE sale_time LIKE ?",
                (today + "%",)
            ).fetchone()[0]
            low_items = con.execute(
                "SELECT * FROM products WHERE stock <= min_stock ORDER BY stock ASC, name"
            ).fetchall()
            inventory_value = con.execute("SELECT COALESCE(SUM(price * stock), 0) FROM products").fetchone()[0]
            reorder_candidates = con.execute(
                "SELECT * FROM products WHERE stock <= min_stock ORDER BY stock ASC, name LIMIT 5"
            ).fetchall()
        self.metric_products.config(text=str(product_count))
        self.metric_sales.config(text=f"₹{self.money(today_sales)}")
        self.metric_low.config(text=str(len(low_items)))
        self.metric_value.config(text=f"₹{self.money(inventory_value)}")

        self.low_tree.delete(*self.low_tree.get_children())
        for row in low_items:
            self.low_tree.insert("", "end", values=(row["id"], row["name"], row["stock"], row["min_stock"]))

        if reorder_candidates:
            suggestions = ", ".join(
                f"{row['name']} ({row['stock']}/{row['min_stock']})" for row in reorder_candidates
            )
            self.dashboard_summary.config(
                text=f"Inventory health: {len(low_items)} item(s) at or below minimum stock. "
                     f"Suggested reorder: {suggestions}"
            )
        else:
            self.dashboard_summary.config(
                text="Inventory health: all products are above their minimum stock threshold."
            )

    def refresh_reports(self):
        if not hasattr(self, "sales_tree"):
            return
        self.sales_tree.delete(*self.sales_tree.get_children())
        self.best_tree.delete(*self.best_tree.get_children())
        with self.connect() as con:
            sales = con.execute("SELECT * FROM sales ORDER BY id DESC LIMIT 100").fetchall()
            total_revenue = con.execute("SELECT COALESCE(SUM(total), 0) FROM sales").fetchone()[0]
            sale_count = con.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
            best = con.execute(
                """SELECT product_name, SUM(quantity) AS units, SUM(line_total) AS revenue
                   FROM sale_items GROUP BY product_name ORDER BY units DESC LIMIT 10"""
            ).fetchall()
            inventory_value = con.execute("SELECT COALESCE(SUM(price * stock), 0) FROM products").fetchone()[0]
        for row in sales:
            self.sales_tree.insert("", "end", values=(
                row["id"], row["sale_time"], self.money(row["subtotal"]),
                self.money(row["discount"]), self.money(row["tax"]), self.money(row["total"])
            ))
        for row in best:
            self.best_tree.insert("", "end", values=(
                row["product_name"], row["units"], self.money(row["revenue"])
            ))
        self.report_summary.config(
            text=f"All-time sales: ₹{self.money(total_revenue)}    |    "
                 f"Completed sales: {sale_count}    |    "
                 f"Current inventory value (at selling price): ₹{self.money(inventory_value)}"
        )

    def export_sales_csv(self):
        export_path = APP_DIR / "sales_export.csv"
        try:
            with self.connect() as con:
                sales = con.execute(
                    "SELECT id, sale_time, subtotal, discount, tax, total FROM sales ORDER BY id DESC"
                ).fetchall()
            with export_path.open("w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Sale ID", "Date and time", "Subtotal", "Discount", "Tax", "Total"])
                for row in sales:
                    writer.writerow([
                        row["id"], row["sale_time"], row["subtotal"], row["discount"], row["tax"], row["total"]
                    ])
            messagebox.showinfo("Export complete", f"Sales CSV exported to: {export_path}")
        except (sqlite3.Error, OSError) as exc:
            messagebox.showerror("Export failed", str(exc))

    def refresh_all(self):
        self.refresh_products()
        self.refresh_combos()
        self.refresh_dashboard()
        self.refresh_reports()
        if hasattr(self, "cart_tree"):
            self.refresh_cart()


def main():
    root = tk.Tk()
    InventoryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
