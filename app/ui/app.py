import customtkinter as ctk
from PIL import Image
from tkinter import messagebox, filedialog
import tkinter as tk
from tkinter import ttk
import threading
import webbrowser
import re
import shutil
import os
from datetime import datetime
from pathlib import Path

from app.config import (
    APP_NAME, ADMIN_PASSWORD, COLORS, SEGMENTOS,
    OPERADORES_TEXTO, OPERADORES_NUM, OPERADORES_DATA,
    FONT_TITLE, FONT_SUBTITLE, FONT_NORMAL, FONT_BUTTON, FONT_SMALL,
    WINDOW_WIDTH, WINDOW_HEIGHT,
    is_employee_build, get_logo_path, get_icon_path,
)
from app import database as db
from app import csv_io
from app.filters import FilterState, FilterRule, build_query, NUM_FIELDS, DATE_FIELDS
from app import ai_engine
from app import search as smart_search
from app import data_importer
from app.builder import build_employee_exe


class SoretracApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(APP_NAME)
        self._sort_col: str | None = None
        self._sort_reverse = False
        self._column_filters: dict[str, dict] = {}
        self._seg_keys = [k for k, _ in SEGMENTOS]

        self.is_admin = not is_employee_build()
        self.admin_unlocked = self.is_admin
        self.current_tab = "clientes"
        self.filter_state = FilterState()
        self.current_rows: list[dict] = []
        self.selected_rows: list[dict] = []
        self.search_query = ""
        self._search_after_id = None

        db.init_db()
        self._build_ui()
        self._center_window()
        self._load_data()

    def _center_window(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(0, (sw - WINDOW_WIDTH) // 2)
        y = max(0, (sh - WINDOW_HEIGHT) // 2 - 30)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")
        self.resizable(False, False)
        self.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.maxsize(WINDOW_WIDTH, WINDOW_HEIGHT)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(6, weight=1)  # so a tabela expande, nao as accoes

        self._build_header()
        self._build_search_bar()
        self._build_kpi_cards()
        self._build_filters()
        self._build_segmentos()
        self._build_actions()
        self._build_main_area()
        self._build_statusbar()
        if self.is_admin:
            self._build_admin_panel()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=COLORS["header"], height=80, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        header.grid_propagate(False)

        logo_path = get_logo_path()
        if logo_path.exists():
            try:
                img = Image.open(logo_path).convert("RGBA")
                w, h = img.size
                logo_h = 50
                logo_w = int(logo_h * w / h)  # proporcao original — sem achatar
                self.logo_img = ctk.CTkImage(img, size=(logo_w, logo_h))
                ctk.CTkLabel(header, image=self.logo_img, text="", width=logo_w + 10).grid(
                    row=0, column=0, padx=(16, 10), pady=14, sticky="w")
            except Exception:
                pass

        info = ctk.CTkFrame(header, fg_color="transparent")
        info.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(info, text="Follow-up Comercial",
                     font=ctk.CTkFont(size=FONT_SUBTITLE, weight="bold"), text_color="white").pack(anchor="w")
        self.lbl_atualizado = ctk.CTkLabel(info, text="", font=ctk.CTkFont(size=FONT_SMALL),
                                            text_color=COLORS["text_muted"])
        self.lbl_atualizado.pack(anchor="w")

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=2, padx=16)
        ctk.CTkButton(right, text="? Ajuda", width=90, height=34, font=ctk.CTkFont(size=FONT_BUTTON),
                      fg_color=COLORS["bg_card_light"], command=self._show_help).pack(side="right", padx=4)
        if not is_employee_build():
            ctk.CTkButton(right, text="Admin", width=80, height=34, command=self._toggle_admin).pack(side="right", padx=4)

        icon = get_icon_path()
        if icon.exists():
            try:
                self.iconbitmap(str(icon))
            except Exception:
                pass

    def _build_search_bar(self):
        bar = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10)
        bar.grid(row=1, column=0, sticky="ew", padx=12, pady=(10, 4))
        bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bar, text="Pesquisar", font=ctk.CTkFont(size=FONT_NORMAL, weight="bold"),
                     text_color=COLORS["accent"]).grid(row=0, column=0, padx=(14, 8), pady=12)

        self.search_entry = ctk.CTkEntry(
            bar, height=42, font=ctk.CTkFont(size=15),
            placeholder_text="Nome, email, telefone, cidade, produto... (ex: silva porto inativo)"
        )
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=10)
        self.search_entry.bind("<KeyRelease>", self._on_search_type)
        self.search_entry.bind("<Return>", lambda e: self._apply_search())

        ctk.CTkButton(bar, text="Pesquisar", width=120, height=40, font=ctk.CTkFont(size=FONT_BUTTON, weight="bold"),
                      fg_color=COLORS["accent"], command=self._apply_search).grid(row=0, column=2, padx=4, pady=10)
        ctk.CTkButton(bar, text="Limpar", width=90, height=40, font=ctk.CTkFont(size=FONT_BUTTON),
                      fg_color=COLORS["bg_card_light"], command=self._clear_search).grid(row=0, column=3, padx=(4, 14), pady=10)

        self.lbl_suggestions = ctk.CTkLabel(bar, text="", font=ctk.CTkFont(size=FONT_SMALL),
                                             text_color=COLORS["text_muted"])
        self.lbl_suggestions.grid(row=1, column=1, sticky="w", padx=4, pady=(0, 6))

    def _build_kpi_cards(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=2, column=0, sticky="ew", padx=12, pady=4)
        stats = db.get_stats()
        cards = [
            ("Clientes", stats["clientes"], COLORS["accent"]),
            ("Vendas", stats["vendas"], COLORS["success"]),
            ("Inativos +90d", stats["inativos_90d"], COLORS["warning"]),
            ("Emails", stats["emails"], COLORS["text_muted"]),
        ]
        self.kpi_labels = {}
        for i, (title, val, color) in enumerate(cards):
            card = ctk.CTkFrame(row, fg_color=COLORS["bg_card"], corner_radius=10)
            card.grid(row=0, column=i, padx=4, sticky="ew")
            row.grid_columnconfigure(i, weight=1)
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=FONT_SMALL), text_color=COLORS["text_muted"]).pack(padx=12, pady=(8, 0))
            lbl = ctk.CTkLabel(card, text=str(val), font=ctk.CTkFont(size=22, weight="bold"), text_color=color)
            lbl.pack(padx=12, pady=(0, 10))
            self.kpi_labels[title] = lbl

    def _build_filters(self):
        self.filters_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10)
        self.filters_frame.grid(row=3, column=0, sticky="new", padx=12, pady=4)

        top = ctk.CTkFrame(self.filters_frame, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(top, text="Filtros", font=ctk.CTkFont(size=FONT_NORMAL, weight="bold")).pack(side="left")
        self.filters_visible = False
        ctk.CTkButton(top, text="Mostrar filtros avancados", width=180, height=30,
                      font=ctk.CTkFont(size=FONT_SMALL), fg_color=COLORS["bg_card_light"],
                      command=self._toggle_filters).pack(side="right")

        self.filters_inner = ctk.CTkFrame(self.filters_frame, fg_color="transparent")

        labels = ["Cliente", "Comercial", "Produto", "Distrito", "Data de", "Data ate"]
        self.filter_entries = {}
        keys = ["cliente", "comercial", "produto", "distrito", "data_de", "data_ate"]

        grid = ctk.CTkFrame(self.filters_inner, fg_color="transparent")
        grid.pack(fill="x", padx=8, pady=4)
        for i, (label, key) in enumerate(zip(labels, keys)):
            ctk.CTkLabel(grid, text=label, font=ctk.CTkFont(size=FONT_SMALL)).grid(row=0, column=i*2, padx=4, pady=2)
            if key == "comercial":
                w = ctk.CTkComboBox(grid, width=140, height=32, values=[""], font=ctk.CTkFont(size=FONT_SMALL))
            else:
                w = ctk.CTkEntry(grid, width=140, height=32, placeholder_text=label, font=ctk.CTkFont(size=FONT_SMALL))
            w.grid(row=1, column=i*2, padx=4, pady=2)
            self.filter_entries[key] = w

        btns = ctk.CTkFrame(self.filters_inner, fg_color="transparent")
        btns.pack(fill="x", padx=8, pady=(4, 10))
        ctk.CTkButton(btns, text="Aplicar filtros", width=140, height=36, font=ctk.CTkFont(size=FONT_BUTTON),
                      fg_color=COLORS["primary"], command=self._apply_filters).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Limpar tudo", width=120, height=36, font=ctk.CTkFont(size=FONT_BUTTON),
                      command=self._clear_all).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Regras avancadas", width=140, height=36, font=ctk.CTkFont(size=FONT_BUTTON),
                      fg_color=COLORS["bg_card_light"], command=self._show_advanced_filters).pack(side="left", padx=4)

    def _toggle_filters(self):
        if self.filters_visible:
            self.filters_inner.pack_forget()
            self.filters_visible = False
        else:
            self.filters_inner.pack(fill="x")
            self.filters_visible = True

    def _build_segmentos(self):
        frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10)
        frame.grid(row=4, column=0, sticky="ew", padx=12, pady=4)
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Ultima compra:", font=ctk.CTkFont(size=FONT_SMALL, weight="bold")).grid(
            row=0, column=0, padx=(12, 6), pady=8, sticky="w")

        seg_labels = [s.replace("\n", " ") for _, s in SEGMENTOS]
        self.segmento_var = ctk.StringVar(value="todos")
        self.seg_button = ctk.CTkSegmentedButton(
            frame, values=seg_labels, height=34,
            font=ctk.CTkFont(size=11),
            command=self._on_segment_button,
        )
        self.seg_button.set(seg_labels[0])
        self.seg_button.grid(row=0, column=1, sticky="ew", padx=4, pady=8)

    def _on_segment_button(self, label: str):
        seg_labels = [s.replace("\n", " ") for _, s in SEGMENTOS]
        try:
            idx = seg_labels.index(label)
            self.segmento_var.set(self._seg_keys[idx])
        except ValueError:
            self.segmento_var.set("todos")
        self._on_segmento_change()

    def _build_actions(self):
        frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10, height=96)
        frame.grid(row=5, column=0, sticky="ew", padx=12, pady=(4, 8))
        frame.grid_propagate(False)
        frame.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(top, text="Acoes rapidas", font=ctk.CTkFont(size=FONT_SMALL, weight="bold"),
                     text_color="white").pack(side="left")

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=8, pady=(0, 10))

        actions = [
            ("Copiar Emails", self._copy_email, COLORS["bg_card_light"]),
            ("Email Seguimento", lambda: self._email_action("seguimento"), COLORS["primary"]),
            ("Email Proposta", lambda: self._email_action("proposta"), COLORS["primary_light"]),
            ("Email Reativacao", lambda: self._email_action("reativacao"), COLORS["warning"]),
            ("Analise IA", self._show_ai_panel, COLORS["accent"]),
            ("Exportar Excel", self._export_excel, COLORS["success"]),
        ]
        for i, (text, cmd, color) in enumerate(actions):
            ctk.CTkButton(btn_row, text=text, width=125, height=36, command=cmd,
                          font=ctk.CTkFont(size=11), fg_color=color).grid(
                row=0, column=i, padx=4, pady=2, sticky="ew")
            btn_row.grid_columnconfigure(i, weight=1)

    def _build_main_area(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=6, column=0, sticky="nsew", padx=12, pady=(0, 4))
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(2, weight=1)

        tabs = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=10, height=52)
        tabs.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        tabs.grid_propagate(False)

        tab_inner = ctk.CTkFrame(tabs, fg_color="transparent")
        tab_inner.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_buttons = {}
        for tab, label in [("clientes", "Clientes"), ("vendas", "Vendas"), ("emails", "Emails")]:
            btn = ctk.CTkButton(tab_inner, text=label, width=140, height=36,
                                font=ctk.CTkFont(size=FONT_BUTTON, weight="bold"),
                                command=lambda t=tab: self._switch_tab(t),
                                fg_color=COLORS["primary"] if tab == "clientes" else COLORS["bg_card_light"])
            btn.pack(side="left", padx=4)
            self.tab_buttons[tab] = btn

        self.lbl_count = ctk.CTkLabel(tab_inner, text="", font=ctk.CTkFont(size=FONT_SMALL),
                                       text_color=COLORS["text_muted"])
        self.lbl_count.pack(side="right", padx=8)

        self.lbl_sort_hint = ctk.CTkLabel(container, text="Clique na coluna para ordenar  |  Duplo-clique para filtrar",
                                           font=ctk.CTkFont(size=10), text_color=COLORS["text_muted"])
        self.lbl_sort_hint.grid(row=1, column=0, sticky="w", pady=(0, 4))

        tf = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=10)
        tf.grid(row=2, column=0, sticky="nsew")
        tf.grid_columnconfigure(0, weight=1)
        tf.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#1a2332", foreground="#f0f2f5",
                         fieldbackground="#1a2332", rowheight=32, font=("Segoe UI", 11))
        style.configure("Treeview.Heading", background="#005696", foreground="white",
                         font=("Segoe UI", 11, "bold"))
        style.map("Treeview", background=[("selected", COLORS["accent"])])
        style.configure("success.Treeview", background="#1a3d2e")
        style.configure("warning.Treeview", background="#3d3018")
        style.configure("danger.Treeview", background="#3d1a1a")

        self.tree = ttk.Treeview(tf, show="headings", selectmode="extended")
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tf, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_tree_double_click)

    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, fg_color=COLORS["header"], height=32, corner_radius=0)
        bar.grid(row=7, column=0, sticky="ew")
        self.lbl_status = ctk.CTkLabel(bar, text="Pronto", font=ctk.CTkFont(size=FONT_SMALL),
                                        text_color=COLORS["text_muted"])
        self.lbl_status.pack(side="left", padx=16, pady=6)

    def _build_admin_panel(self):
        panel = ctk.CTkFrame(self, fg_color=COLORS["primary_dark"], corner_radius=10,
                              border_width=2, border_color=COLORS["primary"])
        panel.grid(row=8, column=0, sticky="ew", padx=12, pady=(4, 12))

        ctk.CTkLabel(panel, text="ADMINISTRACAO",
                     font=ctk.CTkFont(size=FONT_NORMAL, weight="bold"),
                     text_color="white").pack(side="left", padx=16, pady=10)

        ctk.CTkButton(panel, text="Importar Base de Dados", width=220, height=40,
                      font=ctk.CTkFont(size=FONT_BUTTON, weight="bold"),
                      command=self._import_database,
                      fg_color=COLORS["success"]).pack(side="left", padx=6, pady=10)

        ctk.CTkLabel(panel, text="CSV | Excel | SQL | SQLite — deteta automaticamente",
                     font=ctk.CTkFont(size=FONT_SMALL), text_color=COLORS["text_muted"]).pack(side="left", padx=4)

        ctk.CTkButton(panel, text="GERAR 1 FICHEIRO PARA FUNCIONARIOS", width=320, height=44,
                      font=ctk.CTkFont(size=FONT_BUTTON, weight="bold"),
                      command=self._export_package, fg_color=COLORS["danger"]).pack(side="right", padx=16, pady=10)

    # ── Pesquisa inteligente ──────────────────────────────────────────

    def _on_search_type(self, _event=None):
        if self._search_after_id:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(300, self._update_suggestions)

    def _update_suggestions(self):
        q = self.search_entry.get().strip()
        if len(q) < 2:
            self.lbl_suggestions.configure(text="")
            return
        sugs = smart_search.search_suggestions(q, self.current_tab)
        if sugs:
            self.lbl_suggestions.configure(text="Sugestoes: " + " | ".join(sugs[:4]))
        else:
            self.lbl_suggestions.configure(text="")

    def _apply_search(self):
        self.search_query = self.search_entry.get().strip()
        self._load_data()

    def _clear_search(self):
        self.search_entry.delete(0, "end")
        self.search_query = ""
        self.lbl_suggestions.configure(text="")
        self._load_data()

    # ── Dados ─────────────────────────────────────────────────────────

    def _load_data(self):
        self._update_filter_state()
        if self.search_query:
            rows = smart_search.smart_search(self.search_query, self.current_tab)
            if self.filter_state.segmento != "todos" or any([
                self.filter_state.cliente, self.filter_state.comercial,
                self.filter_state.produto, self.filter_state.distrito,
                self.filter_state.data_de, self.filter_state.data_ate,
                self.filter_state.regras,
            ]):
                sql, params = build_query(self.current_tab, self.filter_state)
                filtered_ids = {r["id"] for r in db.query(sql, tuple(params))}
                rows = [r for r in rows if r.get("id") in filtered_ids]
            self.current_rows = rows
        else:
            sql, params = build_query(self.current_tab, self.filter_state)
            self.current_rows = db.query(sql, tuple(params))

        self.current_rows = self._apply_column_filters(self.current_rows)
        self._sort_rows()

        total = db.count_table(self.current_tab)
        shown = len(self.current_rows)
        self.lbl_count.configure(text=f"{shown} de {total} registos")
        self.lbl_atualizado.configure(text=f"Atualizado: {db.get_atualizado_em()}")
        self._populate_table()
        self._refresh_comercial_filter()
        self._update_kpis()
        self.lbl_status.configure(text=f"{self.current_tab.capitalize()} | {shown} registos")

    def _update_kpis(self):
        stats = db.get_stats()
        mapping = {"Clientes": stats["clientes"], "Vendas": stats["vendas"],
                   "Inativos +90d": stats["inativos_90d"], "Emails": stats["emails"]}
        for k, v in mapping.items():
            if k in self.kpi_labels:
                self.kpi_labels[k].configure(text=str(v))

    def _row_tag(self, row: dict) -> str:
        dias = row.get("dias_desde_ultima_compra")
        if dias is None:
            return ""
        try:
            d = int(dias)
            if d <= 30:
                return "success"
            if d > 365:
                return "danger"
            if d > 90:
                return "warning"
        except (ValueError, TypeError):
            pass
        return ""

    def _heading_label(self, col: str) -> str:
        label = col.replace("_", " ")
        if col in self._column_filters and self._column_filters[col].get("valor"):
            label += " [*]"
        if self._sort_col == col:
            label += " v" if self._sort_reverse else " ^"
        return label

    def _natural_key(self, value) -> list:
        parts = re.split(r"(\d+)", str(value or ""))
        result = []
        for p in parts:
            if p.isdigit():
                result.append(int(p))
            else:
                result.append(p.lower())
        return result

    def _sort_key(self, col: str, row: dict):
        val = row.get(col, "")
        if col in NUM_FIELDS or col in ("cliente_codigo", "quantidade", "valor", "dias_desde_ultima_compra"):
            try:
                return float(str(val).replace(",", ".").replace("€", "").strip())
            except (ValueError, TypeError):
                return self._natural_key(val)
        return str(val or "").lower()

    def _sort_rows(self):
        if not self._sort_col or not self.current_rows:
            return
        self.current_rows.sort(key=lambda r: self._sort_key(self._sort_col, r), reverse=self._sort_reverse)

    def _on_column_click(self, col: str):
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False
        self._sort_rows()
        self._populate_table()
        direction = "maior -> menor" if self._sort_reverse else "menor -> maior"
        self.lbl_status.configure(text=f"Ordenado por {col.replace('_', ' ')} ({direction})")

    def _match_column_filter(self, row: dict, col: str, op: str, val: str, val2: str = "") -> bool:
        cell = str(row.get(col, "") or "")
        cv = cell.lower()
        v = val.lower().strip()
        if op == "contém":
            return v in cv
        if op == "igual a":
            return cv == v
        if op == "começa com":
            return cv.startswith(v)
        if op == "termina com":
            return cv.endswith(v)
        if op == "não contém":
            return v not in cv
        try:
            n = float(str(row.get(col, 0)).replace(",", "."))
            fn = float(val.replace(",", "."))
        except (ValueError, TypeError):
            return True
        if op == "=":
            return n == fn
        if op == "≠":
            return n != fn
        if op == ">":
            return n > fn
        if op == ">=":
            return n >= fn
        if op == "<":
            return n < fn
        if op == "<=":
            return n <= fn
        if op == "entre":
            try:
                fn2 = float(val2.replace(",", "."))
            except ValueError:
                fn2 = fn
            return min(fn, fn2) <= n <= max(fn, fn2)
        return True

    def _apply_column_filters(self, rows: list[dict]) -> list[dict]:
        result = rows
        for col, filt in self._column_filters.items():
            val = filt.get("valor", "").strip()
            if not val:
                continue
            result = [
                r for r in result
                if self._match_column_filter(r, col, filt.get("operador", "contém"), val, filt.get("valor2", ""))
            ]
        return result

    def _populate_table(self):
        self.tree.delete(*self.tree.get_children())
        if not self.current_rows:
            self.tree["columns"] = ()
            return
        columns = [k for k in self.current_rows[0].keys() if k != "id"]
        self.tree["columns"] = columns
        for col in columns:
            self.tree.heading(
                col, text=self._heading_label(col),
                command=lambda c=col: self._on_column_click(c),
            )
            self.tree.column(col, width=max(100, min(200, len(col) * 10 + 50)), minwidth=65)
        for row in self.current_rows:
            vals = [row.get(c, "") for c in columns]
            tag = self._row_tag(row)
            self.tree.insert("", "end", values=vals, tags=(tag,) if tag else ())

    def _on_tree_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            col_id = self.tree.identify_column(event.x)
            try:
                idx = int(col_id.replace("#", "")) - 1
                columns = list(self.tree["columns"])
                if 0 <= idx < len(columns):
                    self._show_column_filter(columns[idx])
            except (ValueError, IndexError):
                pass

    def _show_column_filter(self, col: str):
        win = ctk.CTkToplevel(self)
        win.title(f"Filtrar: {col.replace('_', ' ')}")
        win.geometry("420x340")
        win.grab_set()
        win.resizable(False, False)

        ctk.CTkLabel(win, text=col.replace("_", " ").upper(),
                     font=ctk.CTkFont(size=FONT_SUBTITLE, weight="bold")).pack(pady=(12, 8))

        existing = self._column_filters.get(col, {})
        is_num = col in NUM_FIELDS or col in ("cliente_codigo", "dias_desde_ultima_compra", "quantidade", "valor")
        ops = OPERADORES_NUM if is_num else OPERADORES_TEXTO

        op_var = ctk.StringVar(value=existing.get("operador", ops[0]))
        ctk.CTkLabel(win, text="Condicao:", font=ctk.CTkFont(size=FONT_SMALL)).pack(anchor="w", padx=16)
        ctk.CTkComboBox(win, variable=op_var, values=ops, width=360).pack(padx=16, pady=4)

        ctk.CTkLabel(win, text="Valor:", font=ctk.CTkFont(size=FONT_SMALL)).pack(anchor="w", padx=16, pady=(8, 0))
        val_entry = ctk.CTkEntry(win, width=360, height=34, placeholder_text="Ex: C001 ou 90")
        val_entry.pack(padx=16, pady=4)
        if existing.get("valor"):
            val_entry.insert(0, existing["valor"])

        val2_entry = ctk.CTkEntry(win, width=360, height=34, placeholder_text="Valor 2 (para 'entre')")
        val2_entry.pack(padx=16, pady=4)
        if existing.get("valor2"):
            val2_entry.insert(0, existing["valor2"])

        bf = ctk.CTkFrame(win, fg_color="transparent")
        bf.pack(pady=12)

        def apply_filter():
            v = val_entry.get().strip()
            if v:
                self._column_filters[col] = {
                    "operador": op_var.get(), "valor": v, "valor2": val2_entry.get().strip(),
                }
            elif col in self._column_filters:
                del self._column_filters[col]
            win.destroy()
            self._load_data()

        def clear_col():
            self._column_filters.pop(col, None)
            win.destroy()
            self._load_data()

        def sort_asc():
            self._sort_col = col
            self._sort_reverse = False
            win.destroy()
            self._load_data()

        def sort_desc():
            self._sort_col = col
            self._sort_reverse = True
            win.destroy()
            self._load_data()

        ctk.CTkButton(bf, text="Menor -> Maior", width=120, height=34, command=sort_asc,
                      fg_color=COLORS["primary"]).grid(row=0, column=0, padx=4, pady=4)
        ctk.CTkButton(bf, text="Maior -> Menor", width=120, height=34, command=sort_desc,
                      fg_color=COLORS["primary"]).grid(row=0, column=1, padx=4, pady=4)
        ctk.CTkButton(bf, text="Aplicar filtro", width=120, height=34, command=apply_filter,
                      fg_color=COLORS["success"]).grid(row=1, column=0, padx=4, pady=4)
        ctk.CTkButton(bf, text="Limpar", width=120, height=34, command=clear_col,
                      fg_color=COLORS["bg_card_light"]).grid(row=1, column=1, padx=4, pady=4)

    def _refresh_comercial_filter(self):
        w = self.filter_entries.get("comercial")
        if isinstance(w, ctk.CTkComboBox):
            w.configure(values=[""] + db.get_distinct("clientes", "comercial"))

    def _update_filter_state(self):
        fs = self.filter_state
        fs.cliente = self._get_filter_val("cliente")
        fs.comercial = self._get_filter_val("comercial")
        fs.produto = self._get_filter_val("produto")
        fs.distrito = self._get_filter_val("distrito")
        fs.data_de = self._get_filter_val("data_de")
        fs.data_ate = self._get_filter_val("data_ate")
        fs.segmento = self.segmento_var.get()

    def _get_filter_val(self, key):
        w = self.filter_entries[key]
        return w.get().strip() if hasattr(w, "get") else ""

    def _apply_filters(self):
        self._update_filter_state()
        self._load_data()

    def _clear_all(self):
        for w in self.filter_entries.values():
            if isinstance(w, ctk.CTkComboBox):
                w.set("")
            else:
                w.delete(0, "end")
        self.segmento_var.set("todos")
        if hasattr(self, "seg_button"):
            seg_labels = [s.replace("\n", " ") for _, s in SEGMENTOS]
            self.seg_button.set(seg_labels[0])
        self.filter_state = FilterState()
        self._column_filters.clear()
        self._sort_col = None
        self._sort_reverse = False
        self._clear_search()

    def _on_segmento_change(self):
        if self.current_tab == "clientes":
            self._apply_filters()

    def _switch_tab(self, tab):
        self.current_tab = tab
        self._column_filters.clear()
        self._sort_col = None
        self._sort_reverse = False
        for t, btn in self.tab_buttons.items():
            btn.configure(fg_color=COLORS["primary"] if t == tab else COLORS["bg_card_light"])
        self._load_data()

    def _on_select(self, _e=None):
        cols = list(self.tree["columns"])
        self.selected_rows = [dict(zip(cols, self.tree.item(i, "values"))) for i in self.tree.selection()]

    def _get_selected_or_filtered(self):
        return self.selected_rows or self.current_rows

    # ── Acoes ─────────────────────────────────────────────────────────

    def _copy_email(self):
        emails = [r.get("email_factura") or r.get("email", "") for r in self._get_selected_or_filtered()]
        emails = [e for e in emails if e]
        if not emails:
            messagebox.showwarning("Aviso", "Nenhum email encontrado.\n\nSelecione clientes na tabela primeiro.")
            return
        self.clipboard_clear()
        self.clipboard_append("; ".join(emails))
        messagebox.showinfo("Copiado", f"{len(emails)} email(s) copiados.\nCole no Outlook com Ctrl+V.")

    def _email_action(self, tipo):
        rows = self._get_selected_or_filtered()
        if not rows:
            messagebox.showwarning("Aviso", "Selecione um cliente na tabela (clique na linha).")
            return
        row = rows[0]
        body = ai_engine.suggest_email(tipo, row)
        email = row.get("email_factura") or row.get("email", "")
        self._show_email_preview(tipo, email, body, row.get("cliente_nome", ""))

    def _show_email_preview(self, tipo, email, body, nome):
        win = ctk.CTkToplevel(self)
        win.title(f"Email - {tipo}")
        win.geometry("620x520")
        win.grab_set()
        ctk.CTkLabel(win, text=f"Cliente: {nome}", font=ctk.CTkFont(size=FONT_NORMAL, weight="bold")).pack(padx=14, pady=8, anchor="w")
        ctk.CTkLabel(win, text=f"Email: {email or '(sem email)'}", font=ctk.CTkFont(size=FONT_SMALL)).pack(padx=14, anchor="w")
        text = ctk.CTkTextbox(win, width=580, height=360, font=ctk.CTkFont(size=FONT_NORMAL))
        text.pack(padx=14, pady=8)
        text.insert("1.0", body)
        bf = ctk.CTkFrame(win, fg_color="transparent")
        bf.pack(pady=10)
        ctk.CTkButton(bf, text="Copiar texto", width=130, height=38, command=lambda: (
            self.clipboard_clear(), self.clipboard_append(text.get("1.0", "end")),
            messagebox.showinfo("OK", "Texto copiado!")
        )).pack(side="left", padx=6)
        if email:
            ctk.CTkButton(bf, text="Abrir Outlook", width=130, height=38, fg_color=COLORS["primary"],
                          command=lambda: webbrowser.open(f"mailto:{email}")).pack(side="left", padx=6)

    def _show_ai_panel(self):
        analysis = ai_engine.analyze_portfolio(self.current_rows)
        win = ctk.CTkToplevel(self)
        win.title("Analise Inteligente")
        win.geometry("680x560")
        win.grab_set()
        ctk.CTkLabel(win, text="Analise da sua lista", font=ctk.CTkFont(size=FONT_SUBTITLE, weight="bold")).pack(pady=12)
        text = ctk.CTkTextbox(win, width=640, height=460, font=ctk.CTkFont(size=FONT_NORMAL))
        text.pack(padx=16)
        for ins in analysis["insights"]:
            text.insert("end", ins + "\n\n")
        text.insert("end", "--- ACOES SUGERIDAS ---\n\n")
        for i, a in enumerate(analysis["acoes"], 1):
            text.insert("end", f"{i}. {a}\n")

    def _show_help(self):
        messagebox.showinfo(
            "Ajuda Rapida",
            "COMO USAR:\n\n"
            "1. PESQUISAR — escreva nome, email ou cidade na barra azul\n"
            "2. FILTRAR — clique 'Mostrar filtros avancados'\n"
            "3. SEGMENTAR — escolha periodo da ultima compra\n"
            "4. SELECIONAR — clique num cliente na tabela\n"
            "5. AGIR — use os botoes de acao (email, exportar...)\n\n"
            "CORES NA TABELA:\n"
            "Verde = cliente ativo (comprou ha pouco)\n"
            "Amarelo = inativo (+90 dias)\n"
            "Vermelho = critico (+1 ano sem comprar)\n\n"
            "DICAS DE PESQUISA:\n"
            "• 'silva' — encontra clientes Silva\n"
            "• 'porto inativo' — clientes do Porto inativos\n"
            "• '912' — pesquisa por telefone\n\n"
            "ORDENAR / FILTRAR COLUNAS:\n"
            "• Clique no titulo da coluna = ordenar (menor/maior)\n"
            "• Duplo-clique no titulo = filtro avancado da coluna\n"
            "• [*] na coluna = filtro activo | ^ v = ordem"
        )

    def _export_excel(self):
        if not self.current_rows:
            messagebox.showwarning("Aviso", "Sem dados para exportar.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
            initialfile=f"soretrac_{datetime.now().strftime('%Y%m%d')}.xlsx")
        if not path:
            return
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            cols = [k for k in self.current_rows[0].keys() if k != "id"]
            ws.append(cols)
            for row in self.current_rows:
                ws.append([row.get(c, "") for c in cols])
            wb.save(path)
            messagebox.showinfo("Exportado", f"Ficheiro guardado:\n{path}")
        except ImportError:
            p = Path(path).with_suffix(".csv")
            csv_io.export_csv(p, self.current_tab, self.current_rows)
            messagebox.showinfo("Exportado", f"Guardado como CSV:\n{p}")

    def _show_advanced_filters(self):
        win = ctk.CTkToplevel(self)
        win.title("Filtros Avancados")
        win.geometry("720x480")
        win.grab_set()
        logic_var = ctk.StringVar(value=self.filter_state.logica)
        ctk.CTkLabel(win, text="Criar regras de filtro", font=ctk.CTkFont(size=FONT_SUBTITLE, weight="bold")).pack(pady=10)
        lf = ctk.CTkFrame(win, fg_color="transparent")
        lf.pack()
        ctk.CTkRadioButton(lf, text="Todas (AND)", variable=logic_var, value="AND").pack(side="left", padx=10)
        ctk.CTkRadioButton(lf, text="Qualquer (OR)", variable=logic_var, value="OR").pack(side="left", padx=10)
        scroll = ctk.CTkScrollableFrame(win, width=680, height=300)
        scroll.pack(padx=12, pady=8)
        fields_map = {
            "clientes": ["cliente_nome", "dias_desde_ultima_compra", "comercial", "email_factura", "provincia_factura"],
            "vendas": ["cliente_nome", "produto", "valor", "comercial"],
            "emails": ["cliente_nome", "email", "assunto"],
        }
        fields = fields_map.get(self.current_tab, fields_map["clientes"])
        rule_widgets = []

        def add_rule(existing=None):
            rf = ctk.CTkFrame(scroll, fg_color=COLORS["bg_card"])
            rf.pack(fill="x", pady=3)
            cv = ctk.StringVar(value=existing.campo if existing else fields[0])
            ctk.CTkComboBox(rf, variable=cv, values=fields, width=160).pack(side="left", padx=4, pady=6)
            ov = ctk.StringVar(value=existing.operador if existing else "contém")
            oc = ctk.CTkComboBox(rf, variable=ov, values=OPERADORES_TEXTO, width=110)
            oc.pack(side="left", padx=4)
            v1 = ctk.CTkEntry(rf, width=130, placeholder_text="Valor")
            v1.pack(side="left", padx=4)
            v2 = ctk.CTkEntry(rf, width=80, placeholder_text="Ate")
            v2.pack(side="left", padx=4)
            if existing:
                v1.insert(0, existing.valor)
                v2.insert(0, existing.valor2)
            rule_widgets.append((cv, ov, v1, v2, oc))

        for rule in self.filter_state.regras:
            add_rule(rule)
        if not self.filter_state.regras:
            add_rule()
        ctk.CTkButton(win, text="+ Regra", command=lambda: add_rule()).pack(pady=4)

        def apply():
            self.filter_state.logica = logic_var.get()
            self.filter_state.regras = []
            for cv, ov, v1, v2, _ in rule_widgets:
                if v1.get().strip():
                    self.filter_state.regras.append(FilterRule(cv.get(), ov.get(), v1.get(), v2.get()))
            win.destroy()
            self._load_data()

        ctk.CTkButton(win, text="Aplicar", width=160, height=38, fg_color=COLORS["primary"], command=apply).pack(pady=10)

    # ── Admin ─────────────────────────────────────────────────────────

    def _toggle_admin(self):
        if self.admin_unlocked:
            self.admin_unlocked = False
            return
        pwd = ctk.CTkInputDialog(text="Password:", title="Admin").get_input()
        if pwd == ADMIN_PASSWORD:
            self.admin_unlocked = True
            messagebox.showinfo("OK", "Modo admin activo.")
        elif pwd:
            messagebox.showerror("Erro", "Password incorrecta.")

    def _import_database(self):
        if not self.admin_unlocked:
            messagebox.showerror("Acesso negado", "Active o modo admin primeiro.")
            return
        path = filedialog.askopenfilename(
            title="Importar Base de Dados",
            filetypes=[
                ("Todos suportados", "*.csv;*.xlsx;*.xls;*.sql;*.db;*.sqlite"),
                ("CSV", "*.csv"), ("Excel", "*.xlsx;*.xls"),
                ("SQL", "*.sql"), ("SQLite", "*.db;*.sqlite"), ("Todos", "*.*"),
            ],
        )
        if not path:
            folder = filedialog.askdirectory(title="Ou escolha uma pasta com ficheiros")
            if not folder:
                return
            path = folder
        result = data_importer.import_any(Path(path))
        if result.get("ok"):
            messagebox.showinfo("Importado", data_importer.format_import_report(result))
            self._load_data()
        else:
            messagebox.showerror("Erro", result.get("error", "Nao foi possivel importar."))

    def _export_package(self):
        if not self.admin_unlocked:
            messagebox.showerror("Acesso negado", "Active o modo admin.")
            return
        if db.count_table("clientes") == 0:
            messagebox.showwarning("Aviso", "Importe a base de dados primeiro.")
            return
        if not messagebox.askyesno(
            "Gerar ficheiro unico",
            "Vai ser criado UM UNICO ficheiro:\n\n"
            "   Soretrac_Funcionarios.exe\n\n"
            "Com TODOS os dados la dentro.\n"
            "E o UNICO ficheiro que envia aos funcionarios.\n"
            "Eles fazem duplo-clique e ja funciona.\n\n"
            "Continuar? (demora 2-5 minutos)",
        ):
            return

        pw = ctk.CTkToplevel(self)
        pw.title("A gerar executavel...")
        pw.geometry("480x120")
        pw.grab_set()
        lbl = ctk.CTkLabel(pw, text="A preparar...", font=ctk.CTkFont(size=FONT_NORMAL))
        lbl.pack(pady=30)

        def run():
            try:
                exe = build_employee_exe(lambda m: self.after(0, lambda: lbl.configure(text=m)))
                self.after(0, lambda: self._export_done(pw, exe, None))
            except Exception as e:
                self.after(0, lambda: self._export_done(pw, None, str(e)))

        threading.Thread(target=run, daemon=True).start()

    def _export_done(self, win, exe_path, err):
        win.destroy()
        if err:
            messagebox.showerror("Erro", err)
            return
        # Copiar automaticamente para pasta de envio no Ambiente de Trabalho
        desktop_dest = Path.home() / "Desktop" / "Soretrac" / "2-ENVIAR-FUNCIONARIOS"
        if desktop_dest.parent.exists():
            desktop_dest.mkdir(parents=True, exist_ok=True)
            for old in desktop_dest.glob("*"):
                if old.suffix.lower() in (".db", ".zip") or old.name in (
                    "SoretracFollowUp.exe", "SoretracDados.db"
                ):
                    try:
                        old.unlink()
                    except OSError:
                        pass
            final = desktop_dest / "Soretrac_Funcionarios.exe"
            shutil.copy2(exe_path, final)
            messagebox.showinfo(
                "Ficheiro Unico Pronto",
                f"PRONTO!\n\n"
                f"Ficheiro: Soretrac_Funcionarios.exe\n"
                f"Local: {desktop_dest}\n\n"
                f"Envie APENAS este ficheiro aos funcionarios.\n"
                f"Os dados ja vao DENTRO do executavel.\n"
                f"Nao precisa de enviar mais nada.",
            )
            os.startfile(str(desktop_dest))
        else:
            messagebox.showinfo(
                "Ficheiro Unico Pronto",
                f"Ficheiro criado:\n\n{exe_path}\n\n"
                f"Envie APENAS este .exe aos funcionarios.",
            )


def run_app():
    app = SoretracApp()
    app.mainloop()
