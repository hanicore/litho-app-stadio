"""Litho App — corrected interface with a real OpenGL mesh preview.

The preview displays a low-resolution mesh built by the same core algorithm used
for STL export. It is not a painted approximation: rotation, zoom, lighting and
Plane/Sphere geometry all operate on actual vertices and triangles.
"""
from __future__ import annotations

import ctypes
import math
import os
import sys
import traceback
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from OpenGL.GL import (
    GL_AMBIENT, GL_AMBIENT_AND_DIFFUSE, GL_ARRAY_BUFFER, GL_BLEND, GL_COLOR_BUFFER_BIT, GL_COLOR_MATERIAL,
    GL_CULL_FACE, GL_DEPTH_BUFFER_BIT, GL_DEPTH_TEST, GL_DIFFUSE, GL_ELEMENT_ARRAY_BUFFER, GL_EMISSION, GL_FLOAT,
    GL_FRONT_AND_BACK, GL_LEQUAL, GL_LIGHT0, GL_LIGHTING, GL_LINE_SMOOTH,
    GL_LINES, GL_LIGHT_MODEL_AMBIENT, GL_MODELVIEW, GL_NORMALIZE, GL_ONE_MINUS_SRC_ALPHA, GL_POSITION,
    GL_PROJECTION, GL_SHININESS, GL_SPECULAR, GL_SRC_ALPHA, GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER, GL_TEXTURE_MIN_FILTER, GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T, GL_TRIANGLES, GL_UNPACK_ALIGNMENT, GL_UNSIGNED_BYTE,
    GL_UNSIGNED_INT, GL_VERTEX_ARRAY, GL_NORMAL_ARRAY, GL_TEXTURE_COORD_ARRAY,
    GL_LINEAR, GL_CLAMP_TO_EDGE, GL_RGB, GL_RGBA, GL_STATIC_DRAW,
    glBegin, glBlendFunc, glClear, glClearColor, glColor3f, glColor4f, glColorMaterial,
    glDisable, glEnable, glEnd, glFrontFace, glLightModelfv, glLightfv,
    glLineWidth, glLoadIdentity, glMaterialfv, glMatrixMode, glNormal3f, glFrustum,
    glPixelStorei, glRotatef, glScalef, glTexCoord2f, glTexImage2D,
    glTexParameteri, glTranslatef, glVertex3f, glViewport, glDepthFunc,
    glGenTextures, glBindTexture, glEnableClientState, glDisableClientState,
    glVertexPointer, glNormalPointer, glTexCoordPointer, glDrawElements, glDrawArrays,
    glGenBuffers, glBindBuffer, glBufferData, glDeleteBuffers,
)
from PySide6.QtCore import QLocale, QPointF, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPixmap, QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QColorDialog, QComboBox, QDialog, QDoubleSpinBox,
    QFileDialog, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSlider,
    QStyle, QToolButton, QVBoxLayout, QWidget,
)

import core

APP_TITLE = "Litho App"
NUMERIC_LOCALE = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)

# Static interface strings. Dynamic status text is routed through MainWindow._tr.
EN_TO_AR = {
    "IMAGE": "الصورة", "DIMENSIONS": "الأبعاد", "PLANE PARAMETERS": "إعدادات اللوح",
    "MODEL QUALITY": "جودة النموذج", "3D PREVIEW": "معاينة ثلاثية الأبعاد", "LIVE MESH": "شبكة مباشرة",
    "LIGHTING": "الإضاءة", "MODEL PREVIEW": "معاينة النموذج", "IMAGE OPTIONS": "خيارات الصورة",
    "PREVIEW DETAILS": "تفاصيل المعاينة", "PLANE LITHOPHANE": "ليثوفين لوح",
    "Width": "العرض", "Height": "الارتفاع", "Min Thick": "أقل سماكة", "Max Thick": "أعلى سماكة",
    "Base thickness": "سماكة القاعدة", "Forward relief": "عمق البروز الأمامي",
    "Image relief": "تضاريس الصورة", "Relief depth": "عمق الحفر/البروز",
    "Engrave": "حفر", "Raise": "بروز",
    "Target resolution": "دقة الهدف", "Print pixel pitch": "مسافة بكسل الطباعة",
    "Crop to fit": "قص لملاءمة اللوح", "Flip Horizontal": "عكس أفقي",
    "Match source-image detail": "مطابقة تفاصيل الصورة الأصلية", "Lock image ratio": "قفل نسبة الصورة",
    "Brightness": "السطوع", "Contrast": "التباين", "Intensity": "الشدة", "Nightlight": "إضاءة خلفية",
    "Backlight Preview": "معاينة الإضاءة الخلفية", "Preview mode": "وضع المعاينة",
    "Lightbox": "صندوق الإضاءة", "Studio": "الاستوديو",
    "Color": "اللون", "Gamma": "غاما", "Auto contrast": "تباين تلقائي", "Smooth detail": "تنعيم التفاصيل",
    "Mirror for printing": "عكس للطباعة", "Invert image": "عكس الصورة", "Upload Image": "رفع صورة",
    "Change Image": "تغيير الصورة", "✦  Generate Model": "✦  إنشاء النموذج", "⇩  Export STL": "⇩  تصدير STL",
    "No image selected": "لم يتم اختيار صورة", "Ready": "جاهز", "No model dimensions yet": "لا توجد أبعاد للنموذج بعد",
    "Synchronized mesh": "شبكة متزامنة", "JPG, PNG, WEBP": "JPG، PNG، WEBP",
}
AR_TO_EN = {value: key for key, value in EN_TO_AR.items()}


class GenerateWorker(QThread):
    progress = Signal(int, str)
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, params):
        super().__init__()
        self.params = params

    def run(self):
        try:
            self.finished_ok.emit(core.generate_lithophane(
                progress_cb=lambda value, text: self.progress.emit(value, text),
                **self.params,
            ))
        except Exception as exc:
            self.failed.emit(f"{exc}\n\n{traceback.format_exc()}")


class PreviewWorker(QThread):
    """Prepare a live preview off the UI thread; stale results are discarded."""
    ready = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, request_id, params):
        super().__init__()
        self.request_id = request_id
        # Values are copied before the thread starts, so UI widgets are never
        # read from the worker thread.
        self.params = dict(params)

    def _cancelled(self):
        return self.isInterruptionRequested()

    def run(self):
        try:
            params = self.params
            texture_columns = max(16, int(params["width_mm"] * params["px_per_mm"]))
            texture_rows = max(16, int(params["height_mm"] * params["px_per_mm"]))
            geometry_px_per_mm = min(float(params["px_per_mm"]), 2.5)
            columns = max(16, int(params["width_mm"] * geometry_px_per_mm))
            rows = max(16, int(params["height_mm"] * geometry_px_per_mm))
            image_options = dict(
                invert=params["invert"], equalize=params["equalize"],
                blur_smooth=params["blur_smooth"], mirror_horizontal=params["mirror_horizontal"],
                crop_to_fit=params["crop_to_fit"], brightness=params["brightness"],
                contrast=params["contrast"], gamma=params["gamma"],
            )
            # The preview texture preserves the visible photograph's own aspect
            # ratio. A soft extension fills unused panel space, while the STL
            # heightmap below retains its independent crop/print policy.
            texture_heightmap = core.image_to_heightmap(
                params["image_path"], texture_columns, texture_rows,
                contain_full_image=True, **image_options
            )
            if self._cancelled():
                return
            heightmap = core.image_to_heightmap(params["image_path"], columns, rows, **image_options)
            if self._cancelled():
                return
            thickness = core.heightmap_to_thickness(
                heightmap, params["min_thickness_mm"], params["max_thickness_mm"]
            )
            if self._cancelled():
                return
            vertices, faces = core.build_mesh(
                thickness, params["width_mm"], params["height_mm"], params["base_thickness_mm"],
                params["curve_degrees"], 0.0, params["shape"],
                forward_relief_mm=params["forward_relief_mm"],
            )
            if self._cancelled():
                return
            self.ready.emit(self.request_id, {
                "vertices": vertices, "faces": faces,
                "heightmap": heightmap,
                "texture_heightmap": texture_heightmap,
                "columns": columns, "rows": rows,
                "texture_columns": texture_columns, "texture_rows": texture_rows,
                "params": params,
            })
        except Exception as exc:
            if not self._cancelled():
                self.failed.emit(self.request_id, f"{exc}\n\n{traceback.format_exc()}")


class Toggle(QCheckBox):
    """Small switch with the same geometry in every card."""
    def __init__(self, checked=False):
        super().__init__()
        self.setChecked(checked)
        self.setText("")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(38, 22)
        self.toggled.connect(self.update)

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        track = self.rect().adjusted(1, 3, -1, -3)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#5966ee") if self.isChecked() else QColor("#343b4c"))
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        knob = track.height() - 3
        x = track.right() - knob - 2 if self.isChecked() else track.left() + 2
        painter.setBrush(QColor("#ffffff") if self.isChecked() else QColor("#aab1c0"))
        painter.drawEllipse(int(x), int(track.top() + 1.5), knob, knob)


class Stepper(QFrame):
    valueChanged = Signal(float)

    def __init__(self, minimum, maximum, value, step=1.0, decimals=1):
        super().__init__()
        self.setObjectName("stepper")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        self.minus = QToolButton(text="−")
        self.minus.setObjectName("stepButton")
        self.plus = QToolButton(text="+")
        self.plus.setObjectName("stepButton")
        for button in (self.minus, self.plus):
            button.setCursor(Qt.PointingHandCursor)
            button.setFixedSize(27, 29)
        self.spin = QDoubleSpinBox()
        self.spin.setObjectName("numericValue")
        self.spin.setLocale(NUMERIC_LOCALE)
        self.spin.setRange(minimum, maximum)
        self.spin.setSingleStep(step)
        self.spin.setDecimals(decimals)
        self.spin.setValue(value)
        self.spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.spin.setAlignment(Qt.AlignCenter)
        self.spin.setFixedSize(56, 29)
        self.minus.clicked.connect(lambda: self.spin.setValue(self.spin.value() - step))
        self.plus.clicked.connect(lambda: self.spin.setValue(self.spin.value() + step))
        self.spin.valueChanged.connect(self.valueChanged.emit)
        layout.addWidget(self.minus)
        layout.addWidget(self.spin)
        layout.addWidget(self.plus)

    def value(self):
        return self.spin.value()

    def setValue(self, value):
        self.spin.setValue(value)

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self.minus.setEnabled(enabled)
        self.plus.setEnabled(enabled)
        self.spin.setEnabled(enabled)


class FieldRow(QWidget):
    """A single baseline used throughout the sidebars for visual rhythm."""
    def __init__(self, label, minimum, maximum, value, step=1.0, decimals=1, unit="mm"):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(7)
        self.caption = QLabel(label)
        self.caption.setObjectName("fieldCaption")
        self.unit = QLabel(unit)
        self.unit.setObjectName("fieldUnit")
        self.stepper = Stepper(minimum, maximum, value, step, decimals)
        layout.addWidget(self.caption, 1)
        layout.addWidget(self.unit)
        layout.addWidget(self.stepper)

    @property
    def valueChanged(self):
        return self.stepper.valueChanged

    def value(self):
        return self.stepper.value()

    def setValue(self, value):
        self.stepper.setValue(value)

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self.caption.setEnabled(enabled)
        self.unit.setEnabled(enabled)
        self.stepper.setEnabled(enabled)

    def set_label(self, text):
        self.caption.setText(text)


class SliderField(QWidget):
    valueChanged = Signal(int)

    def __init__(self, label, value, minimum=0, maximum=100, formatter=None):
        super().__init__()
        self.formatter = formatter or (lambda v: f"{v}%")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 5)
        layout.setSpacing(4)
        header = QHBoxLayout()
        self.title = QLabel(label)
        self.title.setObjectName("sliderCaption")
        self.value_label = QLabel()
        self.value_label.setObjectName("sliderNumber")
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.value_label)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(value)
        self.slider.setCursor(Qt.PointingHandCursor)
        self.slider.valueChanged.connect(self._changed)
        self._changed(value)
        layout.addLayout(header)
        layout.addWidget(self.slider)

    def _changed(self, value):
        self.value_label.setText(self.formatter(value))
        self.valueChanged.emit(value)

    def value(self):
        return self.slider.value()

    def set_label(self, text):
        self.title.setText(text)


class Section(QFrame):
    def __init__(self, title, icon):
        super().__init__()
        self.setObjectName("section")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(13, 11, 13, 12)
        layout.setSpacing(7)
        title_row = QHBoxLayout()
        mark = QLabel(icon)
        mark.setObjectName("sectionIcon")
        self.title_label = QLabel(title)
        self.title_label.setObjectName("sectionTitle")
        rule = QFrame()
        rule.setObjectName("sectionRule")
        rule.setFrameShape(QFrame.HLine)
        title_row.addWidget(mark)
        title_row.addWidget(self.title_label)
        title_row.addWidget(rule, 1)
        layout.addLayout(title_row)
        self.content = layout

    def set_title(self, title):
        self.title_label.setText(title)

    def add(self, widget):
        self.content.addWidget(widget)

    def add_layout(self, layout):
        self.content.addLayout(layout)


class MeshPreview(QOpenGLWidget):
    """OpenGL renderer for the real preview mesh built by core.build_mesh."""
    viewChanged = Signal()

    def __init__(self, small=False):
        super().__init__()
        self.small = small
        self.setObjectName("meshPreview")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.OpenHandCursor)
        self.vertices = None
        self.faces = None
        self.physical_span_mm = None
        self.preview_scale_per_mm = None
        self.rows = 0
        self.cols = 0
        self.top_face_count = 0
        self.normals = None
        self.vertex_tones = None
        self.vertex_normals = None
        self.texture_coords = None
        self.image_surface = "inner"
        self.texture_image = None
        self.texture_id = None
        self.texture_dirty = False
        self.studio_texture_image = None
        self.studio_texture_id = None
        self.studio_texture_dirty = False
        # Buffer objects keep vertex and index memory stable on every driver.
        # The old client-array path could show diagonal seams on some OpenGL
        # implementations when a large temporary NumPy index array was drawn.
        self.vertex_buffer = None
        self.normal_buffer = None
        self.texcoord_buffer = None
        self.index_buffer = None
        self.surface_vertex_buffer = None
        self.surface_texcoord_buffer = None
        self.surface_vertex_count = 0
        self.mesh_buffer_dirty = False
        self.base_thickness_mm = 0.6
        self.forward_relief_mm = 0.0
        self.min_thickness_mm = 0.8
        self.max_thickness_mm = 3.0
        self.yaw = 0.0
        self.pitch = 0.0
        self.distance = 8.2
        self.pan_x = 0.0
        self.pan_y = 0.0
        self._fit_pending = True
        self._auto_fit = True
        self._last_pos = None
        self.brightness = 75
        self.contrast = 60
        self.night_enabled = True
        self.night_intensity = 80
        self.light_color = QColor("#fff0bd")
        # Lightbox prioritizes transmitted image detail. Studio uses the same
        # mesh but a neutral, angled material light to inspect its geometry.
        self.presentation_mode = "lightbox"
        self.setMinimumHeight(190 if small else 500)

    def set_mesh(self, vertices, faces, grid_shape, image_path, heightmap=None, spherical=False,
                 forward_relief_mm=0.0, texture_heightmap=None, min_thickness_mm=0.8,
                 max_thickness_mm=3.0, base_thickness_mm=0.6):
        vertices = np.asarray(vertices, dtype=np.float32)
        faces = np.asarray(faces, dtype=np.int32)
        self.forward_relief_mm = float(forward_relief_mm)
        self.base_thickness_mm = max(0.0, float(base_thickness_mm))
        self.min_thickness_mm = float(min_thickness_mm)
        self.max_thickness_mm = max(self.min_thickness_mm + 1e-5, float(max_thickness_mm))
        if len(vertices) == 0 or len(faces) == 0:
            return
        # The preview must display the exact generated geometry. Earlier builds
        # enlarged front relief only on screen, which made the preview differ
        # from the exported STL.
        center = (vertices.min(axis=0) + vertices.max(axis=0)) / 2
        span = np.ptp(vertices, axis=0)
        # One uniform coefficient is applied to X, Y and Z. Consequently every
        # ratio in the visible mesh (width : height : depth) is exactly the
        # physical ratio of the STL, while the camera alone performs fitting.
        scale = 4.15 / max(1e-6, float(span.max()))
        self.physical_span_mm = span.copy()
        self.preview_scale_per_mm = scale
        self.vertices = np.ascontiguousarray((vertices - center) * scale, dtype=np.float32)
        self.faces = np.ascontiguousarray(faces, dtype=np.uint32)
        self.image_surface = "outer" if spherical else "inner"
        self.rows, self.cols = grid_shape
        self.top_face_count = max(0, (self.rows - 1) * (self.cols - 1) * 2)
        # Map the same processed heightmap that produced the geometry onto the
        # front face as a material tone. This makes the subject visible in the
        # preview even on GPUs that do not support legacy texture calls.
        if heightmap is not None and np.asarray(heightmap).shape == (self.rows, self.cols):
            # Mesh rows advance upward in OpenGL while image rows advance
            # downward, so reverse the source rows to preserve photo orientation.
            self.vertex_tones = np.asarray(heightmap, dtype=np.float32)[::-1, :].reshape(-1)
            self._set_studio_texture(np.asarray(heightmap, dtype=np.float32))
        else:
            self.vertex_tones = np.full(self.rows * self.cols, 0.72, dtype=np.float32)
        triangles = self.vertices[self.faces]
        normal = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        length = np.linalg.norm(normal, axis=1, keepdims=True)
        self.normals = normal / np.maximum(length, 1e-8)
        # Vectorized averaging avoids Python loops over hundreds of thousands
        # of faces and keeps control changes responsive.
        self.vertex_normals = np.zeros_like(self.vertices, dtype=np.float32)
        np.add.at(self.vertex_normals, self.faces[:, 0], self.normals)
        np.add.at(self.vertex_normals, self.faces[:, 1], self.normals)
        np.add.at(self.vertex_normals, self.faces[:, 2], self.normals)
        vertex_length = np.linalg.norm(self.vertex_normals, axis=1, keepdims=True)
        self.vertex_normals /= np.maximum(vertex_length, 1e-8)
        grid_count = max(1, self.rows * self.cols)
        base_indices = np.arange(len(self.vertices), dtype=np.int32) % grid_count
        texture_rows = base_indices // self.cols
        texture_cols = base_indices % self.cols
        self.texture_coords = np.ascontiguousarray(np.column_stack((
            texture_cols / max(1, self.cols - 1),
            1.0 - texture_rows / max(1, self.rows - 1),
        )).astype(np.float32, copy=False))
        # The textured face is expanded once into independent triangle vertices.
        # This removes driver-dependent client/index interpretation from the
        # image surface, where any bad index seam would be highly visible.
        visible_faces = self.faces[:self.top_face_count].reshape(-1)
        self.surface_vertices = np.ascontiguousarray(self.vertices[visible_faces], dtype=np.float32)
        self.surface_texcoords = np.ascontiguousarray(self.texture_coords[visible_faces], dtype=np.float32)
        self.surface_vertex_count = len(self.surface_vertices)
        self.mesh_buffer_dirty = True
        # Simulate transmitted light through the printed material rather than
        # merely drawing the source photo. Bright image areas map to thin STL
        # regions and therefore glow more; dark regions are thicker and absorb
        # more of the warm backlight. The same processed heightmap drives STL,
        # geometry and this visual transmittance map.
        texture_map = texture_heightmap if texture_heightmap is not None else heightmap
        if texture_map is not None:
            self._texture_heightmap = np.asarray(texture_map, dtype=np.float32).copy()
            self._set_transmission_texture(self._texture_heightmap)
        if self._fit_pending:
            self.reset_camera()
        self.update()

    def clear_mesh(self):
        self.vertices = None
        self.faces = None
        self.update()

    def request_fit(self):
        """Fit the next mesh result whenever a new image is loaded."""
        # Keep the request pending until the new geometry has arrived; fitting
        # the old mesh here would use the wrong aspect ratio for the new photo.
        self._fit_pending = True
        self._auto_fit = True

    def _fit_distance(self):
        if self.vertices is None:
            return 8.2
        span = np.ptp(self.vertices, axis=0)
        half_width = max(0.01, float(span[0]) * 0.5)
        half_height = max(0.01, float(span[1]) * 0.5)
        aspect = max(0.20, self.width() / max(1, self.height()))
        fov = math.radians(32.0 if not self.small else 36.0)
        tangent = math.tan(fov * 0.5)
        # Preserve clean margin around all four edges in the straight photo view.
        vertical = half_height / tangent
        horizontal = half_width / (tangent * aspect)
        return max(3.0, (max(vertical, horizontal) + float(span[2]) * 0.5) / 0.86)

    def reset_camera(self):
        # A front-on, uncropped photo is the default; drag and the wheel retain
        # full interactive 3D control afterwards.
        self.yaw, self.pitch = 0.0, 0.0
        self.distance, self.pan_x, self.pan_y = self._fit_distance(), 0.0, 0.0
        self._fit_pending = False
        self._auto_fit = True
        self.update()

    def set_presentation_mode(self, mode):
        mode = "studio" if mode == "studio" else "lightbox"
        if self.presentation_mode == mode:
            return
        self.presentation_mode = mode
        self.update()

    def set_lighting(self, brightness, contrast, night_enabled, night_intensity, color):
        changed = (self.brightness, self.contrast, self.night_enabled, self.night_intensity, self.light_color) != (
            brightness, contrast, night_enabled, night_intensity, color
        )
        self.brightness = brightness
        self.contrast = contrast
        self.night_enabled = night_enabled
        self.night_intensity = night_intensity
        self.light_color = color
        if changed and self.texture_image is not None:
            # Rebuild the apparent transmitted-light texture immediately; no
            # mesh or STL calculation is needed for environment-only changes.
            self._rebuild_transmission_texture()
        self.update()

    def _rebuild_transmission_texture(self):
        # Reuse the retained high-detail heightmap if it is available.
        if getattr(self, "_texture_heightmap", None) is None:
            return
        self._set_transmission_texture(self._texture_heightmap)

    def _set_transmission_texture(self, texture_map):
        photo = np.clip(np.asarray(texture_map, dtype=np.float32), 0.0, 1.0)
        standard_range = self.max_thickness_mm - self.min_thickness_mm
        # Image relief changes the outer sculpted surface. The transmitted
        # image must keep the lithophane's tonal convention in both modes:
        # bright source pixels stay brighter under backlight and dark pixels
        # stay darker, regardless of whether that detail is engraved or raised.
        thickness = self.min_thickness_mm + (1.0 - photo) * standard_range
        transmission = np.exp(-0.75 * thickness)
        backlight = self.night_intensity / 100.0 if self.night_enabled else 0.06
        exposure = (0.60 + (self.brightness / 100.0) * 1.55) * (0.35 + backlight * 1.60)
        signal = transmission * exposure
        # Preserve the delicate mid-tones of the photo while a soft shoulder
        # stops thin regions from becoming a flat white glare.
        glow = signal / (1.0 + 0.20 * signal)
        glow = np.power(np.clip(glow, 0.0, 1.0), 0.70)
        contrast = 0.65 + (self.contrast / 100.0) * 0.65
        glow = np.clip(0.5 + (glow - 0.5) * contrast, 0.0, 1.0)
        light = np.array((self.light_color.redF(), self.light_color.greenF(), self.light_color.blueF()), dtype=np.float32)
        ivory = np.array((0.99, 0.93, 0.79), dtype=np.float32)
        rgb = np.clip(glow[..., None] * (0.35 * ivory + 0.65 * light), 0.0, 1.0)
        rgba = np.empty((*rgb.shape[:2], 4), dtype=np.uint8)
        rgba[..., :3] = np.clip(rgb * 255.0, 0.0, 255.0).astype(np.uint8)
        rgba[..., 3] = 255
        pixels = np.ascontiguousarray(rgba)
        self.texture_image = QImage(
            pixels.data, pixels.shape[1], pixels.shape[0], pixels.shape[1] * 4,
            QImage.Format.Format_RGBA8888,
        ).copy()
        self.texture_dirty = True

    def initializeGL(self):
        glClearColor(0.012, 0.018, 0.030, 1.0)
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LEQUAL)
        glEnable(GL_NORMALIZE)
        glEnable(GL_LINE_SMOOTH)
        # The STL mesh intentionally contains both exterior faces. Keep both
        # visible in the interactive preview so the lit image side is never
        # hidden solely by winding direction as the user rotates the model.
        glDisable(GL_CULL_FACE)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def resizeGL(self, width, height):
        glViewport(0, 0, max(1, width), max(1, height))
        if self._auto_fit and self.vertices is not None:
            self.distance = self._fit_distance()

    def _set_studio_texture(self, heightmap):
        """Build a neutral tonal material map for geometric Studio inspection."""
        photo = np.clip(np.asarray(heightmap, dtype=np.float32), 0.0, 1.0)
        grad_y, grad_x = np.gradient(photo)
        edge = np.clip(np.hypot(grad_x, grad_y) * 2.2, 0.0, 0.22)
        tone = np.clip(0.34 + photo * 0.50 - edge, 0.16, 0.88)
        rgba = np.empty((*tone.shape, 4), dtype=np.uint8)
        rgba[..., 0] = (tone * 0.88 * 255.0).astype(np.uint8)
        rgba[..., 1] = (tone * 0.93 * 255.0).astype(np.uint8)
        rgba[..., 2] = (tone * 255.0).astype(np.uint8)
        rgba[..., 3] = 255
        pixels = np.ascontiguousarray(rgba)
        self.studio_texture_image = QImage(
            pixels.data, pixels.shape[1], pixels.shape[0], pixels.shape[1] * 4,
            QImage.Format.Format_RGBA8888,
        ).copy()
        self.studio_texture_dirty = True

    def _upload_qimage_texture(self, image, texture_id):
        if texture_id is None:
            texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        data = bytes(image.bits())
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, image.width(), image.height(), 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        return texture_id

    def _upload_texture(self):
        if self.texture_dirty and self.texture_image is not None:
            self.texture_id = self._upload_qimage_texture(self.texture_image, self.texture_id)
            self.texture_dirty = False
        if self.studio_texture_dirty and self.studio_texture_image is not None:
            self.studio_texture_id = self._upload_qimage_texture(self.studio_texture_image, self.studio_texture_id)
            self.studio_texture_dirty = False

    def _draw_floor(self):
        glDisable(GL_LIGHTING)
        glDisable(GL_TEXTURE_2D)
        glLineWidth(1.0)
        glColor4f(0.18, 0.25, 0.37, 0.40)
        glBegin(GL_LINES)
        for index in range(-7, 8):
            glVertex3f(index * 0.65, -3.0, -5.0)
            glVertex3f(index * 0.65, -3.0, 5.0)
            glVertex3f(-5.0, -3.0, index * 0.65)
            glVertex3f(5.0, -3.0, index * 0.65)
        glEnd()

    def _set_lights(self):
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        if self.presentation_mode == "studio":
            # Neutral three-dimensional inspection: a soft key from above-right
            # and restrained ambient fill reveal edges and relief without a
            # competing transmitted-light glow.
            glLightModelfv(GL_LIGHT_MODEL_AMBIENT, (0.11, 0.12, 0.15, 1.0))
            glLightfv(GL_LIGHT0, GL_POSITION, (4.8, 5.6, 6.5, 1.0))
            glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.88, 0.91, 1.0, 1.0))
            glLightfv(GL_LIGHT0, GL_SPECULAR, (0.34, 0.36, 0.42, 1.0))
            glMaterialfv(GL_FRONT_AND_BACK, GL_AMBIENT, (0.19, 0.21, 0.25, 1.0))
            glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE, (0.72, 0.74, 0.80, 1.0))
            glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, (0.24, 0.27, 0.32, 1.0))
            glMaterialfv(GL_FRONT_AND_BACK, GL_SHININESS, (28.0,))
            glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION, (0.0, 0.0, 0.0, 1.0))
            return
        col = self.light_color
        intensity = self.night_intensity / 100 if self.night_enabled else 0.15
        rgb = (col.redF(), col.greenF(), col.blueF())
        ambient = (0.025 + intensity * 0.10, 0.022 + intensity * 0.08, 0.030 + intensity * 0.06, 1.0)
        diffuse = tuple(min(1.0, channel * (0.35 + intensity * 0.55)) for channel in rgb) + (1.0,)
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, ambient)
        glLightfv(GL_LIGHT0, GL_POSITION, (3.5, 4.8, 5.5, 1.0))
        glLightfv(GL_LIGHT0, GL_DIFFUSE, diffuse)
        glLightfv(GL_LIGHT0, GL_SPECULAR, (0.35, 0.35, 0.35, 1.0))
        warm = (0.92, 0.76, 0.52, 1.0)
        glMaterialfv(GL_FRONT_AND_BACK, GL_AMBIENT, (0.16, 0.12, 0.08, 1.0))
        glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE, warm)
        glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, (0.07, 0.06, 0.05, 1.0))
        glMaterialfv(GL_FRONT_AND_BACK, GL_SHININESS, (10.0,))
        # The lightbox intentionally uses a small warm emission in addition to
        # the transmission texture, matching a lit printed panel.
        emissive = tuple(channel * (0.12 + intensity * 0.34) for channel in rgb) + (1.0,)
        glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION, emissive)

    def _upload_mesh_buffers(self):
        """Upload one coherent mesh snapshot while the OpenGL context is current."""
        if not self.mesh_buffer_dirty or self.vertices is None:
            return
        if self.vertex_buffer is None:
            (self.vertex_buffer, self.normal_buffer, self.texcoord_buffer, self.index_buffer,
             self.surface_vertex_buffer, self.surface_texcoord_buffer) = glGenBuffers(6)
        for buffer_id, target, data in (
            (self.vertex_buffer, GL_ARRAY_BUFFER, self.vertices),
            (self.normal_buffer, GL_ARRAY_BUFFER, self.vertex_normals),
            (self.texcoord_buffer, GL_ARRAY_BUFFER, self.texture_coords),
            (self.index_buffer, GL_ELEMENT_ARRAY_BUFFER, self.faces.reshape(-1)),
            (self.surface_vertex_buffer, GL_ARRAY_BUFFER, self.surface_vertices),
            (self.surface_texcoord_buffer, GL_ARRAY_BUFFER, self.surface_texcoords),
        ):
            glBindBuffer(target, buffer_id)
            glBufferData(target, data.nbytes, data, GL_STATIC_DRAW)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
        self.mesh_buffer_dirty = False

    def _draw_triangles(self, start, end, textured):
        if start >= end:
            return
        texture_id = self.texture_id if self.presentation_mode == "lightbox" else self.studio_texture_id
        use_texture = bool(textured and texture_id is not None)
        if use_texture:
            # Lightbox encodes transmitted light in its texture. Studio instead
            # modulates a neutral material map with its angled geometry light.
            if self.presentation_mode == "lightbox":
                glDisable(GL_LIGHTING)
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, texture_id)
            glColor3f(1.0, 1.0, 1.0)
        else:
            glDisable(GL_TEXTURE_2D)
            if not textured:
                if self.presentation_mode == "studio":
                    glColor3f(0.74, 0.78, 0.88)
                else:
                    glColor3f(0.42, 0.33, 0.22)
        glEnableClientState(GL_VERTEX_ARRAY)
        if use_texture:
            glEnableClientState(GL_TEXTURE_COORD_ARRAY)
            glBindBuffer(GL_ARRAY_BUFFER, self.surface_vertex_buffer)
            glVertexPointer(3, GL_FLOAT, 0, ctypes.c_void_p(0))
            glBindBuffer(GL_ARRAY_BUFFER, self.surface_texcoord_buffer)
            glTexCoordPointer(2, GL_FLOAT, 0, ctypes.c_void_p(0))
            glDrawArrays(GL_TRIANGLES, 0, self.surface_vertex_count)
            glDisableClientState(GL_TEXTURE_COORD_ARRAY)
            glEnable(GL_LIGHTING)
        else:
            glEnableClientState(GL_NORMAL_ARRAY)
            glBindBuffer(GL_ARRAY_BUFFER, self.vertex_buffer)
            glVertexPointer(3, GL_FLOAT, 0, ctypes.c_void_p(0))
            glBindBuffer(GL_ARRAY_BUFFER, self.normal_buffer)
            glNormalPointer(GL_FLOAT, 0, ctypes.c_void_p(0))
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.index_buffer)
            index_offset = start * 3 * np.dtype(np.uint32).itemsize
            glDrawElements(GL_TRIANGLES, (end - start) * 3, GL_UNSIGNED_INT, ctypes.c_void_p(index_offset))
            glDisableClientState(GL_NORMAL_ARRAY)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
        glDisableClientState(GL_VERTEX_ARRAY)

    def paintGL(self):
        if self.presentation_mode == "studio":
            glClearColor(0.055, 0.068, 0.095, 1.0)
        else:
            glClearColor(0.012, 0.018, 0.030, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        near, far = 0.1, 100.0
        fov = math.radians(32.0 if not self.small else 36.0)
        top = math.tan(fov / 2.0) * near
        right = top * self.width() / max(1, self.height())
        glFrustum(-right, right, -top, top, near, far)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        # Define lights in camera space before model rotations. Studio lighting
        # then remains on the same side of the viewer as the user rotates the
        # panel, rather than rotating behind the model and turning it black.
        self._set_lights()
        glTranslatef(self.pan_x, self.pan_y, -self.distance)
        glRotatef(self.pitch, 1.0, 0.0, 0.0)
        glRotatef(self.yaw, 0.0, 1.0, 0.0)
        # Keep a dark studio environment so the transmitted-light image is
        # the visual focus rather than a CAD-style floor grid.
        if self.vertices is None:
            return
        self._upload_texture()
        self._upload_mesh_buffers()
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        top_end = min(self.top_face_count, len(self.faces))
        bottom_end = min(self.top_face_count * 2, len(self.faces))
        # Both modes use the same mesh. Lightbox applies the transmitted image;
        # Studio applies a neutral tonal material map under directional light.
        photo_textured = True
        if self.image_surface == "outer":
            self._draw_triangles(0, top_end, textured=False)
            self._draw_triangles(bottom_end, len(self.faces), textured=False)
            self._draw_triangles(top_end, bottom_end, textured=photo_textured)
        else:
            # Draw the opaque back and perimeter first. The transmission layer
            # is last in Lightbox; Studio draws the identical mesh untextured.
            self._draw_triangles(top_end, len(self.faces), textured=False)
            self._draw_triangles(0, top_end, textured=photo_textured)
        glDisable(GL_TEXTURE_2D)
        glDisable(GL_COLOR_MATERIAL)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._last_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._last_pos is not None:
            delta = event.position() - self._last_pos
            self._auto_fit = False
            self.yaw += delta.x() * 0.55
            self.pitch = max(-78, min(78, self.pitch + delta.y() * 0.45))
            self._last_pos = event.position()
            self.update()
            self.viewChanged.emit()

    def mouseReleaseEvent(self, event):
        self._last_pos = None
        self.setCursor(Qt.OpenHandCursor)

    def wheelEvent(self, event):
        self._auto_fit = False
        self.distance = max(3.0, min(24.0, self.distance - event.angleDelta().y() / 650.0))
        self.update()
        self.viewChanged.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1420, 910)
        self.setMinimumSize(1160, 720)
        self.image_path = None
        self.image_ratio = 0.8
        self._ratio_updating = False
        self.mode = "plane"
        self.language = "en"
        self.preview_mode = "lightbox"
        self.translatable_toggle_captions = []
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.refresh_live_mesh)
        self.worker = None
        self._preview_request_id = 0
        self._preview_workers = {}
        self._exporting = False
        self.output_path = str(Path(__file__).with_name("_litho_export.stl"))
        self.light_color = QColor("#fff0bd")
        self._build()
        self._apply_style()
        self.update_lights()
        self._set_mode("plane")

    def closeEvent(self, event):
        # Avoid destroying a live QThread if the user closes the application
        # while a preview or a full-resolution STL is still being prepared.
        for worker in self._preview_workers.values():
            worker.requestInterruption()
        for worker in list(self._preview_workers.values()):
            worker.wait(3000)
        if self.worker is not None and self.worker.isRunning():
            self.worker.wait(5000)
        super().closeEvent(event)

    # --------- layout ---------
    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        page = QVBoxLayout(root)
        page.setContentsMargins(0, 0, 0, 0)
        page.setSpacing(0)
        page.addWidget(self._header())

        content = QHBoxLayout()
        content.setContentsMargins(15, 14, 15, 12)
        content.setSpacing(14)
        page.addLayout(content, 1)

        self.left_scroll, self.left = self._sidebar()
        self.left_scroll.setFixedWidth(306)
        content.addWidget(self.left_scroll)
        self._build_left()

        content.addWidget(self._center(), 1)

        self.right_scroll, self.right = self._sidebar()
        self.right_scroll.setFixedWidth(306)
        content.addWidget(self.right_scroll)
        self._build_right()

        page.addWidget(self._footer())

    def _header(self):
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(65)
        row = QHBoxLayout(header)
        row.setContentsMargins(21, 10, 20, 10)
        row.setSpacing(10)
        logo = QLabel("◈")
        logo.setObjectName("logo")
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedSize(30, 30)
        title = QLabel("Litho App")
        title.setObjectName("brand")
        row.addWidget(logo)
        row.addWidget(title)
        row.addStretch(1)
        holder = QFrame()
        holder.setObjectName("segmented")
        tabs = QHBoxLayout(holder)
        tabs.setContentsMargins(3, 3, 3, 3)
        self.plane_mode_label = QLabel("▣  PLANE LITHOPHANE")
        self.plane_mode_label.setObjectName("planeMode")
        self.plane_mode_label.setAlignment(Qt.AlignCenter)
        self.plane_mode_label.setFixedSize(256, 35)
        tabs.addWidget(self.plane_mode_label)
        row.addWidget(holder)
        row.addStretch(1)
        self.help_button = QToolButton(text="?")
        self.help_button.setObjectName("topTool")
        self.help_button.setToolTip("How to use Plane controls")
        self.help_button.setFixedSize(28, 28)
        self.help_button.clicked.connect(self.show_help)
        row.addWidget(self.help_button)
        self.settings_button = QToolButton(text="⚙")
        self.settings_button.setObjectName("topTool")
        self.settings_button.setToolTip("Choose generated STL folder")
        self.settings_button.setFixedSize(28, 28)
        self.settings_button.clicked.connect(self.choose_export_folder)
        row.addWidget(self.settings_button)
        self.language_button = QToolButton(text="🌐")
        self.language_button.setObjectName("languageButton")
        self.language_button.setToolTip("Switch to Arabic")
        self.language_button.setFixedSize(30, 30)
        self.language_button.setCursor(Qt.PointingHandCursor)
        self.language_button.clicked.connect(self.toggle_language)
        row.addWidget(self.language_button)
        return header

    def _tr(self, text):
        if self.language == "ar":
            return EN_TO_AR.get(text, text)
        return AR_TO_EN.get(text, text)

    def toggle_language(self):
        self.language = "ar" if self.language == "en" else "en"
        self.apply_language()

    def apply_language(self):
        arabic = self.language == "ar"
        self.setLayoutDirection(Qt.RightToLeft if arabic else Qt.LeftToRight)
        self.language_button.setText("🌐")
        self.language_button.setToolTip("Switch to English" if arabic else "Switch to Arabic")
        self.plane_mode_label.setText(f"▣  {self._tr('PLANE LITHOPHANE')}")
        self.help_button.setToolTip("طريقة استخدام عناصر اللوح" if arabic else "How to use Plane controls")
        self.settings_button.setToolTip("اختيار مجلد حفظ STL" if arabic else "Choose generated STL folder")
        # Translate every mapped visible label/button in-place, while file names,
        # numeric values, and model measurements stay untouched.
        for widget_type in (QLabel, QPushButton):
            for widget in self.findChildren(widget_type):
                widget.setText(self._tr(widget.text()))
        self.plane_mode_label.setText(f"▣  {self._tr('PLANE LITHOPHANE')}")
        for index in range(self.relief_mode.count()):
            key = "Engrave" if self.relief_mode.itemData(index) == "engrave" else "Raise"
            self.relief_mode.setItemText(index, self._tr(key))
        for index in range(self.preview_mode_selector.count()):
            key = "Lightbox" if self.preview_mode_selector.itemData(index) == "lightbox" else "Studio"
            self.preview_mode_selector.setItemText(index, self._tr(key))
        self._update_presentation_badge()
        self.relief_mode.setToolTip(
            "اختر الحفر أو البروز للصورة" if arabic else "Choose engraved or raised image detail"
        )
        self.guide_text.setText(
            "هذه معاينة لشبكة النموذج: اسحب للدوران واستخدم عجلة الفأرة للتقريب."
            if arabic else "This is the real model mesh: drag to rotate and use the mouse wheel to zoom."
        )
        self.update_summary()
        self._update_backlight_ui()
        if self.image_path:
            # Changing labels and direction must stay instant; queue the model
            # refresh after the UI has completed its relayout.
            self.schedule_preview(delay_ms=90)
        else:
            self.footer_status.setText("جاهز" if arabic else "Ready")

    def show_help(self):
        if self.language == "ar":
            title = "طريقة استخدام ليثوفين اللوح"
            body = (
                "• رفع صورة يختار الصورة المصدر، ويتحول إلى تغيير الصورة بعد الاختيار.\n"
                "• اختر حفر أو بروز من قائمة تضاريس الصورة.\n"
                "• عمق الحفر/البروز يحدد فرق العمق من 0 حتى 10 مم.\n"
                "• دقة الهدف تُقيَّد تلقائيًا بدقة الصورة ومسافة بكسل الطباعة وأمان الشبكة.\n"
                "• وضع صندوق الإضاءة يوضح الصورة المضيئة، بينما وضع الاستوديو يوضح الحفر والبروز والحواف.\n"
                "• اسحب داخل المعاينة للدوران واستخدم عجلة الفأرة للتقريب، ثم أنشئ النموذج وصدّر STL."
            )
        else:
            title = "Plane Lithophane controls"
            body = (
                "• Upload Image selects the source picture; it changes to Change Image after selection.\n"
                "• Choose Engrave or Raise under Image relief.\n"
                "• Relief depth sets the image depth from 0 to 10 mm.\n"
                "• Target Resolution is automatically limited by image detail, print pixel pitch, and mesh safety.\n"
                "• Lightbox shows the lit image; Studio reveals relief, edges, and thickness.\n"
                "• Drag in 3D Preview to rotate, use the mouse wheel to zoom, then Generate Model and Export STL."
            )
        QMessageBox.information(self, APP_TITLE, f"{title}\n\n{body}")

    def choose_export_folder(self):
        title = "اختيار مجلد حفظ STL" if self.language == "ar" else "Choose generated STL folder"
        folder = QFileDialog.getExistingDirectory(self, title, str(Path(self.output_path).parent))
        if folder:
            self.output_path = str(Path(folder) / "lithophane_plane.stl")
            self.footer_status.setText("تم تحديث مجلد حفظ STL" if self.language == "ar" else "Generated STL folder updated")
            prefix = "سيتم حفظ STL في: " if self.language == "ar" else "Generated STL will be saved to: "
            self.generation_status.setText(f"{prefix}{self.output_path}")

    def _sidebar(self):
        scroll = QScrollArea()
        scroll.setObjectName("sidebarScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)
        holder = QWidget()
        holder.setObjectName("sidebar")
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(11)
        scroll.setWidget(holder)
        return scroll, layout

    def _build_left(self):
        image_section = Section("IMAGE", "▧")
        image_row = QHBoxLayout()
        image_row.setSpacing(10)
        self.image_thumb = QLabel("IMAGE")
        self.image_thumb.setObjectName("thumbnail")
        self.image_thumb.setAlignment(Qt.AlignCenter)
        self.image_thumb.setFixedSize(79, 96)
        image_row.addWidget(self.image_thumb)
        text = QVBoxLayout()
        text.setSpacing(4)
        self.file_label = QPushButton("No image selected")
        self.file_label.setObjectName("fileName")
        self.file_label.setFlat(True)
        self.file_label.setEnabled(False)
        self.file_label.setCursor(Qt.PointingHandCursor)
        self.file_label.setToolTip("Image details")
        self.file_label.clicked.connect(self.show_image_info)
        self.resolution_label = QLabel("JPG, PNG, WEBP")
        self.resolution_label.setObjectName("muted")
        self.image_button = QPushButton("Upload Image")
        self.image_button.setObjectName("outline")
        self.image_button.setCursor(Qt.PointingHandCursor)
        self.image_button.clicked.connect(self.pick_image)
        text.addWidget(self.file_label)
        text.addWidget(self.resolution_label)
        text.addStretch(1)
        text.addWidget(self.image_button)
        image_row.addLayout(text, 1)
        image_section.add_layout(image_row)
        self.left.addWidget(image_section)

        self.plane_section = Section("DIMENSIONS", "▣")
        self.width = FieldRow("Width", 20, 400, 120, 1, 1)
        self.height = FieldRow("Height", 20, 400, 150, 1, 1)
        self.min_thickness = FieldRow("Min Thick", 0.2, 2.0, 0.8, 0.1, 1)
        self.max_thickness = FieldRow("Max Thick", 1.0, 6.0, 3.0, 0.1, 1)
        self.width.valueChanged.connect(self._width_changed)
        self.height.valueChanged.connect(self._height_changed)
        for row in (self.width, self.height):
            self.plane_section.add(row)
        self.plane_section.add(self.min_thickness)
        self.plane_section.add(self.max_thickness)
        self.left.addWidget(self.plane_section)

        self.plane_parameters = Section("PLANE PARAMETERS", "✣")
        self.crop = Toggle(True)
        self.base = FieldRow("Base thickness", 0, 3, 0.6, 0.1, 1)
        self.relief_mode = QComboBox()
        self.relief_mode.setObjectName("reliefMode")
        self.relief_mode.addItem("Engrave", "engrave")
        self.relief_mode.addItem("Raise", "raise")
        self.relief_mode.setToolTip("Choose whether image detail is engraved or raised")
        self.relief_depth = FieldRow("Relief depth", 0.0, 10.0, 2.3, 0.1, 1)
        relief_line = QHBoxLayout()
        relief_line.setContentsMargins(0, 2, 0, 2)
        relief_label = QLabel("Image relief")
        relief_label.setObjectName("fieldCaption")
        relief_line.addWidget(relief_label)
        relief_line.addStretch()
        relief_line.addWidget(self.relief_mode)
        self.relief_mode.currentIndexChanged.connect(self._apply_relief)
        self.relief_depth.valueChanged.connect(self._apply_relief)
        self.plane_parameters.add_layout(self._toggle_line("Crop to fit", self.crop))
        self.plane_parameters.add(self.base)
        self.plane_parameters.add_layout(relief_line)
        self.plane_parameters.add(self.relief_depth)
        self.left.addWidget(self.plane_parameters)

        quality = Section("MODEL QUALITY", "◌")
        # Resolution is limited by source-image detail and a mesh safety ceiling.
        self.quality = FieldRow("Target resolution", 0.5, 12.0, 6.0, 0.5, 1, "px/mm")
        self.print_pixel_pitch = FieldRow("Print pixel pitch", 0.08, 0.60, 0.16, 0.02, 2, "mm/px")
        self.smart_sampling = Toggle(True)
        self.quality_hint = QLabel()
        self.quality_hint.setObjectName("hint")
        self.quality_hint.setWordWrap(True)
        quality.add(self.quality)
        quality.add(self.print_pixel_pitch)
        quality.add_layout(self._toggle_line("Match source-image detail", self.smart_sampling, accent=True))
        quality.add(self.quality_hint)
        self.left.addWidget(quality)
        self.generate_button = QPushButton("✦  Generate Model")
        self.generate_button.setObjectName("primary")
        self.generate_button.setCursor(Qt.PointingHandCursor)
        self.generate_button.setFixedHeight(43)
        self.generate_button.clicked.connect(self.generate)
        self.left.addWidget(self.generate_button)
        self.generation_status = QLabel("Import an image to build the live model preview.")
        self.generation_status.setObjectName("status")
        self.generation_status.setWordWrap(True)
        self.left.addWidget(self.generation_status)
        self.left.addStretch(1)
        for control in self._preview_controls():
            control.valueChanged.connect(self.schedule_preview)
        for toggle in (self.crop, self.smart_sampling):
            toggle.toggled.connect(self.schedule_preview)

    def _center(self):
        card = QFrame()
        card.setObjectName("previewCard")
        column = QVBoxLayout(card)
        column.setContentsMargins(14, 12, 14, 13)
        column.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel("3D PREVIEW")
        title.setObjectName("previewTitle")
        self.live_badge = QLabel("LIVE MESH")
        self.live_badge.setObjectName("liveBadge")
        self.presentation_badge = QLabel("LIGHTBOX")
        self.presentation_badge.setObjectName("modeBadge")
        header.addWidget(title)
        header.addWidget(self.live_badge)
        header.addWidget(self.presentation_badge)
        header.addStretch()
        for symbol, tip, action in (
            ("⟲", "Reset camera", lambda: self.preview.reset_camera()),
            ("☀", "Toggle Backlight Preview", self.toggle_backlight),
        ):
            tool = QToolButton(text=symbol)
            tool.setObjectName("previewTool")
            tool.setToolTip(tip)
            tool.setCursor(Qt.PointingHandCursor)
            tool.setFixedSize(33, 31)
            tool.clicked.connect(action)
            header.addWidget(tool)
        column.addLayout(header)
        self.preview = MeshPreview()
        self.preview.viewChanged.connect(self._preview_view_changed)
        column.addWidget(self.preview, 1)
        guide = QFrame()
        guide.setObjectName("guide")
        guide_layout = QHBoxLayout(guide)
        guide_layout.setContentsMargins(10, 6, 10, 6)
        guide_layout.addWidget(QLabel("◉"))
        self.guide_text = QLabel("هذه معاينة لشبكة النموذج: اسحب للدوران واستخدم عجلة الفأرة للتقريب.")
        self.guide_text.setObjectName("guideText")
        guide_layout.addWidget(self.guide_text)
        guide_layout.addStretch()
        column.addWidget(guide)
        return card

    def _build_right(self):
        lighting = Section("LIGHTING", "☼")
        self.preview_mode_selector = QComboBox()
        self.preview_mode_selector.setObjectName("previewMode")
        self.preview_mode_selector.addItem("Lightbox", "lightbox")
        self.preview_mode_selector.addItem("Studio", "studio")
        mode_line = QHBoxLayout()
        mode_line.setContentsMargins(0, 2, 0, 2)
        mode_label = QLabel("Preview mode")
        mode_label.setObjectName("fieldCaption")
        mode_line.addWidget(mode_label)
        mode_line.addStretch()
        mode_line.addWidget(self.preview_mode_selector)
        lighting.add_layout(mode_line)
        self.brightness = SliderField("Brightness", 75)
        self.contrast = SliderField("Contrast", 60)
        self.nightlight = Toggle(True)
        self.intensity = SliderField("Intensity", 80)
        self.color_button = QPushButton("      ▾")
        self.color_button.setObjectName("color")
        self.color_button.setCursor(Qt.PointingHandCursor)
        self.color_button.clicked.connect(self.pick_color)
        lighting.add(self.brightness)
        lighting.add(self.contrast)
        lighting.add_layout(self._toggle_line("Backlight Preview", self.nightlight, accent=True))
        self.backlight_status = QLabel()
        self.backlight_status.setObjectName("backlightStatus")
        self.backlight_status.setWordWrap(True)
        lighting.add(self.backlight_status)
        color_line = QHBoxLayout()
        color_line.addWidget(QLabel("Color"))
        color_line.addStretch()
        color_line.addWidget(self.color_button)
        lighting.add_layout(color_line)
        lighting.add(self.intensity)
        self.right.addWidget(lighting)

        result = Section("MODEL PREVIEW", "◉")
        self.mini_preview = MeshPreview(small=True)
        self.mini_preview.setFixedHeight(203)
        result.add(self.mini_preview)
        mini_note = QLabel("Synchronized mesh")
        mini_note.setObjectName("syncNote")
        mini_note.setAlignment(Qt.AlignCenter)
        result.add(mini_note)
        self.right.addWidget(result)

        image_options = Section("IMAGE OPTIONS", "▧")
        self.image_brightness = SliderField("Brightness", 0, -50, 50, lambda value: f"{value:+d}")
        self.image_contrast = SliderField("Contrast", 0, -50, 50, lambda value: f"{value:+d}")
        self.gamma = SliderField("Gamma", 100, 50, 180, lambda value: f"{value / 100:.2f}")
        self.equalize = Toggle(False)
        self.smooth = Toggle(False)
        self.mirror_button = QPushButton("Flip Horizontal")
        self.mirror_button.setObjectName("mirrorButton")
        self.mirror_button.setCheckable(True)
        self.mirror_button.setCursor(Qt.PointingHandCursor)
        self.mirror_button.setToolTip("Mirror the source image horizontally for printing")
        self.invert = Toggle(False)
        image_options.add(self.image_brightness)
        image_options.add(self.image_contrast)
        image_options.add(self.gamma)
        image_options.add_layout(self._toggle_line("Auto contrast", self.equalize))
        image_options.add_layout(self._toggle_line("Smooth detail", self.smooth))
        image_options.add(self.mirror_button)
        image_options.add_layout(self._toggle_line("Invert image", self.invert))
        self.right.addWidget(image_options)

        render = Section("PREVIEW DETAILS", "◌")
        self.preview_detail = QLabel("Load an image to calculate mesh dimensions.")
        self.preview_detail.setObjectName("detail")
        self.preview_detail.setWordWrap(True)
        render.add(self.preview_detail)
        self.right.addWidget(render)
        self.right.addStretch(1)
        self.preview_mode_selector.currentIndexChanged.connect(self._apply_preview_mode)
        for slider in (self.brightness, self.contrast, self.intensity):
            slider.valueChanged.connect(self.update_lights)
        self.nightlight.toggled.connect(self.update_lights)
        for slider in (self.image_brightness, self.image_contrast, self.gamma):
            slider.valueChanged.connect(self.schedule_preview)
        for toggle in (self.equalize, self.smooth, self.invert):
            toggle.toggled.connect(self.schedule_preview)
        self.mirror_button.toggled.connect(self.schedule_preview)

    def _footer(self):
        footer = QFrame()
        footer.setObjectName("footer")
        footer.setFixedHeight(58)
        row = QHBoxLayout(footer)
        row.setContentsMargins(22, 9, 21, 9)
        dot = QLabel("●")
        dot.setObjectName("readyDot")
        self.footer_status = QLabel("Ready")
        self.footer_status.setObjectName("footerText")
        self.dimensions = QLabel("No model dimensions yet")
        self.dimensions.setObjectName("footerText")
        row.addWidget(dot)
        row.addWidget(self.footer_status)
        row.addStretch(1)
        row.addWidget(self.dimensions)
        row.addStretch(1)
        self.export_button = QPushButton("⇩  Export STL")
        self.export_button.setObjectName("export")
        self.export_button.setEnabled(False)
        self.export_button.setFixedSize(163, 37)
        self.export_button.clicked.connect(self.export)
        row.addWidget(self.export_button)
        return footer

    def _toggle_line(self, label, toggle, accent=False):
        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 2)
        caption = QLabel(label)
        caption.setObjectName("accent" if accent else "toggleCaption")
        row.addWidget(caption)
        row.addStretch()
        row.addWidget(toggle)
        return row

    # --------- behavior ---------
    def _preview_controls(self):
        return (
            self.width, self.height, self.min_thickness, self.max_thickness,
            self.base, self.relief_depth, self.quality, self.print_pixel_pitch,
        )

    def _set_mode(self, mode="plane"):
        # Plane is the sole product while its corrected manifold engine is active.
        self.mode = "plane"
        self.schedule_preview()
        self.update_summary()

    def _request_dimension_preview(self):
        # The STL is rebuilt with the new physical dimensions. Ask both cameras
        # to refit that *new* mesh so the true aspect ratio is visible rather
        # than retaining the framing calculated for the old size.
        if self.image_path:
            self.preview.request_fit()
            self.mini_preview.request_fit()
        self.schedule_preview()

    def _linked_dimensions(self, width_mm, height_mm):
        """Return a valid panel size that preserves the uploaded image ratio."""
        ratio = max(1e-6, float(self.image_ratio))
        # The caller supplies exactly one edited axis; calculate the other one.
        if width_mm is not None:
            width = float(width_mm)
            height = width / ratio
        else:
            height = float(height_mm)
            width = height * ratio
        # Preserve ratio while respecting the explicit 20–400 mm controls.
        if min(width, height) < 20.0:
            scale = 20.0 / min(width, height)
            width *= scale
            height *= scale
        if max(width, height) > 400.0:
            scale = 400.0 / max(width, height)
            width *= scale
            height *= scale
        return width, height

    def _sync_image_ratio(self, width_mm=None, height_mm=None):
        if self._ratio_updating or not self.image_path:
            return
        width, height = self._linked_dimensions(width_mm, height_mm)
        self._ratio_updating = True
        self.width.setValue(width)
        self.height.setValue(height)
        self._ratio_updating = False

    def _width_changed(self, value):
        if self._ratio_updating:
            return
        # Once an image is uploaded, the printed panel permanently follows its
        # visible aspect ratio. Editing Width therefore updates Height as well.
        self._sync_image_ratio(width_mm=value)
        self._request_dimension_preview()

    def _height_changed(self, value):
        if self._ratio_updating:
            return
        # Likewise, editing Height recalculates Width from the same image ratio.
        self._sync_image_ratio(height_mm=value)
        self._request_dimension_preview()

    def schedule_preview(self, *args, delay_ms=260):
        # Update labels immediately, but wait until editing pauses before any
        # image processing or mesh build touches the UI thread.
        if self.image_path:
            self.preview_timer.start(delay_ms)
        self.update_summary()

    def _apply_relief(self, *args):
        # Both the mode and the depth are live parameters; preparation stays
        # debounced and off the UI thread.
        self.schedule_preview(delay_ms=90)
        self.update_summary()

    def _image_depth_offset(self):
        depth = float(self.relief_depth.value())
        return depth if self.relief_mode.currentData() == "raise" else -depth

    def _sampling_profile(self):
        requested = self.quality.value()
        geometry_limit = math.sqrt(core.MAX_SAMPLES / max(1.0, self.width.value() * self.height.value()))
        print_limit = 1.0 / max(0.01, self.print_pixel_pitch.value())
        source_limit = None
        if getattr(self, "source_pixels", None):
            source_limit = min(
                self.source_pixels[0] / max(1.0, self.width.value()),
                self.source_pixels[1] / max(1.0, self.height.value()),
            )
        effective = min(requested, geometry_limit, print_limit)
        limiter = "requested"
        if geometry_limit < effective + 1e-9:
            limiter = "geometry limit"
        if print_limit < effective + 1e-9:
            limiter = "print pitch"
        if self.smart_sampling.isChecked() and source_limit is not None and source_limit < effective:
            effective = source_limit
            limiter = "source image"
        effective = max(0.5, effective)
        columns = max(2, int(self.width.value() * effective))
        rows = max(2, int(self.height.value() * effective))
        return {
            "requested": requested, "effective": effective, "source_limit": source_limit,
            "geometry_limit": geometry_limit, "print_limit": print_limit,
            "columns": columns, "rows": rows, "samples": columns * rows,
            "limiter": limiter,
        }

    def current_params(self, preview=False):
        profile = self._sampling_profile()
        quality = min(profile["effective"], 1.0) if preview else profile["effective"]
        return {
            "image_path": self.image_path,
            "output_stl_path": self.output_path,
            "width_mm": self.width.value(),
            "height_mm": self.height.value(),
            "px_per_mm": quality,
            "min_thickness_mm": self.min_thickness.value(),
            "max_thickness_mm": self.max_thickness.value(),
            "base_thickness_mm": self.base.value(),
            "forward_relief_mm": self._image_depth_offset(),
            "curve_degrees": 0.0,
            "invert": self.invert.isChecked(),
            "equalize": self.equalize.isChecked(),
            "blur_smooth": self.smooth.isChecked(),
            "mirror_horizontal": self.mirror_button.isChecked(),
            "crop_to_fit": self.crop.isChecked(),
            "brightness": self.image_brightness.value(),
            "contrast": self.image_contrast.value(),
            "gamma": self.gamma.value() / 100,
            "shape": "flat",
            "lang": "ar",
        }

    def refresh_live_mesh(self):
        """Start a cancellable background request for the current live preview."""
        if not self.image_path:
            return
        self._preview_request_id += 1
        request_id = self._preview_request_id
        # Existing workers finish at a safe processing boundary. Their stale
        # results cannot replace the newest preview because of the request id.
        for worker in self._preview_workers.values():
            if worker.isRunning():
                worker.requestInterruption()
        params = self.current_params(preview=False)
        worker = PreviewWorker(request_id, params)
        self._preview_workers[request_id] = worker
        worker.ready.connect(self._apply_live_preview)
        worker.failed.connect(self._preview_failed)
        worker.finished.connect(lambda request_id=request_id: self._preview_workers.pop(request_id, None))
        worker.start()

    def _apply_live_preview(self, request_id, result):
        if request_id != self._preview_request_id:
            return
        params = result["params"]
        vertices = result["vertices"]
        faces = result["faces"]
        heightmap = result["heightmap"]
        texture_heightmap = result["texture_heightmap"]
        self.preview.set_mesh(
            vertices, faces, heightmap.shape, params["image_path"], heightmap, False,
            forward_relief_mm=params["forward_relief_mm"], texture_heightmap=texture_heightmap,
            min_thickness_mm=params["min_thickness_mm"], max_thickness_mm=params["max_thickness_mm"],
            base_thickness_mm=params["base_thickness_mm"],
        )
        self.mini_preview.set_mesh(
            vertices, faces, heightmap.shape, params["image_path"], heightmap, False,
            forward_relief_mm=params["forward_relief_mm"], texture_heightmap=texture_heightmap,
            min_thickness_mm=params["min_thickness_mm"], max_thickness_mm=params["max_thickness_mm"],
            base_thickness_mm=params["base_thickness_mm"],
        )
        if self.language == "ar":
            self.preview_detail.setText(
                f"هندسة حية: {len(vertices):,} رأس · {len(faces):,} مثلثًا\n"
                f"شبكة المعاينة: {result['columns']} × {result['rows']} · تفاصيل الضوء: {result['texture_columns']} × {result['texture_rows']}\n"
                f"اللوح: {params['width_mm']:.1f} × {params['height_mm']:.1f} مم · البروز: {params['forward_relief_mm']:.1f} مم"
            )
        else:
            self.preview_detail.setText(
                f"Live geometry: {len(vertices):,} vertices · {len(faces):,} triangles\n"
                f"Preview mesh: {result['columns']} × {result['rows']} · Light detail: {result['texture_columns']} × {result['texture_rows']}\n"
                f"Panel: {params['width_mm']:.1f} × {params['height_mm']:.1f} mm · Relief: {params['forward_relief_mm']:.1f} mm"
            )
        relief = float(params["forward_relief_mm"])
        depth = abs(relief)
        if relief > 0:
            label = "بروز" if self.language == "ar" else "RAISED"
            self.live_badge.setText(f"{label} +{depth:.1f} mm")
            self.generation_status.setText(
                f"وضع البروز نشط: الصورة بارزة للأمام بمقدار {depth:.1f} مم."
                if self.language == "ar" else f"Raised mode is active: image relief is raised by {depth:.1f} mm."
            )
        elif relief < 0:
            label = "حفر" if self.language == "ar" else "ENGRAVED"
            self.live_badge.setText(f"{label} −{depth:.1f} mm")
            self.generation_status.setText(
                f"وضع الحفر نشط: الصورة محفورة بمقدار {depth:.1f} مم."
                if self.language == "ar" else f"Engraved mode is active: image relief is recessed by {depth:.1f} mm."
            )
        else:
            label = "مسطح" if self.language == "ar" else "FLAT"
            self.live_badge.setText(f"{label} 0.0 mm")
            self.generation_status.setText(
                "لا يوجد عمق إضافي للصورة." if self.language == "ar" else "No additional image relief depth."
            )
        self.footer_status.setText("المعاينة الحية جاهزة" if self.language == "ar" else "Live preview ready")

    def _preview_failed(self, request_id, message):
        if request_id == self._preview_request_id:
            self.generation_status.setText(f"Live preview could not update: {message.splitlines()[0]}")

    def _final_grid_dimensions(self):
        profile = self._sampling_profile()
        return profile["columns"], profile["rows"]

    def update_quality_estimate(self):
        profile = self._sampling_profile()
        rows, columns = profile["rows"], profile["columns"]
        triangles = 4 * (rows - 1) * (columns - 1) + 4 * (rows - 1) + 4 * (columns - 1)
        size_mb = (84 + triangles * 50) / (1024 * 1024)
        source_text = "—" if profile["source_limit"] is None else f"{profile['source_limit']:.1f} px/mm"
        if self.language == "ar":
            limiter = {"requested": "القيمة المطلوبة", "source image": "الصورة الأصلية", "print pitch": "دقة الطباعة", "geometry limit": "حد الشبكة"}.get(profile["limiter"], profile["limiter"])
            self.quality_hint.setText(
                f"دقة الصورة: {profile['effective']:.1f} بكسل/مم · اللوح {columns:,} × {rows:,}\n"
                f"الحد الفعلي: {limiter} · حد الصورة: {source_text} · حد الطباعة: {profile['print_limit']:.1f} بكسل/مم · {triangles:,} مثلثًا\n"
                f"حجم STL التقريبي: {size_mb:.0f} MB · رفع الدقة فوق حد الصورة لا يضيف تفاصيل جديدة."
            )
        else:
            self.quality_hint.setText(
                f"Panel: {columns:,} × {rows:,} samples\n"
                f"Effective: {profile['effective']:.1f} px/mm ({profile['limiter']}) · Source limit: {source_text} · {triangles:,} triangles\n"
                f"~{size_mb:.0f} MB STL · Tip: above the source limit only smooths pixels; it cannot create new photo detail."
            )

    def update_summary(self):
        self.update_quality_estimate()
        relief = self._image_depth_offset()
        total_depth = self.max_thickness.value() + self.base.value() + max(0.0, relief)
        if self.language == "ar":
            self.dimensions.setText(
                f"اللوح: {self.width.value():.1f} × {self.height.value():.1f} × {total_depth:.1f} مم"
            )
        else:
            self.dimensions.setText(
                f"Panel: {self.width.value():.1f} × {self.height.value():.1f} × {total_depth:.1f} mm"
            )

    def _update_presentation_badge(self):
        if not hasattr(self, "presentation_badge"):
            return
        if self.preview_mode == "studio":
            self.presentation_badge.setText("الاستوديو" if self.language == "ar" else "STUDIO")
        else:
            self.presentation_badge.setText("صندوق الإضاءة" if self.language == "ar" else "LIGHTBOX")

    def _apply_preview_mode(self, *args):
        mode = self.preview_mode_selector.currentData() or "lightbox"
        self.preview_mode = mode
        self.preview.set_presentation_mode(mode)
        self.mini_preview.set_presentation_mode(mode)
        self._update_presentation_badge()
        self.update_lights()

    def _preview_view_changed(self):
        # Rotation signals geometric inspection, so Studio becomes active at
        # once; the mesh and all STL parameters remain entirely unchanged.
        if self.preview_mode != "studio" and (abs(self.preview.yaw) > 1.0 or abs(self.preview.pitch) > 1.0):
            self.preview_mode_selector.setCurrentIndex(1)

    def _update_backlight_ui(self):
        is_lightbox = self.preview_mode == "lightbox"
        enabled = is_lightbox and self.nightlight.isChecked()
        self.nightlight.setEnabled(is_lightbox)
        self.brightness.setEnabled(is_lightbox)
        self.contrast.setEnabled(is_lightbox)
        self.intensity.setEnabled(enabled)
        self.color_button.setEnabled(enabled)
        if not is_lightbox:
            text = "وضع الاستوديو: إضاءة محايدة لفحص الشكل والحواف والسماكة."
            if self.language != "ar":
                text = "Studio mode: neutral light for inspecting relief, edges, and thickness."
        elif self.language == "ar":
            state = "مفعّلة" if enabled else "متوقفة"
            text = f"معاينة الإضاءة الخلفية: {state} · صندوق الإضاءة · {self.intensity.value()}% · {self.light_color.name().upper()}"
        else:
            state = "ON" if enabled else "OFF"
            text = f"Backlight Preview: {state} · Lightbox · {self.intensity.value()}% · {self.light_color.name().upper()}"
        self.backlight_status.setText(text)

    def update_lights(self, *args):
        backlight_active = self.preview_mode == "lightbox" and self.nightlight.isChecked()
        values = (self.brightness.value(), self.contrast.value(), backlight_active, self.intensity.value(), self.light_color)
        self.preview.set_lighting(*values)
        self.mini_preview.set_lighting(*values)
        self._update_backlight_ui()

    def toggle_backlight(self):
        if self.preview_mode != "lightbox":
            self.preview_mode_selector.setCurrentIndex(0)
            self.nightlight.setChecked(True)
        else:
            self.nightlight.setChecked(not self.nightlight.isChecked())

    def toggle_nightlight(self):
        # Backwards-compatible route for any prior shortcut or external caller.
        self.toggle_backlight()

    def pick_color(self):
        title = "لون الإضاءة الخلفية" if self.language == "ar" else "Backlight colour"
        color = QColorDialog.getColor(self.light_color, self, title)
        if color.isValid():
            self.light_color = color
            self.color_button.setStyleSheet(
                f"QPushButton {{ background: {color.name()}; color: #10131b; border: 1px solid #69718a; border-radius: 6px; }}"
            )
            self.update_lights()

    def pick_image(self):
        title = "اختيار صورة" if self.language == "ar" else "Select image"
        path, _ = QFileDialog.getOpenFileName(self, title, "", "Images (*.jpg *.jpeg *.png *.webp *.bmp)")
        if path:
            self.load_image(path)

    def _short_image_name(self, name):
        return f"{name[:5]}..." if len(name) > 10 else name

    def show_image_info(self):
        if not self.image_path:
            return
        image = QImage(self.image_path)
        name = Path(self.image_path).name
        dialog = QDialog(self)
        dialog.setWindowTitle("معلومات الصورة" if self.language == "ar" else "Image information")
        # Keep information at left and the image preview at right, matching the
        # requested reference layout regardless of the application's RTL mode.
        dialog.setLayoutDirection(Qt.LeftToRight)
        dialog.setMinimumSize(650, 350)
        dialog.setModal(True)
        layout = QHBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        info_panel = QFrame()
        info_panel.setObjectName("imageInfoPanel")
        info = QVBoxLayout(info_panel)
        info.setContentsMargins(24, 24, 24, 20)
        info.setSpacing(9)
        heading = QLabel("معلومات الصورة" if self.language == "ar" else "IMAGE INFORMATION")
        heading.setObjectName("imageInfoHeading")
        if self.language == "ar":
            heading.setAlignment(Qt.AlignRight)
        info.addWidget(heading)
        ratio = image.width() / max(1, image.height())
        details = (
            ("الاسم", name),
            ("الصيغة", Path(name).suffix.upper().lstrip(".") or "—"),
            ("الأبعاد", f"{image.width()} × {image.height()} px"),
            ("النسبة", f"{ratio:.3f} : 1"),
            ("المسار", str(Path(self.image_path).parent)),
        ) if self.language == "ar" else (
            ("Name", name),
            ("Format", Path(name).suffix.upper().lstrip(".") or "—"),
            ("Pixels", f"{image.width()} × {image.height()} px"),
            ("Aspect ratio", f"{ratio:.3f} : 1"),
            ("Folder", str(Path(self.image_path).parent)),
        )
        for caption, value in details:
            label = QLabel(f"<b>{caption}</b><br>{value}")
            label.setObjectName("imageInfoText")
            label.setWordWrap(True)
            if self.language == "ar":
                label.setAlignment(Qt.AlignRight)
            info.addWidget(label)
        info.addStretch(1)
        close = QPushButton("حسناً" if self.language == "ar" else "OKAY")
        close.setObjectName("imageInfoClose")
        close.clicked.connect(dialog.accept)
        info.addWidget(close)
        layout.addWidget(info_panel, 1)

        preview_panel = QFrame()
        preview_panel.setObjectName("imagePreviewPanel")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(20, 20, 20, 20)
        preview_label = QLabel()
        preview_label.setAlignment(Qt.AlignCenter)
        preview_label.setPixmap(QPixmap(self.image_path).scaled(320, 290, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        preview_layout.addWidget(preview_label, 1)
        layout.addWidget(preview_panel, 1)
        self._last_image_info_dialog = dialog
        dialog.exec()

    def load_image(self, path):
        image = QImage(path)
        if image.isNull():
            QMessageBox.warning(self, APP_TITLE, "The selected image could not be opened.")
            return
        # The engine applies EXIF orientation before making the STL map. Use the
        # same oriented dimensions for the initial physical size suggestion so
        # portrait phone photos are never fitted as landscape images.
        try:
            with Image.open(path) as source_image:
                oriented = ImageOps.exif_transpose(source_image)
                source_width, source_height = oriented.size
        except Exception:
            source_width, source_height = image.width(), image.height()
        self.image_path = path
        # A newly loaded photo opens in Lightbox mode to prioritize the final
        # transmitted image; changing mode never rebuilds or alters the STL.
        self.preview_mode_selector.setCurrentIndex(0)
        self.preview.request_fit()
        self.mini_preview.request_fit()
        self.image_button.setText(self._tr("Change Image"))
        self.source_pixels = (source_width, source_height)
        self.image_ratio = source_width / max(1, source_height)
        thumbnail = QPixmap(path).scaled(self.image_thumb.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        self.image_thumb.setPixmap(thumbnail)
        full_name = os.path.basename(path)
        self.file_label.setText(self._short_image_name(full_name))
        self.file_label.setToolTip(full_name)
        self.file_label.setEnabled(True)
        self.resolution_label.setText(f"{source_width} × {source_height} px")
        # Fit the physical panel to the oriented source ratio exactly at upload.
        # The 150 mm longest-side suggestion is applied once; Width and Height
        # are independent manual controls immediately afterwards.
        if self.image_ratio >= 1.0:
            target_width = 150.0
            target_height = target_width / self.image_ratio
        else:
            target_height = 150.0
            target_width = target_height * self.image_ratio
        # Preserve the ratio even for unusually panoramic inputs, within the
        # explicit UI limits of 20–400 mm per physical dimension.
        if min(target_width, target_height) < 20.0:
            scale = 20.0 / min(target_width, target_height)
            target_width *= scale
            target_height *= scale
        if max(target_width, target_height) > 400.0:
            scale = 400.0 / max(target_width, target_height)
            target_width *= scale
            target_height *= scale
        self._ratio_updating = True
        self.width.setValue(target_width)
        self.height.setValue(target_height)
        self._ratio_updating = False
        self.export_button.setEnabled(True)
        self.schedule_preview(delay_ms=40)
        self.generation_status.setText(
            "جارٍ بناء معاينة الشبكة الحقيقية…" if self.language == "ar" else "Building the true low-resolution mesh preview…"
        )

    def _start_generation(self, output_path, exporting=False):
        if not self.image_path:
            QMessageBox.information(self, APP_TITLE, "اختر صورة أولًا لإنشاء نموذج الليثوفين.")
            return
        self.output_path = str(output_path)
        self._exporting = bool(exporting)
        self.generate_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.generation_status.setText(
            "جارٍ تصدير ملف STL…" if exporting and self.language == "ar" else
            "Exporting STL…" if exporting else "Generating the full STL model…"
        )
        self.footer_status.setText("جارٍ تصدير STL" if exporting and self.language == "ar" else "Exporting STL" if exporting else "Generating STL")
        self.worker = GenerateWorker(self.current_params(preview=False))
        self.worker.progress.connect(self._progress)
        self.worker.finished_ok.connect(self._generated)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def generate(self):
        self._start_generation(self.output_path, exporting=False)

    def _progress(self, value, text):
        self.generation_status.setText(f"{text} {value}%")

    def _generated(self, result):
        self.generate_button.setEnabled(True)
        self.export_button.setEnabled(bool(self.image_path))
        if getattr(self, "_exporting", False):
            self.generation_status.setText(
                f"تم تصدير STL بنجاح: {Path(self.output_path).name}" if self.language == "ar" else
                f"STL exported successfully: {Path(self.output_path).name}"
            )
            self.footer_status.setText("تم تصدير STL" if self.language == "ar" else "STL exported")
        else:
            self.generation_status.setText(f"STL ready — {result['vertices']:,} vertices and {result['faces']:,} triangles.")
            self.footer_status.setText("STL ready")
        self._exporting = False
        self.schedule_preview(delay_ms=500)

    def _failed(self, message):
        self.generate_button.setEnabled(True)
        self.export_button.setEnabled(bool(self.image_path))
        self._exporting = False
        self.footer_status.setText("خطأ في التوليد" if self.language == "ar" else "Generation error")
        self.generation_status.setText("فشل توليد STL. راجع الإعدادات الحالية." if self.language == "ar" else "STL generation failed. Review the current settings.")
        QMessageBox.critical(self, APP_TITLE, message)

    def export(self):
        if not self.image_path:
            QMessageBox.information(self, APP_TITLE, "اختر صورة أولًا لتصدير STL.")
            return
        title = "تصدير STL" if self.language == "ar" else "Export STL"
        default_name = str(Path(self.output_path).with_name("lithophane.stl"))
        path, _ = QFileDialog.getSaveFileName(self, title, default_name, "STL Files (*.stl)")
        if not path:
            return
        if Path(path).suffix.lower() != ".stl":
            path = f"{path}.stl"
        # Export always produces the current model at the path selected here;
        # it no longer silently depends on a previous Generate operation.
        self._start_generation(path, exporting=True)

    def _apply_style(self):
        self.color_button.setStyleSheet("QPushButton { background: #fff0bd; color: #10131b; border: 1px solid #69718a; border-radius: 6px; }")
        self.setStyleSheet("""
            * { font-family: 'Inter', 'Segoe UI', Arial; }
            QMainWindow, #root { background: #090c14; color: #eff2fa; }
            #header { background: #080b13; border-bottom: 1px solid #1c2537; }
            #logo { background: #5867ef; color: #eef1ff; border-radius: 8px; font-size: 18px; font-weight: 800; }
            #brand { color: #f6f7fc; font-size: 17px; font-weight: 700; }
            #segmented { background: #141927; border: 1px solid #222b41; border-radius: 9px; }
            #planeMode { background: #5964ed; color: white; border-radius: 7px; font-size: 12px; font-weight: 800; letter-spacing: 0.5px; }
            #tab { background: transparent; color: #aeb6c8; border: none; border-radius: 7px; font-size: 13px; font-weight: 700; }
            #tab:checked { background: #5964ed; color: white; }
            #topTool { border: none; background: transparent; color: #bfc7d9; border-radius: 6px; font-size: 17px; }
            #topTool:hover { background: #1a2131; color: white; }
            #languageButton { background: #1a2237; border: 1px solid #5366de; color: #e9edff; border-radius: 15px; font-size: 15px; font-family: 'Segoe UI Emoji', 'Segoe UI Symbol', 'Arial'; }
            #languageButton:hover { background: #5964ed; border-color: #8894ff; }
            #workspaceScroll, #workspace, #sidebarScroll, #sidebar { background: transparent; }
            #workspaceScroll QScrollBar:horizontal { background: #0d1018; height: 10px; margin: 2px 13px 4px 13px; border-radius: 5px; }
            #workspaceScroll QScrollBar::handle:horizontal { background: #4f5fd5; min-width: 54px; border-radius: 5px; }
            #workspaceScroll QScrollBar::handle:horizontal:hover { background: #7180ff; }
            #workspaceScroll QScrollBar::add-line:horizontal, #workspaceScroll QScrollBar::sub-line:horizontal { width: 0; }
            QScrollBar:vertical { background: #0d1018; width: 7px; margin: 3px 0; border-radius: 3px; }
            QScrollBar::handle:vertical { background: #343e56; min-height: 32px; border-radius: 3px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            #section { background: #111620; border: 1px solid #202a3d; border-radius: 10px; }
            #sectionIcon { color: #7080ff; font-size: 13px; font-weight: 800; }
            #sectionTitle { color: #e6e9f4; font-size: 11px; font-weight: 800; letter-spacing: 0.4px; }
            #sectionRule { background: #252e42; color: #252e42; max-height: 1px; border: none; }
            #thumbnail { background: #0b0e15; border: 1px dashed #4b566c; border-radius: 7px; color: #667287; font-size: 10px; font-weight: 700; }
            #fileName { color: #f1f3f9; font-size: 11px; font-weight: 700; text-align: left; border: none; padding: 0; }
            #fileName:hover:enabled { color: #aebaff; text-decoration: underline; }
            #muted, #hint, #status, #detail { color: #7e889d; font-size: 10px; }
            #outline { color: #92a5ff; background: #131a2b; border: 1px solid #4c5fd4; border-radius: 5px; min-height: 29px; font-size: 10px; font-weight: 700; }
            #outline:hover { color: white; background: #202a4b; }
            #fieldCaption, #toggleCaption, #sliderCaption { color: #d8dce7; font-size: 10.5px; font-weight: 600; }
            #fieldUnit { color: #6f7a92; font-size: 9px; }
            #accent { color: #c8c8ff; font-size: 10.5px; font-weight: 700; }
            #stepper { background: #0b0f18; border: 1px solid #293249; border-radius: 5px; }
            #numericValue { border: none; background: transparent; color: #f0f2f8; font-size: 10px; font-weight: 700; }
            #stepButton { border: none; background: #151b28; color: #ccd3e4; font-size: 15px; }
            #stepButton:hover { background: #252e43; color: white; }
            #stepButton:disabled, #numericValue:disabled { color: #5c667b; background: #10141d; }
            #framePlacement { min-width: 126px; min-height: 27px; color: #e9edf7; background: #0b0f18; border: 1px solid #293249; border-radius: 5px; padding: 0 7px; font-size: 10px; font-weight: 700; }
            #framePlacement::drop-down { border: none; width: 20px; }
            #framePlacement QAbstractItemView { color: #eef1fa; background: #151c2a; border: 1px solid #38445f; selection-background-color: #5964ed; }
            #hint { line-height: 1.35; padding-top: 3px; }
            #reliefMode, #previewMode { color: #dce3ff; background: #141b2c; border: 1px solid #5365de; border-radius: 6px; min-height: 29px; min-width: 98px; padding: 0 8px; font-size: 10.5px; font-weight: 800; }
            #reliefMode:hover, #previewMode:hover { background: #202a4b; color: white; }
            #reliefMode QAbstractItemView, #previewMode QAbstractItemView { color: #edf1fb; background: #151c2a; border: 1px solid #5365de; selection-background-color: #5964ed; }
            #mirrorButton { color: #bfcaff; background: #121928; border: 1px solid #3d4f9f; border-radius: 6px; min-height: 29px; font-size: 10.5px; font-weight: 700; }
            #mirrorButton:hover { background: #202944; color: white; }
            #mirrorButton:checked { color: white; background: #4656c7; border-color: #8191ff; }
            #primary { color: white; background: #575fec; border: 1px solid #7880ff; border-radius: 8px; font-size: 12px; font-weight: 800; }
            #primary:hover { background: #686ffa; }
            #primary:disabled { color: #9098ac; background: #313648; border-color: #3d435a; }
            #previewCard { background: #0d111b; border: 1px solid #1e283a; border-radius: 10px; }
            #previewTitle { color: #e9edf7; font-size: 11px; font-weight: 800; letter-spacing: 0.5px; }
            #liveBadge { color: #9ea8ff; background: #18203a; border: 1px solid #33416e; border-radius: 4px; padding: 3px 6px; font-size: 9px; font-weight: 800; }
            #modeBadge { color: #b9c7ff; background: #17213a; border: 1px solid #405aad; border-radius: 4px; padding: 3px 6px; font-size: 9px; font-weight: 800; }
            #backlightStatus { color: #8996b0; font-size: 10px; line-height: 1.35; padding: 1px 0; }
            #previewTool { background: #151b29; border: 1px solid #2b354b; color: #d7ddeb; border-radius: 6px; font-size: 16px; }
            #previewTool:hover { border-color: #6474ef; background: #222a3e; }
            #meshPreview { background: #070b13; border: 1px solid #1b263a; border-radius: 8px; }
            #guide { background: #101621; border: 1px solid #222d41; border-radius: 7px; }
            #guide QLabel:first-child { color: #f4ca58; }
            #guideText { color: #aeb6c7; font-size: 10px; }
            #sliderNumber { color: #e9ecf5; background: #171e2b; border: 1px solid #293349; border-radius: 4px; min-width: 31px; padding: 3px 5px; font-size: 9px; }
            QSlider::groove:horizontal { height: 4px; background: #263046; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #5768f3; border-radius: 2px; }
            QSlider::handle:horizontal { background: #7581ff; border: 2px solid #263795; width: 10px; margin: -4px 0; border-radius: 5px; }
            #color { min-width: 58px; min-height: 26px; text-align: right; padding-right: 5px; }
            #syncNote { color: #6675ef; font-size: 10px; font-weight: 700; padding-top: 2px; }
            #footer { background: #080b13; border-top: 1px solid #1b2435; }
            #readyDot { color: #5fd77f; font-size: 15px; }
            #footerText { color: #a9b2c5; font-size: 10.5px; }
            #export { color: #edf1fb; background: #171e2c; border: 1px solid #303a51; border-radius: 7px; font-size: 11px; font-weight: 700; }
            #export:hover { background: #252e45; border-color: #6c7bf2; }
            #export:disabled { color: #626c80; background: #10151e; border-color: #20283a; }
            #imageInfoPanel { background: #0d6572; min-width: 300px; }
            #imagePreviewPanel { background: #f6f7fb; min-width: 300px; }
            #imageInfoHeading { color: #eefafd; font-size: 17px; font-weight: 800; }
            #imageInfoText { color: #d9f0f4; font-size: 11px; line-height: 1.4; }
            #imageInfoClose { color: #dffaff; background: #084c56; border: 1px solid #64bac5; border-radius: 5px; min-height: 30px; font-size: 10px; font-weight: 800; }
            #imageInfoClose:hover { background: #0b5f6c; color: white; }
            QMessageBox { background: #121721; }
            QMessageBox QLabel { color: #edf0f8; }
            QMessageBox QPushButton { background: #5864ec; color: white; border: none; border-radius: 5px; padding: 6px 15px; }
        """)


def main():
    fmt = QSurfaceFormat()
    fmt.setVersion(2, 1)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
    fmt.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(fmt)
    QLocale.setDefault(NUMERIC_LOCALE)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
 