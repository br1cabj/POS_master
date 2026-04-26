import os
import platform
import random
import subprocess
from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from core.base_view import BaseView
from core.context import AppContext
from controllers.article_controller import ArticleController
from utils.label_printer import LabelPrinter
from utils.styles import (
    ACCENT, ACCENT_DIM, ACCENT_TEXT, BORDER, BORDER_ACTIVE,
    GREEN, GREEN_DIM, GREEN_TEXT, ORANGE, ORANGE_DIM, ORANGE_TEXT,
    RED, RED_DIM, RED_TEXT, SURFACE1, SURFACE2, SURFACE3, SURFACE4,
    TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
    apply_treeview_style,
)


class ArticlesView(BaseView):
    def __init__(self, master, ctx: AppContext):
        super().__init__(master, ctx)
        self.controller = ArticleController(ctx.db_engine)

        self.editing_variant_id = None
        self.current_variants = []
        self.suppliers_map = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        apply_treeview_style()

        # ── Panel izquierdo: Formulario ──────────────────────────────────
        self.left_panel = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        self.left_panel.grid(row=0, column=0, sticky='nsew', padx=(16, 8), pady=16)

        self.lbl_form_title = ctk.CTkLabel(
            self.left_panel,
            text='📦 Nuevo Producto',
            font=('Arial', 17, 'bold'),
            text_color=TEXT_PRIMARY,
        )
        self.lbl_form_title.pack(pady=(22, 6))

        ctk.CTkLabel(
            self.left_panel,
            text='Escanea con pistola o escribe el código',
            font=('Arial', 10),
            text_color=TEXT_MUTED,
        ).pack(pady=(0, 14))

        # Campos del formulario
        self.entry_barcode = ctk.CTkEntry(
            self.left_panel,
            placeholder_text='Código de Barras  (Enter para buscar)',
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY, height=36,
        )
        self.entry_barcode.pack(pady=(0, 8), padx=20, fill='x')
        self.entry_barcode.bind('<Return>', self.on_barcode_scanned)

        self.entry_name = ctk.CTkEntry(
            self.left_panel,
            placeholder_text='Nombre del producto',
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY, height=36,
        )
        self.entry_name.pack(pady=(0, 8), padx=20, fill='x')

        ctk.CTkLabel(
            self.left_panel, text='PROVEEDOR ASOCIADO',
            font=('Arial', 9, 'bold'), text_color=TEXT_MUTED, anchor='w',
        ).pack(padx=20, anchor='w', pady=(8, 2))
        self.combo_supplier = ctk.CTkComboBox(
            self.left_panel, values=['Cargando...'],
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY, height=36,
            button_color=SURFACE3, button_hover_color=SURFACE4,
            dropdown_fg_color=SURFACE2, dropdown_text_color=TEXT_PRIMARY,
        )
        self.combo_supplier.pack(pady=(0, 8), padx=20, fill='x')

        self.entry_cost = ctk.CTkEntry(
            self.left_panel, placeholder_text='Precio de Costo ($)',
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY, height=36,
        )
        self.entry_cost.pack(pady=(0, 8), padx=20, fill='x')

        self.entry_price = ctk.CTkEntry(
            self.left_panel, placeholder_text='Precio de Venta ($)',
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY, height=36,
        )
        self.entry_price.pack(pady=(0, 8), padx=20, fill='x')

        self.entry_stock = ctk.CTkEntry(
            self.left_panel, placeholder_text='Stock Inicial',
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY, height=36,
        )
        self.entry_stock.pack(pady=(0, 16), padx=20, fill='x')

        self.btn_add = ctk.CTkButton(
            self.left_panel, text='➕  Agregar al Inventario',
            fg_color=ACCENT_DIM, hover_color=ACCENT, text_color=ACCENT_TEXT,
            border_width=1, border_color=ACCENT, height=38, corner_radius=8,
            cursor='hand2',
            command=self.save_article,
        )
        self.btn_add.pack(pady=(0, 6), padx=20, fill='x')

        self.btn_cancel = ctk.CTkButton(
            self.left_panel, text='↺  Limpiar Formulario',
            fg_color=SURFACE3, hover_color=SURFACE4,
            text_color=TEXT_SECONDARY, border_width=1, border_color=BORDER,
            height=36, corner_radius=8,
            cursor='hand2',
            command=self.reset_form,
        )
        self.btn_cancel.pack(pady=(0, 20), padx=20, fill='x')

        # ── Panel derecho: Catálogo ──────────────────────────────────────
        self.right_panel = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        self.right_panel.grid(row=0, column=1, sticky='nsew', padx=(8, 16), pady=16)

        # Header del catálogo
        hdr = ctk.CTkFrame(self.right_panel, fg_color='transparent')
        hdr.pack(fill='x', padx=16, pady=(16, 4))
        ctk.CTkLabel(
            hdr, text='Catálogo de Productos',
            font=('Arial', 15, 'bold'), text_color=TEXT_PRIMARY, anchor='w',
        ).pack(side='left')

        ctk.CTkLabel(
            self.right_panel,
            text='Doble clic en un producto para editarlo',
            font=('Arial', 10), text_color=TEXT_MUTED,
        ).pack(anchor='w', padx=16, pady=(0, 6))

        # ── Barra de búsqueda en tiempo real ──────────────────────────────
        search_row = ctk.CTkFrame(self.right_panel, fg_color='transparent')
        search_row.pack(fill='x', padx=14, pady=(0, 6))

        self._search_var = ctk.StringVar()
        self._search_var.trace_add('write', self._filter_tree)
        ctk.CTkEntry(
            search_row,
            textvariable=self._search_var,
            placeholder_text='🔍 Buscar por nombre, código o proveedor...',
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY, height=34,
        ).pack(side='left', fill='x', expand=True)

        self.lbl_count = ctk.CTkLabel(
            search_row, text='', font=('Arial', 10),
            text_color=TEXT_MUTED, width=100, anchor='e',
        )
        self.lbl_count.pack(side='right', padx=(8, 0))

        self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
        self.table_container.pack(fill='both', expand=True, padx=14, pady=(0, 8))

        self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

        columns = ('ID', 'Código', 'Nombre', 'Proveedor', 'Costo', 'Venta', 'Stock')
        self.tree = ttk.Treeview(
            self.table_container,
            columns=columns, show='headings', height=15,
            yscrollcommand=self.tree_scroll.set,
        )
        self.tree_scroll.configure(command=self.tree.yview)

        for col in columns:
            self.tree.heading(col, text=col)
            width = 150 if col == 'Nombre' else 80
            anchor = 'w' if col == 'Nombre' else 'center'
            self.tree.column(col, anchor=anchor, width=width)

        self.tree_scroll.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)
        self.tree.bind('<Double-1>', self.on_tree_double_click)

        # Botones inferiores del catálogo
        btns = ctk.CTkFrame(self.right_panel, fg_color='transparent')
        btns.pack(fill='x', padx=14, pady=(4, 14))

        self.btn_delete = ctk.CTkButton(
            btns, text='🗑  Eliminar Seleccionado',
            fg_color=RED_DIM, hover_color=RED, text_color=RED_TEXT,
            border_width=1, border_color=RED, height=36, corner_radius=8,
            cursor='hand2',
            command=self.delete_article,
        )
        self.btn_delete.pack(side='left', expand=True, fill='x', padx=(0, 6))

        self.btn_print_labels = ctk.CTkButton(
            btns, text='🖨  Imprimir Etiquetas PDF',
            fg_color=ACCENT_DIM, hover_color=ACCENT, text_color=ACCENT_TEXT,
            border_width=1, border_color=ACCENT, height=36, corner_radius=8,
            cursor='hand2',
            command=self.print_labels,
        )
        self.btn_print_labels.pack(side='left', expand=True, fill='x')

        self.after(100, self.load_data)
        self.entry_barcode.focus()

    def load_data(self):
        tenant_id = self.ctx.tenant_id

        suppliers = self.controller.get_suppliers_for_combo(tenant_id)
        self.suppliers_map = {s['name']: s['id'] for s in suppliers}

        if self.suppliers_map:
            combo_vals = ['Sin Proveedor'] + list(self.suppliers_map.keys())
            self.combo_supplier.configure(values=combo_vals)
        else:
            self.combo_supplier.configure(values=['Sin Proveedor'])
        self.combo_supplier.set('Sin Proveedor')

        self.current_variants = self.controller.get_all_variants(tenant_id)
        self._filter_tree()

    def _filter_tree(self, *args):
        """Filtra la tabla en tiempo real según el texto del buscador."""
        q = self._search_var.get().lower()
        if q:
            matches = [
                v for v in self.current_variants
                if q in (v.get('name') or '').lower()
                or q in str(v.get('barcode') or '').lower()
                or q in (v.get('supplier_name') or '').lower()
            ]
        else:
            matches = self.current_variants

        for item in self.tree.get_children():
            self.tree.delete(item)

        for variant in matches:
            stock_actual = variant.get('total_stock', 0)
            stock_format = (
                f'{int(stock_actual)}'
                if float(stock_actual).is_integer()
                else f'{float(stock_actual):.2f}'
            )
            self.tree.insert(
                '', 'end',
                values=(
                    variant.get('variant_id'),
                    variant.get('barcode') or 'N/A',
                    variant.get('name'),
                    variant.get('supplier_name'),
                    f'${variant.get("cost_price", 0):.2f}',
                    f'${variant.get("selling_price", 0):.2f}',
                    stock_format,
                ),
            )

        total = len(self.current_variants)
        shown = len(matches)
        if hasattr(self, 'lbl_count'):
            self.lbl_count.configure(
                text=f'{shown} de {total}' if q else f'{total} productos'
            )

    def on_barcode_scanned(self, event):
        barcode = self.entry_barcode.get().strip().lstrip('0') or '0'
        if not barcode:
            return
        found = next(
            (v for v in self.current_variants if str(v.get('barcode')) == barcode), None
        )
        if found:
            self.load_variant_into_form(found)
            self.entry_price.focus()
        else:
            self.reset_form(keep_barcode=True)
            self.entry_name.focus()

    def on_tree_double_click(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        variant_id = self.tree.item(selected[0], 'values')[0]
        found = next(
            (v for v in self.current_variants if str(v.get('variant_id')) == str(variant_id)),
            None,
        )
        if found:
            self.load_variant_into_form(found)

    def load_variant_into_form(self, variant):
        self.reset_form()
        self.editing_variant_id = variant['variant_id']

        self.entry_barcode.insert(0, variant.get('barcode', ''))
        self.entry_name.insert(0, variant.get('name', ''))
        self.entry_cost.insert(0, f'{variant.get("cost_price", 0):.2f}')
        self.entry_price.insert(0, f'{variant.get("selling_price", 0):.2f}')

        supplier_name = variant.get('supplier_name', 'Sin Proveedor')
        self.combo_supplier.set(
            supplier_name if supplier_name in self.suppliers_map else 'Sin Proveedor'
        )

        stock_val = variant.get('total_stock', 0)
        try:
            stock_str = f'{int(stock_val)}' if float(stock_val).is_integer() else f'{float(stock_val):.2f}'
        except (TypeError, ValueError):
            stock_str = str(stock_val)
        self.entry_stock.insert(0, f'Stock actual: {stock_str} u  ·  Ajustar desde Compras')
        self.entry_stock.configure(state='disabled', text_color=TEXT_MUTED)

        self.lbl_form_title.configure(text='✏️ Editando Producto', text_color=ACCENT_TEXT)
        self.btn_add.configure(text='💾  Actualizar Precios / Datos')

    def reset_form(self, keep_barcode=False):
        self.editing_variant_id = None

        barcode_temp = self.entry_barcode.get() if keep_barcode else ''
        self.entry_barcode.delete(0, 'end')
        if keep_barcode:
            self.entry_barcode.insert(0, barcode_temp)

        self.entry_name.delete(0, 'end')
        self.entry_cost.delete(0, 'end')
        self.entry_price.delete(0, 'end')

        self.entry_stock.configure(state='normal', text_color=TEXT_PRIMARY)
        self.entry_stock.delete(0, 'end')
        self.combo_supplier.set('Sin Proveedor')

        self.lbl_form_title.configure(text='📦 Nuevo Producto', text_color=TEXT_PRIMARY)
        self.btn_add.configure(text='➕  Agregar al Inventario')
        if not keep_barcode:
            self.entry_barcode.focus()

    def save_article(self):
        name = self.entry_name.get().strip()
        raw_barcode = self.entry_barcode.get().strip().lstrip('0')
        barcode = (
            raw_barcode if raw_barcode
            else f'99{random.randint(1000000000, 9999999999)}'
        )
        cost_str = self.entry_cost.get().strip().replace(',', '.')
        price_str = self.entry_price.get().strip().replace(',', '.')
        supplier_name = self.combo_supplier.get()
        supplier_id = self.suppliers_map.get(supplier_name)

        if not name or not cost_str or not price_str:
            CTkMessagebox(
                title='Faltan Datos',
                message='Nombre, costo y precio son obligatorios.',
                icon='warning',
            )
            return

        try:
            cost = float(cost_str)
            price = float(price_str)
            initial_stock = 0.0
            if not self.editing_variant_id:
                stock_str = self.entry_stock.get().strip().replace(',', '.')
                initial_stock = float(stock_str) if stock_str else 0.0
        except ValueError:
            CTkMessagebox(title='Error', message='Precios o stock deben ser números.', icon='cancel')
            return

        tenant_id = self.ctx.tenant_id

        if self.editing_variant_id:
            success, msg = self.controller.update_article(
                tenant_id, self.editing_variant_id, name, barcode, cost, price, supplier_id
            )
        else:
            user_id = self.ctx.user_id
            success, msg = self.controller.add_simple_article(
                tenant_id, user_id, name, barcode, cost, price, initial_stock, supplier_id
            )

        if success:
            self.show_success(msg)
            self.reset_form()
            self.load_data()
        else:
            self.show_error(msg)

    def delete_article(self):
        selected = self.tree.selection()
        if not selected:
            return

        msg = CTkMessagebox(
            title='Confirmar',
            message='¿Seguro que deseas eliminar este producto?',
            icon='question', option_1='No', option_2='Sí',
        )
        if msg.get() == 'Sí':
            variant_id = self.tree.item(selected[0], 'values')[0]
            tenant_id = self.ctx.tenant_id
            success, msg_response = self.controller.delete_variant(tenant_id, variant_id)
            if success:
                self.load_data()
                self.reset_form()
                CTkMessagebox(title='Eliminado', message=msg_response, icon='check')
            else:
                CTkMessagebox(title='Error', message=msg_response, icon='cancel')

    def print_labels(self):
        selected_items = self.tree.selection()
        if not selected_items:
            CTkMessagebox(
                title='Atención',
                message='Selecciona al menos un artículo de la tabla.\n(Podés usar Shift o Ctrl para seleccionar varios)',
                icon='info',
            )
            return

        products_to_print = []
        for item_id in selected_items:
            values = self.tree.item(item_id, 'values')
            barcode = values[1] if values[1] != 'N/A' else '000000000000'
            price_str = values[5].replace('$', '')
            products_to_print.append(
                {'name': values[2], 'barcode': barcode, 'price': float(price_str)}
            )

        try:
            printer = LabelPrinter()
            filename = f'etiquetas_{self.ctx.tenant_id}.pdf'
            printer.generate_labels_pdf(products_to_print, filename)
            CTkMessagebox(
                title='¡Éxito!',
                message=f'PDF generado:\n{filename}',
                icon='check',
            )
            try:
                if platform.system() == 'Windows':
                    os.startfile(filename)
                elif platform.system() == 'Darwin':
                    subprocess.call(['open', filename], capture_output=True)
                else:
                    subprocess.call(['xdg-open', filename], capture_output=True)
            except Exception:
                pass
        except Exception as e:
            CTkMessagebox(title='Error', message=f'No se pudo generar el PDF: {e}', icon='cancel')
