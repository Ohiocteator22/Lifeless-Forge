# tests/test_security.py
import os
import tempfile
import unittest
import zipfile
import tarfile
from pathlib import Path

# Add the parent directory to sys.path so we can import forge
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forge.core import safe_extract_zip, safe_extract_tar

class TestZipTraversal(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name) / "extract"
        self.output_dir.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_zip_with_file(self, filename, content=b"test"):
        zf_path = os.path.join(self.temp_dir.name, "test.zip")
        with zipfile.ZipFile(zf_path, 'w') as zf:
            zf.writestr(filename, content)
        return zf_path

    def test_normal_file(self):
        zf_path = self._create_zip_with_file("normal.txt")
        with zipfile.ZipFile(zf_path, 'r') as zf:
            safe_extract_zip(zf, self.output_dir)
        self.assertTrue((self.output_dir / "normal.txt").exists())

    def test_nested_directory(self):
        zf_path = self._create_zip_with_file("a/b/c/nested.txt")
        with zipfile.ZipFile(zf_path, 'r') as zf:
            safe_extract_zip(zf, self.output_dir)
        self.assertTrue((self.output_dir / "a/b/c/nested.txt").exists())

    def test_traversal_dot_dot(self):
        zf_path = self._create_zip_with_file("../evil.txt")
        with zipfile.ZipFile(zf_path, 'r') as zf:
            with self.assertRaises(ValueError) as ctx:
                safe_extract_zip(zf, self.output_dir)
            self.assertIn("traversal", str(ctx.exception))

    def test_traversal_double_dot_dot(self):
        zf_path = self._create_zip_with_file("../../evil.txt")
        with zipfile.ZipFile(zf_path, 'r') as zf:
            with self.assertRaises(ValueError) as ctx:
                safe_extract_zip(zf, self.output_dir)
            self.assertIn("traversal", str(ctx.exception))

    def test_absolute_path_unix(self):
        zf_path = self._create_zip_with_file("/etc/passwd")
        with zipfile.ZipFile(zf_path, 'r') as zf:
            with self.assertRaises(ValueError) as ctx:
                safe_extract_zip(zf, self.output_dir)
            self.assertIn("Absolute", str(ctx.exception))

    def test_absolute_path_windows(self):
        zf_path = self._create_zip_with_file("C:/Windows/System32/drivers/etc/hosts")
        with zipfile.ZipFile(zf_path, 'r') as zf:
            with self.assertRaises(ValueError) as ctx:
                safe_extract_zip(zf, self.output_dir)
            self.assertIn("Absolute", str(ctx.exception))

    def test_windows_traversal(self):
        zf_path = self._create_zip_with_file("..\\..\\evil.txt")
        with zipfile.ZipFile(zf_path, 'r') as zf:
            with self.assertRaises(ValueError) as ctx:
                safe_extract_zip(zf, self.output_dir)
            self.assertIn("traversal", str(ctx.exception))


class TestTarTraversal(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name) / "extract"
        self.output_dir.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_tar_with_file(self, filename, content=b"test"):
        tar_path = os.path.join(self.temp_dir.name, "test.tar")
        with tarfile.open(tar_path, 'w') as tf:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(content)
                tmp.flush()
                tf.add(tmp.name, arcname=filename)
            os.unlink(tmp.name)
        return tar_path

    def test_normal_file(self):
        tar_path = self._create_tar_with_file("normal.txt")
        with tarfile.open(tar_path, 'r') as tf:
            safe_extract_tar(tf, self.output_dir)
        self.assertTrue((self.output_dir / "normal.txt").exists())

    def test_nested_directory(self):
        tar_path = self._create_tar_with_file("a/b/c/nested.txt")
        with tarfile.open(tar_path, 'r') as tf:
            safe_extract_tar(tf, self.output_dir)
        self.assertTrue((self.output_dir / "a/b/c/nested.txt").exists())

    def test_traversal_dot_dot(self):
        tar_path = self._create_tar_with_file("../evil.txt")
        with tarfile.open(tar_path, 'r') as tf:
            with self.assertRaises(ValueError) as ctx:
                safe_extract_tar(tf, self.output_dir)
            self.assertIn("traversal", str(ctx.exception))

    def test_absolute_path_unix(self):
        tar_path = self._create_tar_with_file("/etc/passwd")
        with tarfile.open(tar_path, 'r') as tf:
            with self.assertRaises(ValueError) as ctx:
                safe_extract_tar(tf, self.output_dir)
            self.assertIn("Absolute", str(ctx.exception))

    def test_symlink(self):
        tar_path = os.path.join(self.temp_dir.name, "test.tar")
        with tarfile.open(tar_path, 'w') as tf:
            info = tarfile.TarInfo(name="symlink")
            info.type = tarfile.SYMTYPE
            info.linkname = "target"
            tf.addfile(info)
        with tarfile.open(tar_path, 'r') as tf:
            with self.assertRaises(ValueError) as ctx:
                safe_extract_tar(tf, self.output_dir)
            self.assertIn("Symlink", str(ctx.exception))

    def test_hardlink(self):
        tar_path = os.path.join(self.temp_dir.name, "test.tar")
        with tarfile.open(tar_path, 'w') as tf:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(b"data")
                tmp.flush()
                tf.add(tmp.name, arcname="file1")
                info = tarfile.TarInfo(name="file2")
                info.type = tarfile.LNKTYPE
                info.linkname = "file1"
                tf.addfile(info)
            os.unlink(tmp.name)
        with tarfile.open(tar_path, 'r') as tf:
            with self.assertRaises(ValueError) as ctx:
                safe_extract_tar(tf, self.output_dir)
            self.assertIn("hardlink", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
