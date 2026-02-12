import os
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

try:
    from PIL import ImageTk
except Exception:  # pragma: no cover
    ImageTk = None

try:
    import ttkbootstrap as tb
except Exception:  # pragma: no cover
    tb = None

from label_qr_pdf import LabelRow, default_output_pdf, generate_labels_pdf, generate_qr_list_pdf
from label_qr_pdf import read_labels_from_csv, read_labels_from_txt
from label_qr_pdf import _make_qr_image_with_logo


_BaseWindow = tb.Window if tb is not None else tk.Tk


class App(_BaseWindow):
    def __init__(self) -> None:
        if tb is not None:
            super().__init__(themename="flatly")
        else:
            super().__init__()
        self.title("Toplu QR Kod Etiket")
        self.geometry("980x610")
        self.minsize(900, 560)

        self._use_bootstrap = tb is not None
        self._colors = {
            "header_bg": "#1f5fa8",
            "header_fg": "#ffffff",
            "sub_fg": "#d7e7ff",
        }

        self.txt_path = tk.StringVar(value="")
        self.csv_path = tk.StringVar(value="")
        self.output_path = tk.StringVar(value="")
        self.width_mm = tk.StringVar(value="80")
        self.height_mm = tk.StringVar(value="50")
        self.encoding = tk.StringVar(value="utf-8")
        self.logo_path = tk.StringVar(value="")
        self.logo_scale = tk.StringVar(value="22")

        self._labels: list[LabelRow] = []
        self._preview_imgs: list[ImageTk.PhotoImage] = []
        self._preview_px: int = 170

        root = ttk.Frame(self, padding=0)
        root.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(root, bg=self._colors["header_bg"], padx=14, pady=12)
        header.pack(fill=tk.X)
        title = tk.Label(
            header,
            text="Toplu QR Kod Oluşturucu",
            bg=self._colors["header_bg"],
            fg=self._colors["header_fg"],
            font=("Segoe UI", 18, "bold"),
        )
        title.pack(side=tk.LEFT)
        subtitle = tk.Label(
            header,
            text="TXT / CSV -> Etiket PDF",
            bg=self._colors["header_bg"],
            fg=self._colors["sub_fg"],
            font=("Segoe UI", 10),
        )
        subtitle.pack(side=tk.LEFT, padx=(14, 0), pady=(6, 0))

        content = ttk.Frame(root, padding=12)
        content.pack(fill=tk.BOTH, expand=True)

        body = ttk.Frame(content)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        left.rowconfigure(1, weight=0)

        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self._build_input_tabs(left)
        self._build_settings(left)
        self._build_preview(right)

        self._refresh_labels()

    def _build_input_tabs(self, parent: ttk.Frame) -> None:
        if self._use_bootstrap:
            tabs = tb.Notebook(parent, bootstyle="primary")
        else:
            tabs = ttk.Notebook(parent)
        tabs.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        self.tabs = tabs

        tab_manual = ttk.Frame(tabs, padding=12)
        tab_txt = ttk.Frame(tabs, padding=12)
        tab_csv = ttk.Frame(tabs, padding=12)
        tabs.add(tab_manual, text="  Manuel Giriş  ")
        tabs.add(tab_txt, text="  TXT Dosyası Yükle  ")
        tabs.add(tab_csv, text="  CSV Dosyası Yükle  ")

        self.manual_text = tk.Text(tab_manual, height=8, wrap="word", font=("Segoe UI", 10))
        self.manual_text.pack(fill=tk.BOTH, expand=True)
        ttk.Label(tab_manual, text="Örnek: HALI:buhari-bhr-03-red", foreground="#666").pack(anchor="w", pady=(6, 0))

        row = ttk.Frame(tab_txt)
        row.pack(fill=tk.X)
        ttk.Label(row, text="TXT dosyası:").pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self.txt_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        if self._use_bootstrap:
            tb.Button(row, text="Seç", command=self._pick_txt, bootstyle="secondary").pack(side=tk.LEFT)
        else:
            ttk.Button(row, text="Seç", command=self._pick_txt).pack(side=tk.LEFT)

        row2 = ttk.Frame(tab_csv)
        row2.pack(fill=tk.X)
        ttk.Label(row2, text="CSV dosyası:").pack(side=tk.LEFT)
        ttk.Entry(row2, textvariable=self.csv_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        if self._use_bootstrap:
            tb.Button(row2, text="Seç", command=self._pick_csv, bootstyle="secondary").pack(side=tk.LEFT)
        else:
            ttk.Button(row2, text="Seç", command=self._pick_csv).pack(side=tk.LEFT)

        tabs.bind("<<NotebookTabChanged>>", lambda _e: self._refresh_labels())
        self.manual_text.bind("<KeyRelease>", lambda _e: self._refresh_labels())

    def _build_settings(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Ayarlar", padding=10)
        box.grid(row=1, column=0, sticky="ew")
        box.columnconfigure(1, weight=1)

        ttk.Label(box, text="Kayıt Yeri (PDF):").grid(row=0, column=0, sticky="w")
        ttk.Entry(box, textvariable=self.output_path).grid(row=0, column=1, sticky="we", padx=(8, 0))
        if self._use_bootstrap:
            tb.Button(box, text="Gözat", command=self._pick_output, bootstyle="secondary").grid(row=0, column=2, padx=(8, 0))
        else:
            ttk.Button(box, text="Kaydet", command=self._pick_output).grid(row=0, column=2, padx=(8, 0))

        size = ttk.Frame(box)
        size.grid(row=1, column=0, columnspan=3, sticky="we", pady=(10, 0))
        ttk.Label(size, text="Etiket Boyutu (mm):").pack(side=tk.LEFT)
        ttk.Entry(size, textvariable=self.width_mm, width=6).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(size, text="x").pack(side=tk.LEFT, padx=6)
        ttk.Entry(size, textvariable=self.height_mm, width=6).pack(side=tk.LEFT)

        enc = ttk.Frame(box)
        enc.grid(row=2, column=0, columnspan=3, sticky="we", pady=(10, 0))
        ttk.Label(enc, text="Encoding:").pack(side=tk.LEFT)
        ttk.Entry(enc, textvariable=self.encoding, width=12).pack(side=tk.LEFT, padx=(8, 0))

        logo = ttk.Frame(box)
        logo.grid(row=3, column=0, columnspan=3, sticky="we", pady=(10, 0))
        logo.columnconfigure(1, weight=1)
        ttk.Label(logo, text="Logo (opsiyonel):").grid(row=0, column=0, sticky="w")
        ttk.Entry(logo, textvariable=self.logo_path).grid(row=0, column=1, sticky="we", padx=(8, 0))
        if self._use_bootstrap:
            tb.Button(logo, text="Seç", command=self._pick_logo, bootstyle="secondary").grid(row=0, column=2, padx=(8, 0))
            tb.Button(logo, text="Temizle", command=self._clear_logo, bootstyle="secondary").grid(row=0, column=3, padx=(8, 0))
        else:
            ttk.Button(logo, text="Seç", command=self._pick_logo).grid(row=0, column=2, padx=(8, 0))
            ttk.Button(logo, text="Temizle", command=self._clear_logo).grid(row=0, column=3, padx=(8, 0))

        logo2 = ttk.Frame(box)
        logo2.grid(row=4, column=0, columnspan=3, sticky="we", pady=(8, 0))
        ttk.Label(logo2, text="Logo Boyutu (%):").pack(side=tk.LEFT)
        ttk.Entry(logo2, textvariable=self.logo_scale, width=6).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(logo2, text="(öneri: 18-26)", foreground="#666").pack(side=tk.LEFT, padx=(10, 0))

        actions = ttk.Frame(box)
        actions.grid(row=5, column=0, columnspan=3, sticky="we", pady=(14, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

        if self._use_bootstrap:
            self.btn_generate = tb.Button(actions, text="QR KODLARI OLUŞTUR (PDF)", command=self.generate, bootstyle="success")
            self.btn_generate.grid(row=0, column=0, sticky="we", padx=(0, 8), ipady=8)
            tb.Button(actions, text="PDF Liste Olarak Kaydet", command=self.generate_list_pdf, bootstyle="primary").grid(
                row=0, column=1, sticky="we", ipady=8
            )
        else:
            self.btn_generate = ttk.Button(actions, text="PDF OLUŞTUR", command=self.generate)
            self.btn_generate.grid(row=0, column=0, sticky="we", padx=(0, 8), ipady=8)
            ttk.Button(actions, text="Önizlemeyi Yenile", command=self._refresh_labels).grid(row=0, column=1, sticky="we", ipady=8)

        self.lbl_status = ttk.Label(box, text="0 kayıt", foreground="#666")
        self.lbl_status.grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))

    def _pick_logo(self) -> None:
        p = filedialog.askopenfilename(filetypes=[("Image", "*.png *.jpg *.jpeg"), ("All", "*.*")])
        if not p:
            return
        self.logo_path.set(p)
        self._render_preview()

    def _clear_logo(self) -> None:
        self.logo_path.set("")
        self._render_preview()

    def _build_preview(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Önizleme (ilk 4 kayıt)", padding=10)
        box.grid(row=0, column=0, sticky="nsew")
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)

        self.preview = ttk.Frame(box)
        self.preview.grid(row=0, column=0, sticky="nsew")
        for i in range(2):
            self.preview.columnconfigure(i, weight=1)
        for i in range(2):
            self.preview.rowconfigure(i, weight=1)

        self.preview_cards: list[ttk.Label] = []
        for idx in range(4):
            r = idx // 2
            c = idx % 2
            card = ttk.Label(self.preview, text="", anchor="center", relief="groove")
            card.grid(row=r, column=c, sticky="nsew", padx=6, pady=6, ipadx=6, ipady=6)
            self.preview_cards.append(card)

        def _on_preview_resize(e):
            try:
                w = max(10, int(e.width))
                h = max(10, int(e.height))
                cell_w = (w - 3 * 12) // 2
                cell_h = (h - 3 * 12) // 2
                px = max(90, min(cell_w, cell_h) - 34)
                if abs(px - self._preview_px) >= 8:
                    self._preview_px = px
                    self._render_preview()
            except Exception:
                pass

        self.preview.bind("<Configure>", _on_preview_resize)

    def _pick_txt(self) -> None:
        p = filedialog.askopenfilename(filetypes=[("TXT", "*.txt"), ("All", "*.*")])
        if not p:
            return
        self.txt_path.set(p)
        if not self.output_path.get().strip():
            self.output_path.set(default_output_pdf(p))
        self._refresh_labels()

    def _pick_csv(self) -> None:
        p = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if not p:
            return
        self.csv_path.set(p)
        if not self.output_path.get().strip():
            self.output_path.set(default_output_pdf(p))
        self._refresh_labels()

    def _pick_output(self) -> None:
        p = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not p:
            return
        self.output_path.set(p)

    def _current_input_mode(self) -> str:
        tab = self.tabs.index(self.tabs.select())
        if tab == 0:
            return "manual"
        if tab == 1:
            return "txt"
        return "csv"

    def _refresh_labels(self) -> None:
        try:
            mode = self._current_input_mode()
            enc = self.encoding.get().strip() or "utf-8"
            if mode == "manual":
                raw = self.manual_text.get("1.0", "end").splitlines()
                lines = [ln.strip() for ln in raw if ln.strip()]
                tmp_path = None
                self._labels = []
                for ln in lines:
                    if ":" not in ln:
                        continue
                    cins, rest = ln.split(":", 1)
                    cins = cins.strip()
                    rest = rest.strip()
                    carpet_name = rest.replace("-", " ")
                    self._labels.append(LabelRow(cins=cins, carpet_name=carpet_name, qr_text=ln))
            elif mode == "txt":
                p = self.txt_path.get().strip()
                self._labels = read_labels_from_txt(p, encoding=enc) if p and os.path.exists(p) else []
            else:
                p = self.csv_path.get().strip()
                self._labels = read_labels_from_csv(p, encoding=enc) if p and os.path.exists(p) else []

            self.lbl_status.config(text=f"{len(self._labels)} kayıt")
            self._render_preview()
        except Exception as e:
            self._labels = []
            self.lbl_status.config(text="0 kayıt")
            self._render_preview(clear=True)

    def _render_preview(self, clear: bool = False) -> None:
        if ImageTk is None:
            for card in self.preview_cards:
                card.config(text="Önizleme için Pillow gerekli", image="")
            return
        self._preview_imgs = []
        if clear or not self._labels:
            for card in self.preview_cards:
                card.config(text="", image="")
            return

        sample = self._labels[:4]
        for i in range(4):
            card = self.preview_cards[i]
            if i >= len(sample):
                card.config(text="", image="")
                continue

            row = sample[i]
            logo = self.logo_path.get().strip() or None
            try:
                scale = float((self.logo_scale.get().strip() or "22")) / 100.0
            except ValueError:
                scale = 0.22
            img = _make_qr_image_with_logo(qr_text=row.qr_text, box_size=6, border=1, logo_path=logo, logo_scale=scale)
            px = int(self._preview_px)
            img = img.resize((px, px))
            photo = ImageTk.PhotoImage(img)
            self._preview_imgs.append(photo)
            card.config(image=photo, text=f"{row.cins}\n{row.carpet_name}")
            card.configure(compound="top")

    def generate(self) -> None:
        out = self.output_path.get().strip()
        if not out:
            mode = self._current_input_mode()
            if mode == "txt" and self.txt_path.get().strip():
                out = default_output_pdf(self.txt_path.get().strip())
            elif mode == "csv" and self.csv_path.get().strip():
                out = default_output_pdf(self.csv_path.get().strip())
            else:
                out = "etiketler.pdf"
            self.output_path.set(out)

        try:
            w = float(self.width_mm.get().strip())
            h = float(self.height_mm.get().strip())
        except ValueError:
            messagebox.showerror("Hata", "Etiket ölçüsü sayı olmalı")
            return

        logo = self.logo_path.get().strip() or None
        try:
            logo_scale = float((self.logo_scale.get().strip() or "22")) / 100.0
        except ValueError:
            logo_scale = 0.22

        try:
            self._refresh_labels()
            labels = self._labels
            if not labels:
                messagebox.showerror("Hata", "Dosyada etiket verisi bulunamadı")
                return
            generate_labels_pdf(labels, out, width_mm=w, height_mm=h, logo_path=logo, logo_scale=logo_scale)
        except Exception as e:
            messagebox.showerror("Hata", str(e))
            return

        messagebox.showinfo("Tamam", f"PDF hazır:\n{out}")

    def generate_list_pdf(self) -> None:
        out = self.output_path.get().strip()
        if not out:
            out = "liste.pdf"
            self.output_path.set(out)

        base, ext = os.path.splitext(out)
        if ext.lower() != ".pdf":
            out = out + ".pdf"

        list_out = base + "_liste.pdf"

        logo = self.logo_path.get().strip() or None
        try:
            logo_scale = float((self.logo_scale.get().strip() or "22")) / 100.0
        except ValueError:
            logo_scale = 0.22

        try:
            self._refresh_labels()
            labels = self._labels
            if not labels:
                messagebox.showerror("Hata", "Dosyada etiket verisi bulunamadı")
                return
            generate_qr_list_pdf(labels, list_out, cols=5, rows=12, logo_path=logo, logo_scale=logo_scale)
        except Exception as e:
            messagebox.showerror("Hata", str(e))
            return

        messagebox.showinfo("Tamam", f"Liste PDF hazır:\n{list_out}")


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
