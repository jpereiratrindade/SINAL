"""Matemática tridimensional (vetores, matrizes, projeção) para o renderizador 3D."""

from __future__ import annotations

import math
from typing import NamedTuple


class Vec3(NamedTuple):
    x: float
    y: float
    z: float

    def __add__(self, other: Vec3) -> Vec3:
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vec3) -> Vec3:
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> Vec3:
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    def __rmul__(self, scalar: float) -> Vec3:
        return self * scalar

    def dot(self, other: Vec3) -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: Vec3) -> Vec3:
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def normalize(self) -> Vec3:
        l = self.length()
        if l < 1e-9:
            return Vec3(0.0, 0.0, 0.0)
        return Vec3(self.x / l, self.y / l, self.z / l)

    def lerp(self, other: Vec3, t: float) -> Vec3:
        return Vec3(
            self.x + (other.x - self.x) * t,
            self.y + (other.y - self.y) * t,
            self.z + (other.z - self.z) * t,
        )


def rotate_x(p: Vec3, angle_rad: float) -> Vec3:
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return Vec3(p.x, p.y * cos_a - p.z * sin_a, p.y * sin_a + p.z * cos_a)


def rotate_y(p: Vec3, angle_rad: float) -> Vec3:
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return Vec3(p.x * cos_a + p.z * sin_a, p.y, -p.x * sin_a + p.z * cos_a)


def rotate_z(p: Vec3, angle_rad: float) -> Vec3:
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return Vec3(p.x * cos_a - p.y * sin_a, p.x * sin_a + p.y * cos_a, p.z)


class Camera3D:
    """Câmera de projeção em perspectiva 3D."""

    def __init__(
        self,
        position: Vec3 = Vec3(0.0, 0.35, 2.3),
        target: Vec3 = Vec3(0.0, 0.25, 0.0),
        fov_deg: float = 40.0,
    ) -> None:
        self.position = position
        self.target = target
        self.fov_rad = math.radians(fov_deg)

        # Vetores de base da câmera
        forward = (target - position).normalize()
        world_up = Vec3(0.0, 1.0, 0.0)
        right = forward.cross(world_up).normalize()
        up = right.cross(forward).normalize()

        self.forward = forward
        self.right = right
        self.up = up

    def project(self, p_world: Vec3, width: int, height: int) -> tuple[float, float, float] | None:
        """Projeta ponto 3D para coordenadas 2D na tela (x, y) e profundidade z."""
        rel = p_world - self.position
        # Coordenadas no espaço da câmera
        x_cam = rel.dot(self.right)
        y_cam = rel.dot(self.up)
        z_cam = rel.dot(self.forward)

        if z_cam <= 0.1:  # Ponto atrás ou muito próximo da câmera
            return None

        aspect = width / height
        tan_half_fov = math.tan(self.fov_rad / 2.0)

        # Projeção perspectiva normalizada [-1, 1]
        x_ndc = x_cam / (z_cam * tan_half_fov * aspect)
        y_ndc = y_cam / (z_cam * tan_half_fov)

        # Mapeia para pixels na tela (origem no topo-esquerdo)
        screen_x = (x_ndc + 1.0) * 0.5 * width
        screen_y = (1.0 - y_ndc) * 0.5 * height
        return (screen_x, screen_y, z_cam)
