"""
Lithophane Studio — main.py (Advanced Full-Featured Version)
A professional desktop app that converts photos into 3D-printable lithophanes
with flat, cylindrical, and spherical options, including advanced features.

Run:
    pip install -r requirements.txt
    python main.py
"""
import sys
import os
import traceback
import math

from PySide6.QtCore import Qt, QThread, Signal, QSize, QLocale
from PySide6.QtGui import QPixmap, QImage, QIcon, QDragEnterEvent, QDropEvent, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QFileDialog,
    QVBoxLayout, QHBoxLayout, QGridLayout, QDoubleSpinBox, QSpinBox,
    QCheckBox, QProgressBar, QGroupBox, QFrame, QSizePolicy, QMessageBox,
    QSlider, QComboBox, QSplitter, QScrollArea
)
import numpy as np
from PIL import Image

import core

APP_TITLE = "Lithophane Studio"
_NUMERIC_LOCALE = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)

# ====================== TRANSLATIONS ======================
TR = {
    # Headers
    "app_subtitle": {
        "ar": "حوّل أي صورة إلى لوحة إضاءة ليثوفين ثلاثية الأبعاد جاهزة للطباعة",
        "en": "Turn any photo into a 3D-printable lithophane light panel",
    },
    
    # Previews
    "section_original": {"ar": "الصورة الأصلية", "en": "Original Image"},
    "section_heightmap": {"ar": "معاينة خريطة الإضاءة", "en": "Heightmap Preview"},
    "drop_placeholder": {"ar": "اسحب صورة هنا\nأو اضغط الزر", "en": "Drag image here\nor click button"},
    "heightmap_placeholder": {"ar": "ستظهر بعد التوليد", "en": "Will appear after generation"},
    "pick_button": {"ar": "📂  اختيار صورة", "en": "📂  Choose Image"},
    
    # Status
    "status_ready": {"ar": "جاهز.", "en": "Ready."},
    "status_loaded": {"ar": "تم تحميل: {name}", "en": "Loaded: {name}"},
    "status_generated": {"ar": "تم التوليد ✔  ({v} نقطة / {f} مثلث)", "en": "Generated ✔  ({v} vertices / {f} faces)"},
    "status_error": {"ar": "خطأ أثناء التوليد", "en": "Generation error"},
    "warn_no_image": {"ar": "اختر صورة أولاً", "en": "Please choose an image first"},
    
    # Settings boxes
    "settings_title": {"ar": "⚙️  الإعدادات", "en": "⚙️  Settings"},
    
    # Image options
    "box_image_options": {"ar": "خيارات الصورة", "en": "Image Options"},
    "chk_moon_background": {"ar": "🌙 خلفية قمرية", "en": "🌙 Moon Background"},
    "chk_flip_image": {"ar": "🔄 عكس الصورة", "en": "🔄 Flip Image"},
    "chk_crop_image": {"ar": "✂️ قص الصورة", "en": "✂️ Crop Image"},
    "chk_fit_to_sphere": {"ar": "🎯 ملاءمة للكرة (4:1)", "en": "🎯 Fit to Sphere (4:1)"},
    
    # Dimensions
    "box_dimensions": {"ar": "الأبعاد (مم)", "en": "Dimensions (mm)"},
    "field_width": {"ar": "العرض", "en": "Width"},
    "field_height": {"ar": "الارتفاع", "en": "Height"},
    
    # Thickness
    "box_thickness": {"ar": "السماكة (مم)", "en": "Thickness (mm)"},
    "field_min_thick": {"ar": "الحد الأدنى", "en": "Minimum"},
    "field_max_thick": {"ar": "الحد الأقصى", "en": "Maximum"},
    "field_base_thick": {"ar": "سماكة القاعدة", "en": "Base Thickness"},
    
    # Quality & Shape
    "box_quality": {"ar": "الدقة والشكل", "en": "Resolution & Shape"},
    "field_resolution": {"ar": "الدقة (بكسل/مم)", "en": "Resolution (px/mm)"},
    "field_shape": {"ar": "الشكل", "en": "Shape"},
    "shape_flat": {"ar": "لوح مسطح", "en": "Flat Panel"},
    "shape_cylindrical": {"ar": "أسطواني", "en": "Cylindrical"},
    "shape_spherical": {"ar": "كرة ليثوفين", "en": "Lithophane Sphere"},
    
    # Sphere options
    "box_sphere": {"ar": "⚙️ خيارات الكرة", "en": "⚙️ Sphere Options"},
    "field_sphere_diameter": {"ar": "قطر الكرة (مم)", "en": "Sphere Diameter (mm)"},
    "field_sphere_wall_thickness": {"ar": "سمك الجدار (مم)", "en": "Wall Thickness (mm)"},
    "field_sphere_bottom_hole": {"ar": "فتحة القاعدة (مم)", "en": "Bottom Hole (mm)"},
    "field_sphere_top_hole": {"ar": "ثقب أعلى (مم)", "en": "Top Hole (mm)"},
    "field_sphere_angular_height": {"ar": "الارتفاع الزاوي (درجة)", "en": "Angular Height (degrees)"},
    "field_sphere_angular_width": {"ar": "العرض الزاوي (درجة)", "en": "Angular Width (degrees)"},
    
    # Cylinder options
    "box_cylinder": {"ar": "⚙️ خيارات الأسطوانة", "en": "⚙️ Cylinder Options"},
    "field_cylinder_diameter": {"ar": "القطر الخارجي (مم)", "en": "Outer Diameter (mm)"},
    "field_cylinder_height": {"ar": "الارتفاع (مم)", "en": "Height (mm)"},
    "field_cylinder_thickness": {"ar": "سمك الجدار (مم)", "en": "Wall Thickness (mm)"},
    "field_cylinder_ledge": {"ar": "قطر الحافة (مم)", "en": "Ledge Diameter (mm)"},
    
    # Buttons
    "generate_btn": {"ar": "✨  توليد نموذج STL", "en": "✨  Generate STL"},
    "export_btn": {"ar": "💾  حفظ ملف STL", "en": "💾  Save STL"},
    "calc_diameter_btn": {"ar": "📐  حساب القطر", "en": "📐  Calculate Diameter"},
    
    # Dialogs
    "choose_image_dialog": {"ar": "اختر صورة", "en": "Choose Image"},
    "save_stl_dialog": {"ar": "حفظ ملف STL", "en": "Save STL File"},
    "saved_to": {"ar": "تم الحفظ في:\n{path}", "en": "Saved to:\n{path}"},
    
    # Info
    "sphere_calc_title": {"ar": "معلومات الكرة", "en": "Sphere Information"},
    "sphere_info": {
        "ar": "القطر: {d:.1f} مم = {d_cm:.2f} سم\nالحجم: {v:.0f} سم³ = {v_l:.2f} لتر",
        "en": "Diameter: {d:.1f} mm = {d_cm:.2f} cm\nVolume: {v:.0f} cm³ = {v_l:.2f} liters",
    },
}

# ====================== WORKER THREAD ======================
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

# ====================== DROP ZONE ======================
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
        pix = QPixmap(path).scaled(310, 310, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(pix)
        self._has_image = True

# ====================== MAIN WINDOW ======================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1400, 1000)
        self.image_path = None
        self.last_result = None
        self.worker = None
        self.lang = "ar"

        self._build_ui()
        self._apply_style()
        self.retranslate_ui()

    def _build_ui(self):
        outer_scroll = QScrollArea()
        outer_scroll.setWidgetResizable(True)
        outer_scroll.setFrameShape(QFrame.NoFrame)
        outer_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setCentralWidget(outer_scroll)

        content = QWidget()
        outer_scroll.setWidget(content)
        page = QVBoxLayout(content)
        page.setContentsMargins(18, 18, 18, 18)
        page.setSpacing(12)

        # Language button
        top_bar = QHBoxLayout()
        self.lang_btn = QPushButton("🌐")
        self.lang_btn.setObjectName("langBtn")
        self.lang_btn.setFixedSize(68, 50)
        self.lang_btn.clicked.connect(self.toggle_language)
        top_bar.addStretch()
        top_bar.addWidget(self.lang_btn, alignment=Qt.AlignLeft)
        page.addLayout(top_bar)

        # Header
        title = QLabel("🖼  Lithophane Studio")
        title.setObjectName("appTitle")
        page.addWidget(title)

        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("appSubtitle")
        self.subtitle_label.setWordWrap(True)
        page.addWidget(self.subtitle_label)

        # Main layout
        top_row = QHBoxLayout()
        top_row.setSpacing(18)
        page.addLayout(top_row)

        # ===== LEFT: Image previews =====
        left = QVBoxLayout()
        left.setSpacing(12)

        previews = QHBoxLayout()
        previews.setSpacing(10)

        col1 = QVBoxLayout()
        self.section_original_label = QLabel()
        self.section_original_label.setObjectName("sectionLabel")
        col1.addWidget(self.section_original_label)
        self.drop_label = DropImageLabel()
        self.drop_label.imageDropped.connect(self.load_image)
        col1.addWidget(self.drop_label)
        previews.addLayout(col1)

        col2 = QVBoxLayout()
        self.section_heightmap_label = QLabel()
        self.section_heightmap_label.setObjectName("sectionLabel")
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
        self.status_label.setWordWrap(True)
        left.addWidget(self.status_label)

        top_row.addLayout(left, 5)

        # ===== RIGHT: Settings =====
        right = QVBoxLayout()
        right.setSpacing(12)

        self.settings_title = QLabel()
        self.settings_title.setObjectName("bigSection")
        right.addWidget(self.settings_title)

        # Image options
        self.image_options_box = QGroupBox()
        img_v = QVBoxLayout(self.image_options_box)
        self.moon_bg_check = QCheckBox()
        self.flip_image_check = QCheckBox()
        self.crop_image_check = QCheckBox()
        self.fit_to_sphere_check = QCheckBox()
        img_v.addWidget(self.moon_bg_check)
        img_v.addWidget(self.flip_image_check)
        img_v.addWidget(self.crop_image_check)
        img_v.addWidget(self.fit_to_sphere_check)
        right.addWidget(self.image_options_box)

        # Dimensions
        self.dim_box = QGroupBox()
        dim_v = QVBoxLayout(self.dim_box)
        self.width_spin, self.field_width_label = self._labeled_spin(dim_v, 20, 400, 100)
        self.height_spin, self.field_height_label = self._labeled_spin(dim_v, 20, 400, 100)
        right.addWidget(self.dim_box)

        # Thickness
        self.thick_box = QGroupBox()
        thick_v = QVBoxLayout(self.thick_box)
        self.min_thick_spin, self.field_min_thick_label = self._labeled_spin(thick_v, 0.2, 2.0, 0.6, 0.1)
        self.max_thick_spin, self.field_max_thick_label = self._labeled_spin(thick_v, 1.0, 6.0, 3.0, 0.1)
        self.base_thick_spin, self.field_base_thick_label = self._labeled_spin(thick_v, 0.0, 3.0, 0.6, 0.1)
        right.addWidget(self.thick_box)

        # Quality & Shape
        self.quality_box = QGroupBox()
        quality_v = QVBoxLayout(self.quality_box)
        self.resolution_spin, self.field_resolution_label = self._labeled_spin(quality_v, 0.5, 15.0, 4.0, 0.5)
        
        shape_row = QVBoxLayout()
        shape_row.setSpacing(2)
        self.field_shape_label = QLabel()
        self.field_shape_label.setObjectName("fieldLabel")
        shape_row.addWidget(self.field_shape_label)
        self.shape_combo = QComboBox()
        self.shape_combo.addItems(["flat", "cylindrical", "spherical"])
        self.shape_combo.currentTextChanged.connect(self.on_shape_changed)
        shape_row.addWidget(self.shape_combo)
        quality_v.addLayout(shape_row)
        quality_v.addSpacing(6)
        right.addWidget(self.quality_box)

        # Sphere options
        self.sphere_box = QGroupBox()
        self.sphere_box.setVisible(False)
        sphere_v = QVBoxLayout(self.sphere_box)
        self.sphere_diameter_spin, self.field_sphere_diameter_label = self._labeled_spin(sphere_v, 30, 300, 100, 5)
        self.sphere_wall_spin, self.field_sphere_wall_label = self._labeled_spin(sphere_v, 0.5, 5.0, 1.0, 0.1)
        self.sphere_bottom_hole_spin, self.field_sphere_bottom_label = self._labeled_spin(sphere_v, 0, 30, 10, 1)
        self.sphere_top_hole_spin, self.field_sphere_top_label = self._labeled_spin(sphere_v, 0, 30, 0, 1)
        self.sphere_angular_height_spin, self.field_sphere_angular_height_label = self._labeled_spin(sphere_v, 10, 180, 90, 10)
        self.sphere_angular_width_spin, self.field_sphere_angular_width_label = self._labeled_spin(sphere_v, 10, 360, 90, 10)
        right.addWidget(self.sphere_box)

        # Cylinder options
        self.cylinder_box = QGroupBox()
        self.cylinder_box.setVisible(False)
        cyl_v = QVBoxLayout(self.cylinder_box)
        self.cylinder_diameter_spin, self.field_cylinder_diameter_label = self._labeled_spin(cyl_v, 20, 300, 70, 5)
        self.cylinder_height_spin, self.field_cylinder_height_label = self._labeled_spin(cyl_v, 10, 200, 25, 5)
        self.cylinder_thickness_spin, self.field_cylinder_thickness_label = self._labeled_spin(cyl_v, 0.5, 10, 5, 0.5)
        self.cylinder_ledge_spin, self.field_cylinder_ledge_label = self._labeled_spin(cyl_v, 20, 300, 75, 5)
        right.addWidget(self.cylinder_box)

        # Buttons
        self.calc_diameter_btn = QPushButton()
        self.calc_diameter_btn.setObjectName("calcBtn")
        self.calc_diameter_btn.clicked.connect(self.show_sphere_calculator)
        self.calc_diameter_btn.setVisible(False)
        right.addWidget(self.calc_diameter_btn)

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
        right_widget.setFixedWidth(420)
        top_row.addWidget(right_widget, 0)

        page.addStretch()

    def _labeled_spin(self, parent_layout, lo, hi, val, step=1.0):
        row = QVBoxLayout()
        row.setSpacing(2)
        lbl = QLabel()
        lbl.setObjectName("fieldLabel")
        lbl.setWordWrap(True)
        row.addWidget(lbl)
        
        spin = QDoubleSpinBox()
        spin.setLocale(_NUMERIC_LOCALE)
        spin.setRange(lo, hi)
        spin.setSingleStep(step)
        spin.setDecimals(1)
        spin.setValue(val)
        row.addWidget(spin)
        
        parent_layout.addLayout(row)
        parent_layout.addSpacing(4)
        return spin, lbl

    def _section_label(self, text, big=False):
        lbl = QLabel(text)
        lbl.setObjectName("bigSection" if big else "sectionLabel")
        return lbl

    def toggle_language(self):
        self.lang = "en" if self.lang == "ar" else "ar"
        self.retranslate_ui()

    def _get_shape_value(self):
        text = self.shape_combo.currentText()
        shape_map = {
            self._t("shape_flat"): "flat",
            self._t("shape_cylindrical"): "cylindrical",
            self._t("shape_spherical"): "spherical",
        }
        return shape_map.get(text, "flat")

    def on_shape_changed(self):
        is_spherical = self._get_shape_value() == "spherical"
        is_cylindrical = self._get_shape_value() == "cylindrical"
        self.sphere_box.setVisible(is_spherical)
        self.cylinder_box.setVisible(is_cylindrical)
        self.calc_diameter_btn.setVisible(is_spherical)

    def show_sphere_calculator(self):
        diameter_mm = self.sphere_diameter_spin.value()
        volume_mm3 = (4/3) * math.pi * (diameter_mm/2) ** 3
        volume_cm3 = volume_mm3 / 1000
        volume_liters = volume_cm3 / 1000

        message = self._t("sphere_info").format(
            d=diameter_mm,
            d_cm=diameter_mm/10,
            v=volume_cm3,
            v_l=volume_liters,
        )
        QMessageBox.information(self, self._t("sphere_calc_title"), message)

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

        self.settings_title.setText(self._t("settings_title"))
        self.image_options_box.setTitle(self._t("box_image_options"))
        self.moon_bg_check.setText(self._t("chk_moon_background"))
        self.flip_image_check.setText(self._t("chk_flip_image"))
        self.crop_image_check.setText(self._t("chk_crop_image"))
        self.fit_to_sphere_check.setText(self._t("chk_fit_to_sphere"))

        self.dim_box.setTitle(self._t("box_dimensions"))
        self.field_width_label.setText(self._t("field_width"))
        self.field_height_label.setText(self._t("field_height"))

        self.thick_box.setTitle(self._t("box_thickness"))
        self.field_min_thick_label.setText(self._t("field_min_thick"))
        self.field_max_thick_label.setText(self._t("field_max_thick"))
        self.field_base_thick_label.setText(self._t("field_base_thick"))

        self.quality_box.setTitle(self._t("box_quality"))
        self.field_resolution_label.setText(self._t("field_resolution"))
        self.field_shape_label.setText(self._t("field_shape"))
        
        current_shape_idx = self.shape_combo.currentIndex()
        self.shape_combo.clear()
        self.shape_combo.addItems([
            self._t("shape_flat"),
            self._t("shape_cylindrical"),
            self._t("shape_spherical"),
        ])
        self.shape_combo.setCurrentIndex(current_shape_idx)

        self.sphere_box.setTitle(self._t("box_sphere"))
        self.field_sphere_diameter_label.setText(self._t("field_sphere_diameter"))
        self.field_sphere_wall_label.setText(self._t("field_sphere_wall_thickness"))
        self.field_sphere_bottom_label.setText(self._t("field_sphere_bottom_hole"))
        self.field_sphere_top_label.setText(self._t("field_sphere_top_hole"))
        self.field_sphere_angular_height_label.setText(self._t("field_sphere_angular_height"))
        self.field_sphere_angular_width_label.setText(self._t("field_sphere_angular_width"))

        self.cylinder_box.setTitle(self._t("box_cylinder"))
        self.field_cylinder_diameter_label.setText(self._t("field_cylinder_diameter"))
        self.field_cylinder_height_label.setText(self._t("field_cylinder_height"))
        self.field_cylinder_thickness_label.setText(self._t("field_cylinder_thickness"))
        self.field_cylinder_ledge_label.setText(self._t("field_cylinder_ledge"))

        self.generate_btn.setText(self._t("generate_btn"))
        self.export_btn.setText(self._t("export_btn"))
        self.calc_diameter_btn.setText(self._t("calc_diameter_btn"))

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #14161c; }
            QScrollArea { background-color: #14161c; border: none; }
            QWidget { background-color: #14161c; }
            QLabel { color: #e8e8ec; font-size: 12px; }
            #appTitle { font-size: 22px; font-weight: 700; color: #ffffff; }
            #appSubtitle { font-size: 11px; color: #9a9dae; margin-bottom: 6px; }
            #sectionLabel { font-size: 12px; font-weight: 600; color: #c9cbe0; }
            #bigSection { font-size: 15px; font-weight: 700; color: #ffffff; margin-bottom: 2px; }
            #statusLabel { color: #8fd6a3; font-size: 11px; }
            #fieldLabel { font-size: 11px; color: #b7b9cc; }
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
                border-radius: 8px;
                color: #6b6f85;
            }
            QGroupBox {
                color: #d5d7e6;
                font-weight: 600;
                border: 1px solid #2a2e3a;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #181b23;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 2px;
            }
            QDoubleSpinBox, QSpinBox, QComboBox {
                background-color: #1c1f28;
                color: #ffffff;
                border: 1px solid #343a4a;
                border-radius: 5px;
                padding: 4px 6px;
                min-height: 20px;
            }
            QDoubleSpinBox:focus, QSpinBox:focus {
                border: 1px solid #6c5ce7;
            }
            QPushButton {
                background-color: #262a38;
                color: #ffffff;
                border: 1px solid #3a3f52;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #313648; }
            QPushButton:disabled { color: #63667a; background-color: #1c1f28; }
            #primaryBtn {
                background-color: #6c5ce7;
                border: none;
                padding: 10px 14px;
            }
            #primaryBtn:hover { background-color: #7d6ff0; }
            #calcBtn {
                background-color: #1c1f28;
                border: 1px solid #6c5ce7;
                color: #c9c2f9;
            }
            #calcBtn:hover { background-color: #24283a; }
            QProgressBar {
                background-color: #1c1f28;
                border: 1px solid #343a4a;
                border-radius: 5px;
                text-align: center;
                color: #ffffff;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #6c5ce7;
                border-radius: 5px;
            }
            QCheckBox { color: #d5d7e6; spacing: 6px; font-size: 11px; }
        """)

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
            invert=self.moon_bg_check.isChecked(),
            equalize=False,
            blur_smooth=self.crop_image_check.isChecked(),
            mirror_horizontal=self.flip_image_check.isChecked(),
            shape=self._get_shape_value(),
            sphere_diameter_mm=self.sphere_diameter_spin.value(),
            sphere_wall_thickness_mm=self.sphere_wall_spin.value(),
            sphere_bottom_hole_mm=self.sphere_bottom_hole_spin.value(),
            sphere_top_hole_mm=self.sphere_top_hole_spin.value(),
            sphere_angular_height=self.sphere_angular_height_spin.value(),
            sphere_angular_width=self.sphere_angular_width_spin.value(),
            cylinder_diameter_mm=self.cylinder_diameter_spin.value(),
            cylinder_height_mm=self.cylinder_height_spin.value(),
            cylinder_thickness_mm=self.cylinder_thickness_spin.value(),
            cylinder_ledge_mm=self.cylinder_ledge_spin.value(),
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
        self._heightmap_buffer = np.ascontiguousarray((heightmap * 255).astype(np.uint8))
        arr = self._heightmap_buffer
        h, w = arr.shape
        qimg = QImage(arr.data, w, h, w, QImage.Format_Grayscale8)
        pix = QPixmap.fromImage(qimg).scaled(310, 310, Qt.KeepAspectRatio, Qt.SmoothTransformation)
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
    app.setStyle("Fusion")
    app.setLayoutDirection(Qt.RightToLeft)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
