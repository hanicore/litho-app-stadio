"""Plane-only lithophane engine.

This module is a corrected replacement for the planar path in the uploaded
core.py. It creates only the two material surfaces and the external perimeter
walls, producing a closed manifold STL suitable for slicing.
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

MAX_SAMPLES = 1_000_000
STL_RECORD_DTYPE = np.dtype([
    ("normal", "<f4", (3,)),
    ("v1", "<f4", (3,)),
    ("v2", "<f4", (3,)),
    ("v3", "<f4", (3,)),
    ("attribute", "<u2"),
], align=False)


def image_to_heightmap(
    image_path: str,
    px_width: int,
    px_height: int,
    invert: bool = False,
    equalize: bool = False,
    blur_smooth: bool = False,
    mirror_horizontal: bool = False,
    crop_to_fit: bool = True,
    brightness: float = 0.0,
    contrast: float = 0.0,
    gamma: float = 1.0,
    contain_full_image: bool = False,
) -> np.ndarray:
    """Create a normalized grayscale heightmap for a planar lithophane."""
    image = Image.open(image_path)
    image = ImageOps.exif_transpose(image).convert("L")
    if mirror_horizontal:
        image = ImageOps.mirror(image)
    if equalize:
        image = ImageOps.equalize(image)
    if blur_smooth:
        from PIL import ImageFilter
        image = image.filter(ImageFilter.GaussianBlur(radius=1))
    if brightness:
        image = ImageEnhance.Brightness(image).enhance(max(0.05, 1.0 + brightness / 100.0))
    if contrast:
        image = ImageEnhance.Contrast(image).enhance(max(0.05, 1.0 + contrast / 100.0))
    target = (max(2, int(px_width)), max(2, int(px_height)))
    if contain_full_image:
        # The preview keeps the visible photograph at its true aspect ratio.
        # A softened, darker cover image fills any remaining panel area, avoiding
        # both geometric stretching and empty letterbox bands. This branch is
        # preview-only; STL sampling still follows crop_to_fit below.
        fitted = ImageOps.contain(image, target, method=Image.LANCZOS)
        background = ImageOps.fit(image, target, method=Image.LANCZOS, centering=(0.5, 0.5))
        from PIL import ImageFilter
        blur_radius = max(2, int(min(target) * 0.035))
        background = background.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        background = ImageEnhance.Brightness(background).enhance(0.52)
        image = background
        image.paste(fitted, ((target[0] - fitted.width) // 2, (target[1] - fitted.height) // 2))
    elif crop_to_fit:
        image = ImageOps.fit(image, target, method=Image.LANCZOS, centering=(0.5, 0.5))
    else:
        image = image.resize(target, Image.LANCZOS)
    heightmap = np.asarray(image, dtype=np.float32) / 255.0
    if gamma != 1.0:
        heightmap = np.power(heightmap, 1.0 / max(0.05, gamma), dtype=np.float32)
    if invert:
        heightmap = 1.0 - heightmap
    return np.clip(heightmap, 0.0, 1.0).astype(np.float32, copy=False)


def heightmap_to_thickness(heightmap: np.ndarray, min_thickness_mm: float, max_thickness_mm: float) -> np.ndarray:
    """Map bright pixels to thin regions and dark pixels to thick regions."""
    if min_thickness_mm <= 0 or max_thickness_mm <= 0:
        raise ValueError("Thickness values must be greater than zero.")
    if min_thickness_mm > max_thickness_mm:
        raise ValueError("Minimum thickness cannot exceed maximum thickness.")
    return (
        float(min_thickness_mm)
        + (1.0 - heightmap) * (float(max_thickness_mm) - float(min_thickness_mm))
    ).astype(np.float32, copy=False)


def _perimeter_faces(rows: int, cols: int, bottom_offset: int) -> np.ndarray:
    """Create walls for the outer perimeter only; never add internal cell walls."""
    top_columns = np.arange(cols - 1, dtype=np.int32)
    top_a, top_b = top_columns, top_columns + 1
    bottom_a = (rows - 1) * cols + top_columns
    bottom_b = bottom_a + 1
    horizontal = np.concatenate((
        np.stack((top_a, top_b, top_a + bottom_offset), axis=1),
        np.stack((top_b, top_b + bottom_offset, top_a + bottom_offset), axis=1),
        np.stack((bottom_a, bottom_a + bottom_offset, bottom_b), axis=1),
        np.stack((bottom_b, bottom_a + bottom_offset, bottom_b + bottom_offset), axis=1),
    ))

    side_rows = np.arange(rows - 1, dtype=np.int32)
    left_a, left_b = side_rows * cols, (side_rows + 1) * cols
    right_a, right_b = side_rows * cols + cols - 1, (side_rows + 1) * cols + cols - 1
    vertical = np.concatenate((
        np.stack((left_a, left_a + bottom_offset, left_b), axis=1),
        np.stack((left_b, left_a + bottom_offset, left_b + bottom_offset), axis=1),
        np.stack((right_a, right_b, right_a + bottom_offset), axis=1),
        np.stack((right_b, right_b + bottom_offset, right_a + bottom_offset), axis=1),
    ))
    return np.concatenate((horizontal, vertical)).astype(np.int32, copy=False)


def _frame_sides(
    border_mm: float = 0.0,
    frame_left_mm: float = 0.0,
    frame_right_mm: float = 0.0,
    frame_top_mm: float = 0.0,
    frame_bottom_mm: float = 0.0,
) -> tuple[float, float, float, float]:
    """Resolve legacy all-around borders and explicit, independently sized sides."""
    sides = [float(frame_left_mm), float(frame_right_mm), float(frame_top_mm), float(frame_bottom_mm)]
    if any(value < 0 for value in sides) or border_mm < 0:
        raise ValueError("Frame widths cannot be negative.")
    # Preserve compatibility with older projects that use one all-around value.
    if border_mm > 0 and not any(sides):
        sides = [float(border_mm)] * 4
    return tuple(sides)


def frame_outer_dimensions(
    width_mm: float,
    height_mm: float,
    border_mm: float = 0.0,
    frame_left_mm: float = 0.0,
    frame_right_mm: float = 0.0,
    frame_top_mm: float = 0.0,
    frame_bottom_mm: float = 0.0,
) -> tuple[float, float]:
    """Return the external panel dimensions while preserving photo dimensions."""
    left, right, top, bottom = _frame_sides(
        border_mm, frame_left_mm, frame_right_mm, frame_top_mm, frame_bottom_mm
    )
    return float(width_mm) + left + right, float(height_mm) + top + bottom


def expand_outer_frame_grid(
    image_grid: np.ndarray,
    width_mm: float,
    height_mm: float,
    border_mm: float = 0.0,
    frame_left_mm: float = 0.0,
    frame_right_mm: float = 0.0,
    frame_top_mm: float = 0.0,
    frame_bottom_mm: float = 0.0,
    frame_value: float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[int, int, int, int]]:
    """Add independent exterior frame bands without resizing or covering the photo.

    The returned grid preserves the photo at its original physical dimensions.
    Extra rows and columns exist only outside its edges and are height-matched
    at the join so the frame is bonded to the photo without a gap.
    """
    grid = np.asarray(image_grid, dtype=np.float32)
    if grid.ndim != 2 or min(grid.shape) < 2:
        raise ValueError("The image grid must contain at least two rows and two columns.")
    rows, cols = grid.shape
    left, right, top, bottom = _frame_sides(
        border_mm, frame_left_mm, frame_right_mm, frame_top_mm, frame_bottom_mm
    )
    density_x = (cols - 1) / max(float(width_mm), 1e-6)
    density_y = (rows - 1) / max(float(height_mm), 1e-6)
    left_n = max(1, int(round(left * density_x))) if left > 0 else 0
    right_n = max(1, int(round(right * density_x))) if right > 0 else 0
    top_n = max(1, int(round(top * density_y))) if top > 0 else 0
    bottom_n = max(1, int(round(bottom * density_y))) if bottom > 0 else 0
    fill = float(grid.max() if frame_value is None else frame_value)
    outer = np.full((rows + top_n + bottom_n, cols + left_n + right_n), fill, dtype=np.float32)
    image_row = slice(bottom_n, bottom_n + rows)
    image_col = slice(left_n, left_n + cols)
    outer[image_row, image_col] = grid

    # The frame is strictly outside the photo.  Its vertices immediately next
    # to each photo edge use the *same* height as that edge.  The remaining
    # frame width transitions outward to the requested frame height.  This
    # creates one continuous watertight surface: no empty seam and no border
    # cell can cover an image pixel.
    def blend_edge(edge: np.ndarray, count: int, far_to_near: bool) -> np.ndarray:
        if count <= 0:
            return np.empty((len(edge), 0), dtype=np.float32)
        ramp = np.linspace(1.0, 0.0, count, dtype=np.float32)
        if not far_to_near:
            ramp = ramp[::-1]
        return edge[:, None] * (1.0 - ramp[None, :]) + fill * ramp[None, :]

    if left_n:
        outer[image_row, :left_n] = blend_edge(grid[:, 0], left_n, far_to_near=True)
    if right_n:
        outer[image_row, left_n + cols:] = blend_edge(grid[:, -1], right_n, far_to_near=False)
    if bottom_n:
        outer[:bottom_n, image_col] = blend_edge(grid[0, :], bottom_n, far_to_near=True).T
    if top_n:
        outer[bottom_n + rows:, image_col] = blend_edge(grid[-1, :], top_n, far_to_near=False).T

    # Blend the four exterior corners from their nearest photo corner.  Using
    # the larger horizontal/vertical distance keeps both adjoining frame bands
    # continuous while leaving the photo rectangle completely unchanged.
    def corner_block(corner_value: float, y_ramp: np.ndarray, x_ramp: np.ndarray) -> np.ndarray:
        ramp = np.maximum(y_ramp[:, None], x_ramp[None, :])
        return (corner_value * (1.0 - ramp) + fill * ramp).astype(np.float32)

    if left_n and bottom_n:
        outer[:bottom_n, :left_n] = corner_block(
            float(grid[0, 0]), np.linspace(1.0, 0.0, bottom_n), np.linspace(1.0, 0.0, left_n)
        )
    if right_n and bottom_n:
        outer[:bottom_n, left_n + cols:] = corner_block(
            float(grid[0, -1]), np.linspace(1.0, 0.0, bottom_n), np.linspace(0.0, 1.0, right_n)
        )
    if left_n and top_n:
        outer[bottom_n + rows:, :left_n] = corner_block(
            float(grid[-1, 0]), np.linspace(0.0, 1.0, top_n), np.linspace(1.0, 0.0, left_n)
        )
    if right_n and top_n:
        outer[bottom_n + rows:, left_n + cols:] = corner_block(
            float(grid[-1, -1]), np.linspace(0.0, 1.0, top_n), np.linspace(0.0, 1.0, right_n)
        )

    image_x = np.linspace(0.0, float(width_mm), cols, dtype=np.float32)
    image_y = np.linspace(0.0, float(height_mm), rows, dtype=np.float32)
    left_x = np.linspace(-left, 0.0, left_n + 1, dtype=np.float32)[:-1] if left_n else np.empty(0, dtype=np.float32)
    right_x = np.linspace(float(width_mm), float(width_mm) + right, right_n + 1, dtype=np.float32)[1:] if right_n else np.empty(0, dtype=np.float32)
    bottom_y = np.linspace(-bottom, 0.0, bottom_n + 1, dtype=np.float32)[:-1] if bottom_n else np.empty(0, dtype=np.float32)
    top_y = np.linspace(float(height_mm), float(height_mm) + top, top_n + 1, dtype=np.float32)[1:] if top_n else np.empty(0, dtype=np.float32)
    return np.concatenate((left_x, image_x, right_x)), np.concatenate((bottom_y, image_y, top_y)), outer, (left_n, right_n, top_n, bottom_n)


def build_plane_mesh(
    thickness_mm: np.ndarray,
    width_mm: float,
    height_mm: float,
    base_thickness_mm: float = 0.6,
    border_mm: float = 0.0,
    forward_relief_mm: float = 0.0,
    frame_left_mm: float = 0.0,
    frame_right_mm: float = 0.0,
    frame_top_mm: float = 0.0,
    frame_bottom_mm: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Build a closed Plane mesh with image dimensions and frame dimensions kept separate."""
    if thickness_mm.ndim != 2 or min(thickness_mm.shape) < 2:
        raise ValueError("The heightmap must contain at least two rows and two columns.")
    if width_mm <= 0 or height_mm <= 0:
        raise ValueError("Width and height must be greater than zero.")
    if base_thickness_mm < 0:
        raise ValueError("Base thickness cannot be negative.")

    image_depth = np.asarray(thickness_mm, dtype=np.float32)
    image_total = image_depth + float(base_thickness_mm)
    # Signed relief depth is normalized against the image contrast: a positive
    # value raises the dark/detail regions and a negative value engraves the
    # same regions. The UI may choose any depth from 0 to 10 mm while the
    # physical minimum thickness remains underneath.
    if abs(forward_relief_mm) > 1e-7:
        spread = float(image_depth.max() - image_depth.min())
        if spread > 1e-7:
            normalized = (image_depth - image_depth.min()) / spread
            detail = normalized if forward_relief_mm > 0 else (1.0 - normalized)
            image_total = float(base_thickness_mm) + float(image_depth.min()) + detail * abs(float(forward_relief_mm))
    frame_height = float(image_total.max())
    x, y, total, _ = expand_outer_frame_grid(
        image_total, width_mm, height_mm, border_mm, frame_left_mm, frame_right_mm,
        frame_top_mm, frame_bottom_mm, frame_value=frame_height,
    )
    rows, cols = total.shape
    if rows * cols > MAX_SAMPLES:
        raise ValueError(f"Frame configuration creates {rows * cols:,} samples; maximum supported is {MAX_SAMPLES:,}.")
    yy, xx = np.meshgrid(y, x, indexing="ij")
    top_vertices = np.stack((xx, yy, total), axis=-1).reshape(-1, 3)
    bottom_vertices = np.stack((xx, yy, np.zeros_like(total)), axis=-1).reshape(-1, 3)
    vertices = np.concatenate((top_vertices, bottom_vertices)).astype(np.float32, copy=False)

    r = np.arange(rows - 1, dtype=np.int32)[:, None]
    c = np.arange(cols - 1, dtype=np.int32)[None, :]
    a = (r * cols + c).ravel()
    b, d = a + 1, a + cols
    e = d + 1
    top_faces = np.concatenate((np.stack((a, d, b), axis=1), np.stack((b, d, e), axis=1)))
    bottom_faces = np.concatenate((
        np.stack((a + rows * cols, b + rows * cols, d + rows * cols), axis=1),
        np.stack((b + rows * cols, e + rows * cols, d + rows * cols), axis=1),
    ))
    walls = _perimeter_faces(rows, cols, rows * cols)
    faces = np.concatenate((top_faces, bottom_faces, walls)).astype(np.int32, copy=False)
    return vertices, faces


def build_mesh(
    thickness_mm: np.ndarray,
    width_mm: float,
    height_mm: float,
    base_thickness_mm: float = 0.6,
    curve_degrees: float = 0.0,
    border_mm: float = 0.0,
    shape: str = "flat",
    sphere_diameter_mm: float = 0.0,
    sphere_wall_thickness_mm: float = 0.0,
    sphere_bottom_hole_mm: float = 0.0,
    sphere_top_hole_mm: float = 0.0,
    sphere_angular_height: float = 0.0,
    sphere_angular_width: float = 0.0,
    cylinder_diameter_mm: float = 0.0,
    cylinder_height_mm: float = 0.0,
    cylinder_thickness_mm: float = 0.0,
    cylinder_ledge_mm: float = 0.0,
    forward_relief_mm: float = 0.0,
    frame_left_mm: float = 0.0,
    frame_right_mm: float = 0.0,
    frame_top_mm: float = 0.0,
    frame_bottom_mm: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Compatibility entry point for a Plane-only UI and its live preview."""
    if shape not in ("flat", "plane", "") or curve_degrees:
        raise ValueError("This core module supports uncurved Plane lithophanes only.")
    return build_plane_mesh(
        thickness_mm, width_mm, height_mm, base_thickness_mm, border_mm,
        forward_relief_mm, frame_left_mm, frame_right_mm, frame_top_mm, frame_bottom_mm,
    )


def write_stl(vertices: np.ndarray, faces: np.ndarray, output_path: str, name: str = "plane_lithophane", chunk_size: int = 250_000) -> None:
    """Write a binary STL in chunks, keeping memory stable for high resolution."""
    with Path(output_path).open("wb") as stream:
        header = f"Lithophane Plane export: {name}".encode("utf-8")
        stream.write(header[:80].ljust(80, b"\0"))
        stream.write(struct.pack("<I", len(faces)))
        for start in range(0, len(faces), chunk_size):
            chunk_faces = faces[start:start + chunk_size]
            triangles = vertices[chunk_faces]
            normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
            normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-8)
            records = np.empty(len(chunk_faces), dtype=STL_RECORD_DTYPE)
            records["normal"] = normals
            records["v1"], records["v2"], records["v3"] = triangles[:, 0], triangles[:, 1], triangles[:, 2]
            records["attribute"] = 0
            stream.write(records.tobytes())


def generate_plane_lithophane(
    image_path: str,
    output_stl_path: str,
    width_mm: float = 120.0,
    height_mm: float = 150.0,
    px_per_mm: float = 6.0,
    min_thickness_mm: float = 0.8,
    max_thickness_mm: float = 3.0,
    base_thickness_mm: float = 0.6,
    border_mm: float = 0.0,
    invert: bool = False,
    equalize: bool = False,
    blur_smooth: bool = False,
    mirror_horizontal: bool = False,
    crop_to_fit: bool = True,
    brightness: float = 0.0,
    contrast: float = 0.0,
    gamma: float = 1.0,
    forward_relief_mm: float = 0.0,
    frame_left_mm: float = 0.0,
    frame_right_mm: float = 0.0,
    frame_top_mm: float = 0.0,
    frame_bottom_mm: float = 0.0,
    progress_cb=None,
) -> dict:
    """Generate a high-resolution, watertight Plane lithophane STL without a frame by default."""
    columns, rows = max(2, int(width_mm * px_per_mm)), max(2, int(height_mm * px_per_mm))
    samples = columns * rows
    if samples > MAX_SAMPLES:
        raise ValueError(f"Resolution creates {samples:,} samples; maximum supported is {MAX_SAMPLES:,}.")
    report = lambda value, text: progress_cb(value, text) if progress_cb else None
    report(5, "Reading image…")
    heightmap = image_to_heightmap(
        image_path, columns, rows, invert, equalize, blur_smooth,
        mirror_horizontal, crop_to_fit, brightness, contrast, gamma,
    )
    report(30, "Computing thickness…")
    thickness = heightmap_to_thickness(heightmap, min_thickness_mm, max_thickness_mm)
    report(55, "Building watertight Plane mesh…")
    grid_x, grid_y, _, _ = expand_outer_frame_grid(
        thickness, width_mm, height_mm, border_mm, frame_left_mm, frame_right_mm,
        frame_top_mm, frame_bottom_mm,
    )
    outer_samples = len(grid_x) * len(grid_y)
    if outer_samples > MAX_SAMPLES:
        raise ValueError(f"Frame configuration creates {outer_samples:,} samples; maximum supported is {MAX_SAMPLES:,}.")
    vertices, faces = build_plane_mesh(
        thickness, width_mm, height_mm, base_thickness_mm, border_mm, forward_relief_mm,
        frame_left_mm, frame_right_mm, frame_top_mm, frame_bottom_mm,
    )
    outer_width_mm, outer_height_mm = frame_outer_dimensions(
        width_mm, height_mm, border_mm, frame_left_mm, frame_right_mm, frame_top_mm, frame_bottom_mm
    )
    report(78, "Writing STL…")
    write_stl(vertices, faces, output_stl_path)
    report(100, "Done")
    return {
        "vertices": len(vertices),
        "faces": len(faces),
        "heightmap": heightmap,
        "thickness": thickness,
        "top_grid": vertices[: len(grid_x) * len(grid_y)].reshape(len(grid_y), len(grid_x), 3),
        "sample_width": columns,
        "sample_height": rows,
        "sample_count": samples,
        "outer_sample_width": len(grid_x),
        "outer_sample_height": len(grid_y),
        "outer_sample_count": outer_samples,
        "estimated_stl_bytes": 84 + len(faces) * 50,
        "forward_relief_mm": float(forward_relief_mm),
        "outer_width_mm": outer_width_mm,
        "outer_height_mm": outer_height_mm,
        "frame_sides_mm": _frame_sides(border_mm, frame_left_mm, frame_right_mm, frame_top_mm, frame_bottom_mm),
    }


def generate_lithophane(
    image_path: str,
    output_stl_path: str,
    width_mm: float = 120.0,
    height_mm: float = 150.0,
    px_per_mm: float = 6.0,
    min_thickness_mm: float = 0.8,
    max_thickness_mm: float = 3.0,
    base_thickness_mm: float = 0.6,
    curve_degrees: float = 0.0,
    border_mm: float = 0.0,
    invert: bool = False,
    equalize: bool = False,
    blur_smooth: bool = False,
    mirror_horizontal: bool = False,
    crop_to_fit: bool = True,
    brightness: float = 0.0,
    contrast: float = 0.0,
    gamma: float = 1.0,
    forward_relief_mm: float = 0.0,
    frame_left_mm: float = 0.0,
    frame_right_mm: float = 0.0,
    frame_top_mm: float = 0.0,
    frame_bottom_mm: float = 0.0,
    shape: str = "flat",
    sphere_diameter_mm: float = 0.0,
    sphere_wall_thickness_mm: float = 0.0,
    sphere_bottom_hole_mm: float = 0.0,
    sphere_top_hole_mm: float = 0.0,
    sphere_angular_height: float = 0.0,
    sphere_angular_width: float = 0.0,
    cylinder_diameter_mm: float = 0.0,
    cylinder_height_mm: float = 0.0,
    cylinder_thickness_mm: float = 0.0,
    cylinder_ledge_mm: float = 0.0,
    lang: str = "ar",
    progress_cb=None,
) -> dict:
    """Drop-in core API for a Plane-only application.

    The legacy sphere/cylinder arguments are accepted only so an existing UI can
    call this module unchanged. They are intentionally ignored; Plane is the
    sole supported product in this focused engine.
    """
    if shape not in ("flat", "plane", ""):
        raise ValueError("This core module supports Plane lithophanes only.")
    return generate_plane_lithophane(
        image_path=image_path,
        output_stl_path=output_stl_path,
        width_mm=width_mm,
        height_mm=height_mm,
        px_per_mm=px_per_mm,
        min_thickness_mm=min_thickness_mm,
        max_thickness_mm=max_thickness_mm,
        base_thickness_mm=base_thickness_mm,
        border_mm=border_mm,
        invert=invert,
        equalize=equalize,
        blur_smooth=blur_smooth,
        mirror_horizontal=mirror_horizontal,
        crop_to_fit=crop_to_fit,
        brightness=brightness,
        contrast=contrast,
        gamma=gamma,
        forward_relief_mm=forward_relief_mm,
        frame_left_mm=frame_left_mm,
        frame_right_mm=frame_right_mm,
        frame_top_mm=frame_top_mm,
        frame_bottom_mm=frame_bottom_mm,
        progress_cb=progress_cb,
    )
