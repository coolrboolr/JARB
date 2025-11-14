import tempfile
import textwrap
import unittest

from tool_library import ToolLibrary


def _add_tool(library: ToolLibrary, name: str, code: str) -> None:
    source = textwrap.dedent(code)
    namespace = {}
    exec(source, namespace)
    library.add_tool(name, namespace[name], source)


class ToolLibraryMetadataTests(unittest.TestCase):
    def test_describe_tool_includes_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = ToolLibrary(tmp)
            _add_tool(
                library,
                "double",
                """
                def double(value: int) -> int:
                    \"""Return value * 2.\"""
                    return value * 2
                """,
            )

            description = library.describe_tool("double")
            self.assertEqual(description["name"], "double")
            self.assertEqual(description["docstring"], "Return value * 2.")

            params = description["parameters"]
            self.assertEqual(len(params), 1)
            self.assertTrue(params[0]["required"])
            self.assertEqual(params[0]["annotation"]["type"], "int")
            self.assertEqual(description["return_annotation"], int)

            signature = library.get_tool_signature("double")
            self.assertIn("value", signature.parameters)

            source = library.get_tool_source("double")
            self.assertIn("return value * 2", source)

    def test_reload_after_edit_refreshes_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = ToolLibrary(tmp)
            _add_tool(
                library,
                "demo",
                """
                def demo(value: int):
                    \"""Original doc.\"""
                    return value
                """,
            )

            path = library.tools_dir / "demo.py"
            path.write_text(
                textwrap.dedent(
                    """
                    def demo(value: int):
                        \"""Updated doc.\"""
                        return value * 3
                    """
                ),
                encoding="utf-8",
            )

            library.load_tool("demo")
            description = library.describe_tool("demo")
            self.assertEqual(description["docstring"], "Updated doc.")

    def test_missing_tool_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = ToolLibrary(tmp)
            with self.assertRaises(FileNotFoundError):
                library.describe_tool("missing")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
