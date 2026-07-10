"""
core.py — Lithophane generation engine
----------------------------------------
Handles:
  1) Image -> grayscale heightmap (numpy array, 0..1)
  2) Heightmap -> 3D mesh (flat panel OR curved/cylindrical panel)
  3) Mesh -> binary STL export (no external mesh library required)
"""

from __future__ import annotations
import struct
import numpy as np
from PIL import Image, ImageOps


# ----------------------------------------------------------------------
# 1) Image -> Heightmap
# ----------------------------------------------------------------------
def image_to_heightmap(
    image_path: str,
    px_width: int,
    px_height: int,
    invert: bool = False,
    equalize: bool = False,
    blur_smooth: bool = False,
    mirror_horizontal: bool = False,
) -> np.ndarray:
    """
    Load an image and convert it into a normalized grayscale heightmap.
    Returns a 2D numpy array (rows=px_height, cols=px_width), values in [0, 1]
    where 0 = pure black (original), 1 = pure white (original).

    mirror_horizontal: flips the image left/right before generating the mesh.
        Lithophanes are viewed from the front with a light behind them —
        depending on how the model ends up oriented on the print bed / in the
        slicer, text can come out reading backwards. Toggle this to correct it.
    """
    img = Image.open(image_path)
    img = ImageOps.exif_transpose(img)          # respect camera rotation metadata
    img = img.convert("L")                      # grayscale

    if mirror_horizontal:
        img = ImageOps.mirror(img)               # flip left/right

    if equalize:
        img = ImageOps.equalize(img)

    if blur_smooth:
        from PIL import ImageFilter
        img = img.filter(ImageFilter.GaussianBlur(radius=1))

    img = img.resize((px_width, px_height), Image.LANCZOS)

    arr = np.asarray(img, dtype=np.float64) / 255.0
    if invert:
        arr = 1.0 - arr

    return arr


# ----------------------------------------------------------------------
# 2) Heightmap -> Thickness map
# ----------------------------------------------------------------------
def heightmap_to_thickness(
    heightmap: np.ndarray,
    min_thickness_mm: float,
    max_thickness_mm: float,
) -> np.ndarray:
    """
    Bright pixels (value near 1) => thin (lets light through)
    Dark pixels   (value near 0) => thick (blocks light)
    """
    brightness = heightmap
    thickness = min_thickness_mm + (1.0 - brightness) * (max_thickness_mm - min_thickness_mm)
    return thickness


# ----------------------------------------------------------------------
# 3) Thickness map -> Mesh (vertices, faces)
# ----------------------------------------------------------------------
def build_mesh(
    thickness_mm: np.ndarray,
    width_mm: float,
    height_mm: float,
    base_thickness_mm: float = 0.6,
    curve_degrees: float = 0.0,
    border_mm: float = 0.0,
):
    """
    Build a manifold triangular mesh from a thickness map.

    thickness_mm : 2D array (rows, cols) of local panel thickness (mm)
    width_mm / height_mm : physical size of the panel
    base_thickness_mm : always-solid backing added under the thinnest point
                        (keeps very thin/bright areas from having near-zero walls)
    curve_degrees : 0 = flat panel. >0 bends the panel around a cylinder,
                    turning it into a curved lamp-shade style lithophane.
    border_mm : optional solid raised border frame width (0 = no frame)

    Returns: (vertices: (N,3) float32, faces: (M,3) int32)
    """
    rows, cols = thickness_mm.shape
    total_thickness = thickness_mm + base_thickness_mm  # add solid backing

    # ---- X,Y grid in physical space (mm) ----
    xs = np.linspace(0, width_mm, cols)
    ys = np.linspace(0, height_mm, rows)

    if curve_degrees > 0:
        # Wrap the flat panel around a cylinder.
        # Arc length along X == width_mm, spanning `curve_degrees`.
        theta_total = np.radians(curve_degrees)
        radius = width_mm / theta_total
        thetas = np.linspace(-theta_total / 2, theta_total / 2, cols)
        # top surface (outer, lit side) sits at `radius`
        # bottom surface (inner) sits at radius - local thickness
        cos_t = np.cos(thetas)
        sin_t = np.sin(thetas)
    else:
        radius = None

    # ---- Optional raised border: push border pixels to max thickness ----
    if border_mm > 0:
        px_per_mm_x = (cols - 1) / width_mm if width_mm > 0 else 1
        px_per_mm_y = (rows - 1) / height_mm if height_mm > 0 else 1
        bx = max(1, int(border_mm * px_per_mm_x))
        by = max(1, int(border_mm * px_per_mm_y))
        frame_h = total_thickness.max()
        total_thickness[:by, :] = frame_h
        total_thickness[-by:, :] = frame_h
        total_thickness[:, :bx] = frame_h
        total_thickness[:, -bx:] = frame_h

    n = rows * cols

    def idx(r, c):
        return r * cols + c

    top_verts = np.zeros((n, 3), dtype=np.float32)
    bot_verts = np.zeros((n, 3), dtype=np.float32)

    if curve_degrees > 0:
        for r in range(rows):
            y = ys[r]
            for c in range(cols):
                i = idx(r, c)
                t = total_thickness[r, c]
                ct, st = cos_t[c], sin_t[c]
                # outer (top / lit) surface at fixed radius
                top_verts[i] = (radius * st, y, radius * ct)
                # inner (bottom) surface, pulled in by local thickness
                inner_r = radius - t
                bot_verts[i] = (inner_r * st, y, inner_r * ct)
    else:
        for r in range(rows):
            y = ys[r]
            for c in range(cols):
                i = idx(r, c)
                t = total_thickness[r, c]
                x = xs[c]
                top_verts[i] = (x, y, t)
                bot_verts[i] = (x, y, 0.0)

    vertices = np.vstack([top_verts, bot_verts])
    bot_offset = n

    faces = []

    # ---- Top surface (two triangles per quad) ----
    for r in range(rows - 1):
        for c in range(cols - 1):
            a = idx(r, c)
            b = idx(r, c + 1)
            d = idx(r + 1, c)
            e = idx(r + 1, c + 1)
            faces.append((a, d, b))
            faces.append((b, d, e))

    # ---- Bottom surface (reversed winding = normals point down) ----
    for r in range(rows - 1):
        for c in range(cols - 1):
            a = idx(r, c) + bot_offset
            b = idx(r, c + 1) + bot_offset
            d = idx(r + 1, c) + bot_offset
            e = idx(r + 1, c + 1) + bot_offset
            faces.append((a, b, d))
            faces.append((b, e, d))

    # ---- Side walls (close the volume so the STL is manifold) ----
    # top edge (r=0)
    for c in range(cols - 1):
        a, b = idx(0, c), idx(0, c + 1)
        a2, b2 = a + bot_offset, b + bot_offset
        faces.append((a, b, a2))
        faces.append((b, b2, a2))
    # bottom edge (r=rows-1)
    for c in range(cols - 1):
        a, b = idx(rows - 1, c), idx(rows - 1, c + 1)
        a2, b2 = a + bot_offset, b + bot_offset
        faces.append((a, a2, b))
        faces.append((b, a2, b2))
    # left edge (c=0)
    for r in range(rows - 1):
        a, b = idx(r, 0), idx(r + 1, 0)
        a2, b2 = a + bot_offset, b + bot_offset
        faces.append((a, a2, b))
        faces.append((b, a2, b2))
    # right edge (c=cols-1)
    for r in range(rows - 1):
        a, b = idx(r, cols - 1), idx(r + 1, cols - 1)
        a2, b2 = a + bot_offset, b + bot_offset
        faces.append((a, b, a2))
        faces.append((b, b2, a2))

    faces = np.array(faces, dtype=np.int32)
    return vertices, faces


# ----------------------------------------------------------------------
# 4) Mesh -> binary STL
# ----------------------------------------------------------------------
def write_stl(vertices: np.ndarray, faces: np.ndarray, filepath: str, name: str = "lithophane"):
    """Write a binary STL file (fast, no external dependency)."""
    tri = vertices[faces]  # (M, 3, 3)
    v0, v1, v2 = tri[:, 0], tri[:, 1], tri[:, 2]
    normals = np.cross(v1 - v0, v2 - v0)
    norms_len = np.linalg.norm(normals, axis=1)
    norms_len[norms_len == 0] = 1.0
    normals = (normals.T / norms_len).T.astype(np.float32)

    with open(filepath, "wb") as f:
        header = f"Lithophane Studio export: {name}".encode("utf-8")
        f.write(header[:80].ljust(80, b"\0"))
        f.write(struct.pack("<I", len(faces)))
        for i in range(len(faces)):
            f.write(struct.pack("<3f", *normals[i]))
            f.write(struct.pack("<3f", *v0[i]))
            f.write(struct.pack("<3f", *v1[i]))
            f.write(struct.pack("<3f", *v2[i]))
            f.write(struct.pack("<H", 0))


# ----------------------------------------------------------------------
# 5) Convenience: full pipeline in one call
# ----------------------------------------------------------------------
def generate_lithophane(
    image_path: str,
    output_stl_path: str,
    width_mm: float = 100.0,
    height_mm: float = 100.0,
    px_per_mm: float = 2.0,
    min_thickness_mm: float = 0.6,
    max_thickness_mm: float = 3.0,
    base_thickness_mm: float = 0.6,
    curve_degrees: float = 0.0,
    border_mm: float = 0.0,
    invert: bool = False,
    equalize: bool = False,
    blur_smooth: bool = False,
    mirror_horizontal: bool = False,
    lang: str = "ar",
    progress_cb=None,
):
    """One-shot pipeline. progress_cb(percent:int, message:str) is optional."""
    _MSG = {
        "read":   {"ar": "قراءة الصورة...",              "en": "Reading image..."},
        "thick":  {"ar": "حساب خريطة السماكة...",         "en": "Computing thickness map..."},
        "mesh":   {"ar": "بناء الشبكة ثلاثية الأبعاد...", "en": "Building 3D mesh..."},
        "export": {"ar": "تصدير ملف STL...",              "en": "Exporting STL file..."},
        "done":   {"ar": "تم بنجاح!",                     "en": "Done!"},
    }
    lang = lang if lang in ("ar", "en") else "ar"

    def report(pct, key):
        if progress_cb:
            progress_cb(pct, _MSG[key][lang])

    report(5, "read")
    px_w = max(2, int(width_mm * px_per_mm))
    px_h = max(2, int(height_mm * px_per_mm))
    heightmap = image_to_heightmap(
        image_path, px_w, px_h, invert, equalize, blur_smooth, mirror_horizontal
    )

    report(35, "thick")
    thickness = heightmap_to_thickness(heightmap, min_thickness_mm, max_thickness_mm)

    report(55, "mesh")
    vertices, faces = build_mesh(
        thickness, width_mm, height_mm, base_thickness_mm, curve_degrees, border_mm
    )

    report(85, "export")
    write_stl(vertices, faces, output_stl_path)

    rows, cols = thickness.shape
    top_grid = vertices[: rows * cols].reshape(rows, cols, 3)

    report(100, "done")
    return {
        "vertices": len(vertices),
        "faces": len(faces),
        "heightmap": heightmap,
        "thickness": thickness,
        "top_grid": top_grid,
    }
