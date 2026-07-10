"""
Lithophane Studio — main.py
A professional desktop app (PySide6) that converts any photo
into a printable 3D lithophane (.stl), with flat or curved
(lamp-shade) panel modes. Supports Arabic / English UI toggle.

Run:
    pip install -r requirements.txt
    python main.py
"""
import sys
import os
import traceback

from PySide6.QtCore import Qt, QThread, Signal, QSize, QLocale
from PySide6.QtGui import QPixmap, QImage, QIcon, QDragEnterEvent, QDropEvent, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QFileDialog,
    QVBoxLayout, QHBoxLayout, QGridLayout, QDoubleSpinBox, QSpinBox,
    QCheckBox, QProgressBar, QGroupBox, QFrame, QSizePolicy, QMessageBox,
    QSlider, QComboBox, QSplitter, QScrollArea, QStackedWidget
)
import numpy as np
from PIL import Image

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers 3d projection)

import core

APP_TITLE = "Lithophane Studio"

# Force '.' as the decimal separator regardless of the system/Windows locale,
# otherwise QDoubleSpinBox can flag values like 1.5 as "invalid" (red border)
# on machines whose regional settings use ',' as the decimal separator.
_NUMERIC_LOCALE = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)


# ------------------------------------------------------------------
# Translations
# ------------------------------------------------------------------
TR = {
    "app_subtitle": {
        "ar": "حوّل أي صورة إلى لوحة إضاءة ليثوفين ثلاثية الأبعاد جاهزة للطباعة",
        "en": "Turn any photo into a 3D-printable lithophane light panel",
    },
    "section_original": {"ar": "الصورة الأصلية", "en": "Original Image"},
    "section_heightmap": {"ar": "معاينة خريطة الإضاءة (Heightmap)", "en": "Heightmap Preview"},
    "drop_placeholder": {
        "ar": "اسحب صورة هنا\nأو اضغط زر (اختيار صورة)",
        "en": "Drag an image here\nor click (Choose Image)",
    },
    "heightmap_placeholder": {"ar": "ستظهر هنا بعد التوليد", "en": "Will appear here after generation"},
    "pick_button": {"ar": "📂  اختيار صورة", "en": "📂  Choose Image"},
    "status_ready": {"ar": "جاهز.", "en": "Ready."},
    "status_loaded": {"ar": "تم تحميل: {name}", "en": "Loaded: {name}"},
    "settings_title": {"ar": "⚙️  إعدادات الليثوفين", "en": "⚙️  Lithophane Settings"},
    "box_dimensions": {"ar": "الأبعاد الفيزيائية (مم)", "en": "Physical Dimensions (mm)"},
    "box_thickness": {"ar": "السماكة (مم)", "en": "Thickness (mm)"},
    "box_quality": {"ar": "الدقة والشكل", "en": "Resolution & Shape"},
    "box_options": {"ar": "خيارات إضافية", "en": "Additional Options"},
    "field_width": {"ar": "العرض", "en": "Width"},
    "field_height": {"ar": "الارتفاع", "en": "Height"},
    "field_min_thick": {"ar": "أقل سماكة (أفتح جزء)", "en": "Min thickness (brightest area)"},
    "field_max_thick": {"ar": "أعلى سماكة (أغمق جزء)", "en": "Max thickness (darkest area)"},
    "field_base_thick": {"ar": "سماكة القاعدة الصلبة", "en": "Solid base thickness"},
    "field_resolution": {"ar": "الدقة (بكسل/مم)", "en": "Resolution (px/mm)"},
    "field_curve": {"ar": "الانحناء° (0 = مسطح)", "en": "Curve° (0 = flat)"},
    "field_border": {"ar": "إطار حافة (مم)", "en": "Border frame (mm)"},
    "chk_invert": {"ar": "عكس الإضاءة (Invert)", "en": "Invert lighting"},
    "chk_equalize": {"ar": "تحسين التباين تلقائيًا (Equalize)", "en": "Auto contrast (Equalize)"},
    "chk_smooth": {"ar": "تنعيم الصورة (تقليل التشويش)", "en": "Smooth image (reduce noise)"},
    "chk_mirror": {
        "ar": "🔄  عكس أفقي (لتصحيح النص المعكوس)",
        "en": "🔄  Mirror horizontally (fix reversed text)",
    },
    "generate_btn": {"ar": "✨  توليد نموذج STL", "en": "✨  Generate STL Model"},
    "export_btn": {"ar": "💾  حفظ ملف STL", "en": "💾  Save STL File"},
    "warn_no_image": {"ar": "الرجاء اختيار صورة أولاً.", "en": "Please choose an image first."},
    "choose_image_dialog": {"ar": "اختر صورة", "en": "Choose Image"},
    "save_stl_dialog": {"ar": "حفظ ملف STL", "en": "Save STL File"},
    "saved_to": {"ar": "تم الحفظ في:\n{path}", "en": "Saved to:\n{path}"},
    "status_generated": {
        "ar": "تم التوليد ✔  ({v} نقطة / {f} مثلث)",
        "en": "Generated ✔  ({v} vertices / {f} faces)",
    },
    "status_error": {"ar": "حدث خطأ أثناء التوليد.", "en": "An error occurred during generation."},
    "lang_btn_to_en": {"ar": "🌐 EN", "en": "🌐 EN"},
    "lang_btn_to_ar": {"ar": "🌐 عربي", "en": "🌐 عربي"},
    "preview3d_btn": {"ar": "🔼\nمعاينة ثلاثية الأبعاد", "en": "🔼\n3D Preview"},
    "back_home_btn": {"ar": "⬅️  العودة للرئيسية", "en": "⬅️  Back to Home"},
    "preview3d_page_title": {"ar": "🧊  معاينة ثلاثية الأبعاد", "en": "🧊  3D Preview"},
    "preview3d_hint": {
        "ar": "اسحب بالماوس لتدوير النموذج",
        "en": "Drag with the mouse to rotate the model",
    },
    "preview3d_empty": {
        "ar": "ولّد نموذجًا أولاً لعرض المعاينة هنا",
        "en": "Generate a model first to see the preview here",
    },
}


# ------------------------------------------------------------------
# Background worker so the UI never freezes during mesh generation
# ------------------------------------------------------------------
class GenerateWorker(QThread):
    progress = Signal(int, str)
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, params: dict):
        super().__init__()
        self.params = params

    def run(self):
        try:
            result = core.generate_lithophane(
                progress_cb=lambda p, m: self.progress.emit(p, m),
                **self.params,
            )
            self.finished_ok.emit(result)
        except Exception as e:
            self.failed.emit(f"{e}\n\n{traceback.format_exc()}")


# ------------------------------------------------------------------
# Drag & drop image preview label
# ------------------------------------------------------------------
class DropImageLabel(QLabel):
    imageDropped = Signal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(320, 320)
        self.setObjectName("dropZone")
        self._has_image = False

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
                self.imageDropped.emit(path)
                break

    def set_image(self, path: str):
        pix = QPixmap(path).scaled(
            max(self.width() - 10, 50), max(self.height() - 10, 50),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.setPixmap(pix)
        self._has_image = True


# ------------------------------------------------------------------
# Main Window
# ------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1280, 900)
        self.image_path = None
        self.last_result = None
        self.worker = None
        self.lang = "ar"

        self._build_ui()
        self._apply_style()
        self.retranslate_ui()

    # ---------------- UI construction ----------------
    def _build_ui(self):
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self._build_home_page()
        self._build_preview3d_page()

        self.stack.addWidget(self.home_scroll)
        self.stack.addWidget(self.preview3d_page)
        self.stack.setCurrentIndex(0)

    def _build_home_page(self):
        outer_scroll = QScrollArea()
        outer_scroll.setWidgetResizable(True)
        outer_scroll.setFrameShape(QFrame.NoFrame)
        outer_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.home_scroll = outer_scroll

        content = QWidget()
        outer_scroll.setWidget(content)
        page = QVBoxLayout(content)
        page.setContentsMargins(18, 18, 18, 18)
        page.setSpacing(18)

        # ===== Top bar: language toggle (globe button, pinned top-left) =====
        top_bar = QHBoxLayout()
        self.lang_btn = QPushButton("🌐")
        self.lang_btn.setObjectName("langBtn")
        self.lang_btn.setFixedSize(68, 50)
        self.lang_btn.setCursor(Qt.PointingHandCursor)
        self.lang_btn.clicked.connect(self.toggle_language)
        # AlignLeft is an *absolute* alignment (not direction-aware), so the
        # globe button always sits at the physical top-left corner, in both
        # Arabic (RTL) and English (LTR) modes.
        top_bar.addStretch()
        top_bar.addWidget(self.lang_btn, alignment=Qt.AlignLeft)
        page.addLayout(top_bar)

        # ===== Header =====
        title = QLabel("🖼  Lithophane Studio")
        title.setObjectName("appTitle")
        page.addWidget(title)

        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("appSubtitle")
        self.subtitle_label.setWordWrap(True)
        page.addWidget(self.subtitle_label)

        # ===== Top row: (left) previews  |  (right) settings =====
        top_row = QHBoxLayout()
        top_row.setSpacing(18)
        page.addLayout(top_row)

        # ---- LEFT column ----
        left = QVBoxLayout()
        left.setSpacing(12)

        previews = QHBoxLayout()
        previews.setSpacing(10)

        col1 = QVBoxLayout()
        self.section_original_label = self._section_label("")
        col1.addWidget(self.section_original_label)
        self.drop_label = DropImageLabel()
        self.drop_label.imageDropped.connect(self.load_image)
        col1.addWidget(self.drop_label)
        previews.addLayout(col1)

        col2 = QVBoxLayout()
        self.section_heightmap_label = self._section_label("")
        col2.addWidget(self.section_heightmap_label)
        self.heightmap_label = QLabel()
        self.heightmap_label.setAlignment(Qt.AlignCenter)
        self.heightmap_label.setFixedSize(320, 320)
        self.heightmap_label.setObjectName("dropZone")
        col2.addWidget(self.heightmap_label)
        previews.addLayout(col2)

        left.addLayout(previews)

        self.pick_btn = QPushButton()
        self.pick_btn.clicked.connect(self.pick_image)
        left.addWidget(self.pick_btn)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        left.addWidget(self.progress)

        self.status_label = QLabel()
        self.status_label.setObjectName("statusLabel")
        left.addWidget(self.status_label)

        self.preview3d_btn = QPushButton()
        self.preview3d_btn.setObjectName("preview3dBtn")
        self.preview3d_btn.clicked.connect(self.open_preview3d_page)
        left.addWidget(self.preview3d_btn)

        top_row.addLayout(left, 5)

        # ---- RIGHT column: settings ----
        right = QVBoxLayout()
        right.setSpacing(14)
        self.settings_title_label = self._section_label("", big=True)
        right.addWidget(self.settings_title_label)

        self.size_box = QGroupBox()
        size_v = QVBoxLayout(self.size_box)
        self.width_spin, self.field_width_label = self._labeled_spin(size_v, 20, 400, 100)
        self.height_spin, self.field_height_label = self._labeled_spin(size_v, 20, 400, 100)
        right.addWidget(self.size_box)

        self.thick_box = QGroupBox()
        thick_v = QVBoxLayout(self.thick_box)
        self.min_thick_spin, self.field_min_thick_label = self._labeled_spin(thick_v, 0.2, 2.0, 0.6, step=0.1)
        self.max_thick_spin, self.field_max_thick_label = self._labeled_spin(thick_v, 1.0, 6.0, 3.0, step=0.1)
        self.base_thick_spin, self.field_base_thick_label = self._labeled_spin(thick_v, 0.0, 3.0, 0.6, step=0.1)
        right.addWidget(self.thick_box)

        self.quality_box = QGroupBox()
        quality_v = QVBoxLayout(self.quality_box)
        self.resolution_spin, self.field_resolution_label = self._labeled_spin(quality_v, 0.5, 15.0, 4.0, step=0.5)
        self.curve_spin, self.field_curve_label = self._labeled_spin(quality_v, 0.0, 180.0, 0.0, step=5.0)
        self.border_spin, self.field_border_label = self._labeled_spin(quality_v, 0.0, 10.0, 0.0, step=0.5)
        right.addWidget(self.quality_box)

        self.options_box = QGroupBox()
        options_v = QVBoxLayout(self.options_box)
        self.invert_check = QCheckBox()
        self.equalize_check = QCheckBox()
        self.smooth_check = QCheckBox()
        self.mirror_check = QCheckBox()
        options_v.addWidget(self.invert_check)
        options_v.addWidget(self.equalize_check)
        options_v.addWidget(self.smooth_check)
        options_v.addWidget(self.mirror_check)
        right.addWidget(self.options_box)

        self.generate_btn = QPushButton()
        self.generate_btn.setObjectName("primaryBtn")
        self.generate_btn.clicked.connect(self.on_generate)
        right.addWidget(self.generate_btn)

        self.export_btn = QPushButton()
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.on_save_as)
        right.addWidget(self.export_btn)

        right_widget = QWidget()
        right_widget.setLayout(right)
        right_widget.setFixedWidth(380)
        top_row.addWidget(right_widget, 0)

        page.addStretch()

    def _build_preview3d_page(self):
        page_widget = QWidget()
        self.preview3d_page = page_widget
        layout = QVBoxLayout(page_widget)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        top_bar = QHBoxLayout()
        self.back_home_btn = QPushButton()
        self.back_home_btn.setObjectName("backHomeBtn")
        self.back_home_btn.clicked.connect(self.close_preview3d_page)
        top_bar.addWidget(self.back_home_btn, alignment=Qt.AlignLeft)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        self.preview3d_title_label = QLabel()
        self.preview3d_title_label.setObjectName("appTitle")
        layout.addWidget(self.preview3d_title_label)

        self.preview3d_hint_label = QLabel()
        self.preview3d_hint_label.setObjectName("appSubtitle")
        layout.addWidget(self.preview3d_hint_label)

        self.fig3d = Figure(facecolor="#1c1f28")
        self.canvas3d = FigureCanvas(self.fig3d)
        self.canvas3d.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.ax3d = self.fig3d.add_subplot(111, projection="3d")
        self._style_3d_axes(empty=True)
        layout.addWidget(self.canvas3d, 1)  # stretch=1 -> fills the rest of the page, down to the bottom

    # ---------------- Page navigation ----------------
    def open_preview3d_page(self):
        if self.last_result is not None:
            self._update_3d_preview(self.last_result["top_grid"])
        else:
            self._style_3d_axes(empty=True)
        self.stack.setCurrentIndex(1)

    def close_preview3d_page(self):
        self.stack.setCurrentIndex(0)

    # ---------------- 3D preview helpers ----------------
    def _style_3d_axes(self, empty=False):
        ax = self.ax3d
        ax.clear()
        ax.set_facecolor("#1c1f28")
        for pane in (ax.xaxis, ax.yaxis, ax.zaxis):
            pane.set_pane_color((0.11, 0.12, 0.16, 1.0))
        ax.tick_params(colors="#6b6f85", labelsize=8)
        if empty:
            ax.text2D(
                0.5, 0.5, self._t("preview3d_empty"),
                transform=ax.transAxes, ha="center", color="#6b6f85", fontsize=12,
            )
        self.canvas3d.draw()

    def _update_3d_preview(self, top_grid: np.ndarray):
        rows, cols, _ = top_grid.shape
        # Heavily downsample for a smooth, lag-free interactive rotation.
        # matplotlib's 3D rendering has no GPU acceleration, so a dense mesh
        # makes every mouse-drag frame expensive and the UI appears to freeze
        # while it catches up on a backlog of motion events.
        max_dim = 40
        step = max(1, max(rows, cols) // max_dim)
        grid = top_grid[::step, ::step, :]

        X, Y, Z = grid[:, :, 0], grid[:, :, 1], grid[:, :, 2]

        self._style_3d_axes(empty=False)
        self.ax3d.plot_surface(
            X, Y, Z,
            cmap="inferno",
            linewidth=0,
            antialiased=False,
            shade=True,
            rcount=grid.shape[0],
            ccount=grid.shape[1],
        )
        try:
            self.ax3d.set_box_aspect(
                (X.max() - X.min() or 1, Y.max() - Y.min() or 1, (Z.max() - Z.min()) * 3 or 1)
            )
        except Exception:
            pass
        self.canvas3d.draw()

    # ---------------- small widget builders ----------------
    def _section_label(self, text, big=False):
        lbl = QLabel(text)
        lbl.setObjectName("bigSection" if big else "sectionLabel")
        return lbl

    def _labeled_spin(self, parent_layout, lo, hi, val, step=1.0):
        """
        Label placed ABOVE the field (not beside it), full width, so long
        labels never get clipped or squeezed by a narrow column.
        Returns (spinbox, label) so the label text can be translated later.
        """
        row = QVBoxLayout()
        row.setSpacing(2)
        lbl = QLabel()
        lbl.setObjectName("fieldLabel")
        lbl.setWordWrap(True)
        row.addWidget(lbl)

        spin = QDoubleSpinBox()
        spin.setLocale(_NUMERIC_LOCALE)          # avoid ',' vs '.' validation issues
        spin.setRange(lo, hi)
        spin.setSingleStep(step)
        spin.setDecimals(1)
        spin.setValue(val)
        spin.setButtonSymbols(QDoubleSpinBox.UpDownArrows)
        row.addWidget(spin)

        parent_layout.addLayout(row)
        parent_layout.addSpacing(6)
        return spin, lbl

    # ---------------- Language ----------------
    def toggle_language(self):
        self.lang = "en" if self.lang == "ar" else "ar"
        self.retranslate_ui()

    def _t(self, key):
        return TR[key][self.lang]

    def retranslate_ui(self):
        is_ar = self.lang == "ar"
        self.lang_btn.setToolTip("Switch to English" if is_ar else "التبديل إلى العربية")
        self.subtitle_label.setText(self._t("app_subtitle"))
        self.section_original_label.setText(self._t("section_original"))
        self.section_heightmap_label.setText(self._t("section_heightmap"))
        if not self.drop_label._has_image:
            self.drop_label.setText(self._t("drop_placeholder"))
        if self.heightmap_label.pixmap() is None or self.heightmap_label.pixmap().isNull():
            self.heightmap_label.setText(self._t("heightmap_placeholder"))
        self.pick_btn.setText(self._t("pick_button"))
        if self.image_path:
            self.status_label.setText(self._t("status_loaded").format(name=os.path.basename(self.image_path)))
        else:
            self.status_label.setText(self._t("status_ready"))

        self.settings_title_label.setText(self._t("settings_title"))
        self.size_box.setTitle(self._t("box_dimensions"))
        self.thick_box.setTitle(self._t("box_thickness"))
        self.quality_box.setTitle(self._t("box_quality"))
        self.options_box.setTitle(self._t("box_options"))

        self.field_width_label.setText(self._t("field_width"))
        self.field_height_label.setText(self._t("field_height"))
        self.field_min_thick_label.setText(self._t("field_min_thick"))
        self.field_max_thick_label.setText(self._t("field_max_thick"))
        self.field_base_thick_label.setText(self._t("field_base_thick"))
        self.field_resolution_label.setText(self._t("field_resolution"))
        self.field_curve_label.setText(self._t("field_curve"))
        self.field_border_label.setText(self._t("field_border"))

        self.invert_check.setText(self._t("chk_invert"))
        self.equalize_check.setText(self._t("chk_equalize"))
        self.smooth_check.setText(self._t("chk_smooth"))
        self.mirror_check.setText(self._t("chk_mirror"))

        self.generate_btn.setText(self._t("generate_btn"))
        self.export_btn.setText(self._t("export_btn"))
        self.preview3d_btn.setText(self._t("preview3d_btn"))

        self.back_home_btn.setText(self._t("back_home_btn"))
        self.preview3d_title_label.setText(self._t("preview3d_page_title"))
        self.preview3d_hint_label.setText(self._t("preview3d_hint"))
        # refresh the "generate a model first" placeholder text if it's showing
        if self.last_result is None:
            self._style_3d_axes(empty=True)

    # ---------------- Styling ----------------
    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #14161c; }
            QScrollArea { background-color: #14161c; border: none; }
            QWidget { background-color: #14161c; }
            QLabel { color: #e8e8ec; font-size: 13px; }
            #appTitle { font-size: 22px; font-weight: 700; color: #ffffff; }
            #appSubtitle { font-size: 12px; color: #9a9dae; margin-bottom: 6px; }
            #sectionLabel { font-size: 13px; font-weight: 600; color: #c9cbe0; }
            #bigSection { font-size: 16px; font-weight: 700; color: #ffffff; margin-bottom: 4px; }
            #statusLabel { color: #8fd6a3; font-size: 12px; }
            #fieldLabel { font-size: 12px; color: #b7b9cc; }
            #langBtn {
                background-color: #262a38;
                color: #ffffff;
                border: 1px solid #3a3f52;
                border-radius: 25px;
                font-size: 20px;
                font-weight: 700;
                padding: 0px;
            }
            #langBtn:hover { background-color: #3a3f52; }
            #dropZone {
                background-color: #1c1f28;
                border: 2px dashed #3a3f52;
                border-radius: 10px;
                color: #6b6f85;
            }
            QGroupBox {
                color: #d5d7e6;
                font-weight: 600;
                border: 1px solid #2a2e3a;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #181b23;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QDoubleSpinBox, QSpinBox, QComboBox {
                background-color: #1c1f28;
                color: #ffffff;
                border: 1px solid #343a4a;
                border-radius: 6px;
                padding: 6px 8px;
                min-height: 22px;
            }
            QDoubleSpinBox:focus, QSpinBox:focus {
                border: 1px solid #6c5ce7;
            }
            QPushButton {
                background-color: #262a38;
                color: #ffffff;
                border: 1px solid #3a3f52;
                border-radius: 8px;
                padding: 10px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #313648; }
            QPushButton:disabled { color: #63667a; background-color: #1c1f28; }
            #primaryBtn {
                background-color: #6c5ce7;
                border: none;
            }
            #primaryBtn:hover { background-color: #7d6ff0; }
            #preview3dBtn {
                background-color: #1c1f28;
                border: 1px solid #6c5ce7;
                color: #c9c2f9;
                font-weight: 700;
            }
            #preview3dBtn:hover { background-color: #24283a; }
            #backHomeBtn {
                background-color: #262a38;
                border: 1px solid #3a3f52;
                padding: 8px 16px;
            }
            QProgressBar {
                background-color: #1c1f28;
                border: 1px solid #343a4a;
                border-radius: 6px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #6c5ce7;
                border-radius: 6px;
            }
            QCheckBox { color: #d5d7e6; spacing: 8px; }
        """)

    # ---------------- Actions ----------------
    def pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self._t("choose_image_dialog"), "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if path:
            self.load_image(path)

    def load_image(self, path: str):
        self.image_path = path
        self.drop_label.set_image(path)
        self.status_label.setText(self._t("status_loaded").format(name=os.path.basename(path)))
        self.export_btn.setEnabled(False)

    def on_generate(self):
        if not self.image_path:
            QMessageBox.warning(self, APP_TITLE, self._t("warn_no_image"))
            return

        params = dict(
            image_path=self.image_path,
            output_stl_path=os.path.join(os.getcwd(), "_preview_output.stl"),
            width_mm=self.width_spin.value(),
            height_mm=self.height_spin.value(),
            px_per_mm=self.resolution_spin.value(),
            min_thickness_mm=self.min_thick_spin.value(),
            max_thickness_mm=self.max_thick_spin.value(),
            base_thickness_mm=self.base_thick_spin.value(),
            curve_degrees=self.curve_spin.value(),
            border_mm=self.border_spin.value(),
            invert=self.invert_check.isChecked(),
            equalize=self.equalize_check.isChecked(),
            blur_smooth=self.smooth_check.isChecked(),
            mirror_horizontal=self.mirror_check.isChecked(),
            lang=self.lang,
        )

        self.generate_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.progress.setValue(0)

        self.worker = GenerateWorker(params)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_ok.connect(self.on_generate_done)
        self.worker.failed.connect(self.on_generate_failed)
        self.worker.start()

    def on_progress(self, pct, msg):
        self.progress.setValue(pct)
        self.status_label.setText(msg)

    def on_generate_done(self, result: dict):
        self.last_result = result
        self.generate_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.status_label.setText(
            self._t("status_generated").format(v=result["vertices"], f=result["faces"])
        )
        self._show_heightmap_preview(result["heightmap"])

    def on_generate_failed(self, message: str):
        self.generate_btn.setEnabled(True)
        self.status_label.setText(self._t("status_error"))
        QMessageBox.critical(self, APP_TITLE, message)

    def _show_heightmap_preview(self, heightmap: np.ndarray):
        # keep a reference on self so the buffer isn't garbage-collected
        # while QImage still points at it
        self._heightmap_buffer = np.ascontiguousarray((heightmap * 255).astype(np.uint8))
        arr = self._heightmap_buffer
        h, w = arr.shape
        qimg = QImage(arr.data, w, h, w, QImage.Format_Grayscale8)
        pix = QPixmap.fromImage(qimg).scaled(
            max(self.heightmap_label.width() - 10, 50), max(self.heightmap_label.height() - 10, 50),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.heightmap_label.setPixmap(pix)

    def on_save_as(self):
        if not os.path.exists("_preview_output.stl"):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, self._t("save_stl_dialog"), "lithophane.stl", "STL Files (*.stl)"
        )
        if path:
            import shutil
            shutil.copyfile("_preview_output.stl", path)
            QMessageBox.information(self, APP_TITLE, self._t("saved_to").format(path=path))


def main():
    QLocale.setDefault(_NUMERIC_LOCALE)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")             # ensures the stylesheet renders consistently on Windows
    app.setLayoutDirection(Qt.RightToLeft)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
