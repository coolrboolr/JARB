import os
import tempfile
import unittest

from flow_library import FlowLibrary


class FlowLibraryTests(unittest.TestCase):
    def test_save_and_list_and_delete_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = FlowLibrary(tmp)

            flow = {"name": "demo", "steps": [{"id": "only", "tool": "noop", "params": {}}]}
            library.save_flow(flow)

            self.assertEqual(library.list_flows(), ["demo"])
            loaded = library.get_flow("demo")
            self.assertEqual(loaded["name"], "demo")

            library.delete_flow("demo")
            self.assertIsNone(library.get_flow("demo"))
            self.assertEqual(library.list_flows(), [])

    def test_missing_flow_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = FlowLibrary(tmp)
            self.assertIsNone(library.get_flow("missing"))

    def test_requires_name_on_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = FlowLibrary(tmp)
            with self.assertRaises(ValueError):
                library.save_flow({"steps": []})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
