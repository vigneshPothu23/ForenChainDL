"""
Checks for the mobile-responsive layer in app.py.

Run from the project folder:
    python -m unittest tests.test_responsive_css -v

These are static checks (no browser needed):
  * the responsive CSS function exists and main() calls it first;
  * every layout rule lives inside a max-width media query, so desktop
    (wider than 768px) is not restyled;
  * the only rule outside a media query is text wrapping for long values;
  * no external scripts, fonts or URLs are added by the responsive block.
"""
import ast
import re
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app.py"


def _source():
    return APP.read_text(encoding="utf-8-sig")


def _css_block(source):
    start = source.index("/* FORENCHAIN_RESPONSIVE_V1 */")
    end = source.index("</style>", start)
    return source[start:end]


class ResponsiveCssTest(unittest.TestCase):
    def test_app_compiles(self):
        compile(_source(), str(APP), "exec")

    def test_function_defined_and_called_first_in_main(self):
        tree = ast.parse(_source())
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        self.assertIn("_fc_responsive_css", functions)
        main = functions["main"]
        first = main.body[0]
        self.assertIsInstance(first, ast.Expr)
        self.assertEqual(getattr(first.value.func, "id", None), "_fc_responsive_css")

    def test_layout_rules_only_inside_media_queries(self):
        css = _css_block(_source())
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        depth, outside = 0, []
        buffer = ""
        for char in css:
            if char == "{":
                if depth == 0:
                    outside.append(buffer.strip())
                depth += 1
                buffer = ""
            elif char == "}":
                depth -= 1
                buffer = ""
            else:
                buffer += char
        top_level = [sel for sel in outside if sel and not sel.startswith("@media")]
        self.assertTrue(all("@media (max-width:" in m for m in outside if m.startswith("@media")))
        # Only the wrapping rule and the placeholder box sizing live outside media queries.
        joined = " ".join(top_level)
        for selector in top_level:
            self.assertTrue(
                ".fcs-empty" in selector or ".fcd-step small" in selector,
                f"unexpected desktop rule: {selector}",
            )
        self.assertIn(".fcs-empty", joined)

    def test_no_external_resources(self):
        css = _css_block(_source())
        self.assertNotRegex(css, r"https?://|@import|<script")

    def test_breakpoints(self):
        css = _css_block(_source())
        self.assertIn("@media (max-width: 768px)", css)
        self.assertIn("@media (max-width: 640px)", css)
        self.assertIn("min-height: 44px", css)


if __name__ == "__main__":
    unittest.main(verbosity=2)
