import os
import unittest
import uuid

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from single_instance import SingleInstanceGuard


class SingleInstanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_second_instance_notifies_primary_and_exits(self):
        server_name = f"synapcap-test-{uuid.uuid4()}"
        primary = SingleInstanceGuard(server_name)
        secondary = SingleInstanceGuard(server_name)
        activations = []
        primary.activation_requested.connect(lambda: activations.append(True))
        try:
            self.assertTrue(primary.acquire())
            self.assertFalse(secondary.acquire())
            self.app.processEvents()
            self.assertEqual(activations, [True])
        finally:
            secondary.close()
            primary.close()
