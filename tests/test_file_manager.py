"""Unit tests for FileManager."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'SlicerAICopilot'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
import tempfile
import shutil
from unittest.mock import Mock, patch

from SlicerAICopilotLib.file_manager import FileManager
from SlicerAICopilotLib.utils import get_file_type, scan_folder_for_files, group_dicom_series


class TestFileType(unittest.TestCase):

    def test_dicom_detection(self):
        self.assertEqual(get_file_type("scan.dcm"), "DICOM")
        self.assertEqual(get_file_type("scan.DICOM"), "DICOM")

    def test_nifti_detection(self):
        self.assertEqual(get_file_type("volume.nii"), "NIfTI")
        self.assertEqual(get_file_type("volume.nii.gz"), "NIfTI")

    def test_nrrd_detection(self):
        self.assertEqual(get_file_type("volume.nrrd"), "NRRD")
        self.assertEqual(get_file_type("volume.nhdr"), "NRRD")

    def test_model_detection(self):
        for ext in [".vtk", ".stl", ".obj", ".ply"]:
            self.assertEqual(get_file_type(f"model{ext}"), "MODEL")

    def test_unknown_file(self):
        self.assertIsNone(get_file_type("readme.txt"))
        self.assertIsNone(get_file_type("data.csv"))

    def test_case_insensitive(self):
        self.assertEqual(get_file_type("SCAN.DCM"), "DICOM")
        self.assertEqual(get_file_type("MODEL.STL"), "MODEL")

    def _write_temp_and_detect(self, payload):
        fd, path = tempfile.mkstemp(suffix='')
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(payload)
            return get_file_type(path)
        finally:
            os.unlink(path)

    def test_dicom_detection_by_content(self):
        self.assertEqual(self._write_temp_and_detect(b'\x00' * 128 + b'DICM'), "DICOM")

    def test_vtk_detection_by_content(self):
        self.assertEqual(self._write_temp_and_detect(b'# vtk DataFile Version 3.0'), "MODEL")

    def test_nrrd_detection_by_content(self):
        self.assertEqual(self._write_temp_and_detect(b'NRRD0004'), "NRRD")


class TestScanFolder(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_scan_empty_folder(self):
        result = scan_folder_for_files(self.test_dir)
        self.assertEqual(result["nifti_files"], [])
        self.assertEqual(result["model_files"], [])

    def test_scan_with_nifti(self):
        nifti_path = os.path.join(self.test_dir, "brain.nii.gz")
        with open(nifti_path, 'w') as f:
            f.write("fake")
        result = scan_folder_for_files(self.test_dir)
        self.assertEqual(len(result["nifti_files"]), 1)
        self.assertIn("brain.nii.gz", result["nifti_files"][0])

    def test_scan_with_models(self):
        for ext in [".vtk", ".stl"]:
            path = os.path.join(self.test_dir, f"model{ext}")
            with open(path, 'w') as f:
                f.write("fake")
        result = scan_folder_for_files(self.test_dir)
        self.assertEqual(len(result["model_files"]), 2)

    def test_scan_recursive(self):
        subdir = os.path.join(self.test_dir, "subdir")
        os.makedirs(subdir)
        path = os.path.join(subdir, "deep.nii")
        with open(path, 'w') as f:
            f.write("fake")
        result = scan_folder_for_files(self.test_dir)
        self.assertEqual(len(result["nifti_files"]), 1)

    def test_scan_separates_other_files(self):
        path = os.path.join(self.test_dir, "notes.txt")
        with open(path, 'w') as f:
            f.write("notes")
        result = scan_folder_for_files(self.test_dir)
        self.assertEqual(len(result["other_files"]), 1)


class TestGroupDicom(unittest.TestCase):

    def test_empty_list(self):
        result = group_dicom_series([])
        self.assertEqual(result, [])

    def test_groups_by_directory(self):
        files = ["/data/scan1.dcm", "/data/scan2.dcm", "/data2/scan3.dcm"]
        result = group_dicom_series(files)
        self.assertEqual(len(result), 2)

    def test_single_directory(self):
        files = ["/data/scan1.dcm", "/data/scan2.dcm"]
        result = group_dicom_series(files)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]), 2)


class TestFileManager(unittest.TestCase):

    def setUp(self):
        self.fm = FileManager()
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_scan_folder_not_found(self):
        result = self.fm.scan_folder("/nonexistent/path")
        self.assertIn("error", result)

    def test_scan_folder_success(self):
        nifti = os.path.join(self.test_dir, "volume.nii")
        with open(nifti, 'w') as f:
            f.write("fake")
        result = self.fm.scan_folder(self.test_dir)
        self.assertIn("nifti_files", result)
        self.assertEqual(len(result["nifti_files"]), 1)

    def test_get_detected_files_summary_empty(self):
        summary = self.fm.get_detected_files_summary()
        self.assertIn("No files scanned", summary)

    def test_get_detected_files_summary_with_data(self):
        nifti = os.path.join(self.test_dir, "volume.nii")
        with open(nifti, 'w') as f:
            f.write("fake")
        result = self.fm.scan_folder(self.test_dir)
        summary = self.fm.get_detected_files_summary(result)
        self.assertIn("NIfTI", summary)

    @patch('SlicerAICopilotLib.file_manager.SLICER_AVAILABLE', False)
    def test_import_no_slicer(self):
        scan_result = {"nifti_files": ["/fake/path.nii"], "other_files": []}
        result = self.fm.import_case(scan_result)
        self.assertFalse(result["success"])
        self.assertIn("Slicer not available", result["error"])

    def test_import_no_scan_result(self):
        result = self.fm.import_case(None)
        self.assertFalse(result["success"])

    def test_last_scan_result_stored(self):
        nifti = os.path.join(self.test_dir, "vol.nii")
        with open(nifti, 'w') as f:
            f.write("fake")
        self.fm.scan_folder(self.test_dir)
        self.assertIsNotNone(self.fm.last_scan_result)


if __name__ == '__main__':
    unittest.main()
