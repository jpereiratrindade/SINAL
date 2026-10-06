"""Exportador de malhas e rigs para o formato padrão GLTF 2.0 / GLB."""

from __future__ import annotations

import json
from pathlib import Path
import struct
from typing import Any

from sinal.avatar.sina import SinaAvatarModel, SinaAnatomy
from sinal.render.math3d import Vec3
from sinal.render.poses import POSE_REST, BodyPose3D


def export_sina_glb(output_path: str | Path, pose: BodyPose3D | None = None) -> Path:
    """Exporta o avatar SINA para um arquivo 3D binário padrão .glb (glTF 2.0)."""
    dest = Path(output_path)
    current_pose = pose or POSE_REST
    sina = SinaAvatarModel()
    primitives = sina.build_scene_primitives(current_pose)

    vertices: list[float] = []
    normals: list[float] = []
    colors: list[float] = []
    indices: list[int] = []

    # Gera malha poligonal para cada elemento da SINA
    for _depth, prim_type, params in primitives:
        if prim_type == "sphere":
            center, radius, color, _ = params
            _tessellate_sphere(center, radius, radius, radius, color, vertices, normals, colors, indices)
        elif prim_type == "ellipsoid":
            center, radii, color, _ = params
            _tessellate_sphere(center, radii.x, radii.y, radii.z, color, vertices, normals, colors, indices)
        elif prim_type == "capsule":
            p0, p1, radius, color, _ = params
            _tessellate_cylinder(p0, p1, radius, color, vertices, normals, colors, indices)

    # Converte arrays para bytes estruturados
    num_verts = len(vertices) // 3
    num_indices = len(indices)

    v_bytes = struct.pack(f"<{len(vertices)}f", *vertices)
    n_bytes = struct.pack(f"<{len(normals)}f", *normals)
    c_bytes = struct.pack(f"<{len(colors)}f", *colors)
    i_bytes = struct.pack(f"<{len(indices)}I", *indices)

    # Buffer combinado
    bin_buffer = v_bytes + n_bytes + c_bytes + i_bytes
    # Alinhamento em 4 bytes
    padding = (4 - (len(bin_buffer) % 4)) % 4
    bin_buffer += b"\x00" * padding

    v_offset = 0
    n_offset = len(v_bytes)
    c_offset = n_offset + len(n_bytes)
    i_offset = c_offset + len(c_bytes)

    min_pos = [min(vertices[i::3]) for i in range(3)] if vertices else [0, 0, 0]
    max_pos = [max(vertices[i::3]) for i in range(3)] if vertices else [0, 0, 0]

    gltf_dict: dict[str, Any] = {
        "asset": {"version": "2.0", "generator": "SINAL-SINA-3D-Engine"},
        "scenes": [{"nodes": [0]}],
        "scene": 0,
        "nodes": [{"name": "SINA_Interpreter", "mesh": 0}],
        "meshes": [
            {
                "name": "SINA_BodyMesh",
                "primitives": [
                    {
                        "attributes": {
                            "POSITION": 0,
                            "NORMAL": 1,
                            "COLOR_0": 2,
                        },
                        "indices": 3,
                        "mode": 4,  # TRIANGLES
                    }
                ],
            }
        ],
        "accessors": [
            {
                "bufferView": 0,
                "byteOffset": 0,
                "componentType": 5126,  # FLOAT
                "count": num_verts,
                "type": "VEC3",
                "max": max_pos,
                "min": min_pos,
            },
            {
                "bufferView": 1,
                "byteOffset": 0,
                "componentType": 5126,  # FLOAT
                "count": num_verts,
                "type": "VEC3",
            },
            {
                "bufferView": 2,
                "byteOffset": 0,
                "componentType": 5126,  # FLOAT
                "count": num_verts,
                "type": "VEC3",
            },
            {
                "bufferView": 3,
                "byteOffset": 0,
                "componentType": 5125,  # UNSIGNED_INT
                "count": num_indices,
                "type": "SCALAR",
            },
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": v_offset, "byteLength": len(v_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": n_offset, "byteLength": len(n_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": c_offset, "byteLength": len(c_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": i_offset, "byteLength": len(i_bytes), "target": 34963},
        ],
        "buffers": [{"byteLength": len(bin_buffer)}],
    }

    json_str = json.dumps(gltf_dict, separators=(",", ":"))
    json_bytes = json_str.encode("utf-8")
    json_pad = (4 - (len(json_bytes) % 4)) % 4
    json_bytes += b" " * json_pad

    # GLB Header
    header_magic = b"glTF"
    header_version = 2
    json_chunk_len = len(json_bytes)
    json_chunk_type = b"JSON"
    bin_chunk_len = len(bin_buffer)
    bin_chunk_type = b"BIN\x00"

    total_len = 12 + 8 + json_chunk_len + 8 + bin_chunk_len
    header = struct.pack("<4sII", header_magic, header_version, total_len)

    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        f.write(header)
        f.write(struct.pack("<I4s", json_chunk_len, json_chunk_type))
        f.write(json_bytes)
        f.write(struct.pack("<I4s", bin_chunk_len, bin_chunk_type))
        f.write(bin_buffer)

    return dest


def _tessellate_sphere(
    c: Vec3, rx: float, ry: float, rz: float, color: tuple[int, int, int],
    vertices: list[float], normals: list[float], colors: list[float], indices: list[int]
) -> None:
    import math
    lat_steps = 12
    lon_steps = 16
    start_idx = len(vertices) // 3
    cr, cg, cb = color[0] / 255.0, color[1] / 255.0, color[2] / 255.0

    for i in range(lat_steps + 1):
        theta = i * math.pi / lat_steps
        sin_t, cos_t = math.sin(theta), math.cos(theta)
        for j in range(lon_steps + 1):
            phi = j * 2.0 * math.pi / lon_steps
            sin_p, cos_p = math.sin(phi), math.cos(phi)

            nx = sin_t * cos_p
            ny = cos_t
            nz = sin_t * sin_p

            px = c.x + nx * rx
            py = c.y + ny * ry
            pz = c.z + nz * rz

            vertices.extend([px, py, pz])
            normals.extend([nx, ny, nz])
            colors.extend([cr, cg, cb])

    for i in range(lat_steps):
        for j in range(lon_steps):
            first = start_idx + (i * (lon_steps + 1)) + j
            second = first + lon_steps + 1
            indices.extend([first, second, first + 1])
            indices.extend([second, second + 1, first + 1])


def _tessellate_cylinder(
    p0: Vec3, p1: Vec3, r: float, color: tuple[int, int, int],
    vertices: list[float], normals: list[float], colors: list[float], indices: list[int]
) -> None:
    import math
    axis = (p1 - p0)
    length = axis.length()
    if length < 1e-6:
        return
    dir_v = axis * (1.0 / length)

    # Vetores perpendiculares ortonormais
    up = Vec3(0, 1, 0) if abs(dir_v.y) < 0.9 else Vec3(1, 0, 0)
    right = dir_v.cross(up).normalize()
    up = right.cross(dir_v).normalize()

    segments = 12
    start_idx = len(vertices) // 3
    cr, cg, cb = color[0] / 255.0, color[1] / 255.0, color[2] / 255.0

    for i in range(segments + 1):
        angle = i * 2.0 * math.pi / segments
        ca, sa = math.cos(angle), math.sin(angle)
        radial_normal = right * ca + up * sa
        offset = radial_normal * r

        # Vértice na base
        v0 = p0 + offset
        vertices.extend([v0.x, v0.y, v0.z])
        normals.extend([radial_normal.x, radial_normal.y, radial_normal.z])
        colors.extend([cr, cg, cb])

        # Vértice no topo
        v1 = p1 + offset
        vertices.extend([v1.x, v1.y, v1.z])
        normals.extend([radial_normal.x, radial_normal.y, radial_normal.z])
        colors.extend([cr, cg, cb])

    for i in range(segments):
        i0 = start_idx + (i * 2)
        i1 = i0 + 1
        i2 = start_idx + ((i + 1) * 2)
        i3 = i2 + 1
        indices.extend([i0, i1, i2])
        indices.extend([i1, i3, i2])
