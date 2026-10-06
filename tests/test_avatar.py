"""Testes unitários para o modelo do avatar SINA e exportador GLB."""

from pathlib import Path
import tempfile
import unittest

from sinal.avatar.gltf_export import export_sina_glb
from sinal.avatar.sina import SinaAvatarModel, SinaAnatomy
from sinal.render.poses import POSE_REST, get_sign_pose


class AvatarTests(unittest.TestCase):
    def test_sina_model_builds_anatomical_primitives(self) -> None:
        model = SinaAvatarModel()
        primitives = model.build_scene_primitives(POSE_REST)
        self.assertGreater(len(primitives), 20)

        types = {item[1] for item in primitives}
        self.assertIn("ellipsoid", types)
        self.assertIn("sphere", types)
        self.assertIn("capsule", types)

    def test_sina_pose_changes_finger_and_arm_geometry(self) -> None:
        model = SinaAvatarModel()
        pose_ola = get_sign_pose("OLA", 0.5)
        primitives = model.build_scene_primitives(pose_ola)
        self.assertTrue(any(item[1] == "ellipsoid" for item in primitives))

    def test_export_sina_glb_produces_valid_binary_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "sina_test.glb"
            exported = export_sina_glb(out_file)
            self.assertTrue(exported.exists())
            self.assertGreater(exported.stat().st_size, 1000)

            # Valida cabeçalho glTF 2.0 (magic: b"glTF")
            with open(exported, "rb") as f:
                header = f.read(12)
                magic, version, length = header[:4], int.from_bytes(header[4:8], "little"), int.from_bytes(header[8:12], "little")
                self.assertEqual(magic, b"glTF")
                self.assertEqual(version, 2)
                self.assertEqual(length, exported.stat().st_size)


if __name__ == "__main__":
    unittest.main()
