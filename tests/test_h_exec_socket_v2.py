from pathlib import Path
import os
import unittest

from telemetry_availability.h_exec_live_v2 import admin_socket_address


class LongWorkspaceAdminSocketTests(unittest.TestCase):
    def test_long_absolute_workspace_is_removed_without_changing_cwd(self):
        before=Path.cwd()
        absolute=before/'workflow-results/h-exec'
        address=admin_socket_address(absolute)
        self.assertFalse(Path(address).is_absolute())
        self.assertEqual(Path(address),Path('workflow-results/h-exec/admin/admin.sock'))
        self.assertLess(len(os.fsencode(address)),108)
        self.assertEqual(before,Path.cwd())

    def test_outside_workspace_and_still_long_relative_path_are_rejected(self):
        with self.assertRaises(ValueError):
            admin_socket_address(Path.cwd().parent/'outside-workflow')
        with self.assertRaises(ValueError):
            admin_socket_address(Path.cwd()/('x'*110))
