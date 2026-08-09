"""The single most important architectural invariant of this project:
bi_terminal.core and bi_terminal.specs must never import a rendering toolkit
or any bi_terminal.renderers module. This is what lets a stdio door renderer
install with nothing beyond `requests`.

bi_terminal.driver (the shared AppDriver, extracted from
renderers/textual/app.py once it became clear the flow-orchestration logic
was 100% renderer-agnostic) gets a related but slightly looser check: it may
import renderers.base (a zero-toolkit-dependency Protocol module, needed for
a type hint) but must never import a rendering toolkit directly, nor any
CONCRETE renderer package (renderers.textual/ansi/petscii/atascii) — doing
so would silently reintroduce the exact duplication problem the extraction
was meant to eliminate.

AST-based (not just "try importing with textual uninstalled") so it catches
the mistake at authoring time regardless of what's installed in the current
environment, and reports every offending import in one run instead of
stopping at the first ImportError.
"""

import ast
import pathlib

import bi_terminal.core as core_pkg
import bi_terminal.driver as driver_module
import bi_terminal.specs as specs_pkg

FORBIDDEN_TOP_LEVEL = {"textual", "curses", "rich", "rich_pixels", "ascii_magic", "PIL"}


def _imported_module_roots(py_file: pathlib.Path):
    tree = ast.parse(py_file.read_text(), filename=str(py_file))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                yield node.module.split(".")[0]
            elif node.module and node.level > 0:
                # relative import, e.g. `from .renderers import X` or
                # `from ..renderers.textual import Y` — check the dotted
                # module path itself for a "renderers" segment.
                yield f"__relative__:{node.module}"


def _check_package_dir(pkg_dir: pathlib.Path, package_label: str):
    violations = []
    for py_file in pkg_dir.rglob("*.py"):
        for root in _imported_module_roots(py_file):
            if root in FORBIDDEN_TOP_LEVEL:
                violations.append(f"{py_file}: imports forbidden module '{root}'")
            elif root.startswith("__relative__:") and "renderers" in root.split(":", 1)[1]:
                violations.append(
                    f"{py_file}: relative-imports a renderers module ({root.split(':', 1)[1]})"
                )
    assert not violations, (
        f"bi_terminal.{package_label} must never import a rendering toolkit or "
        f"bi_terminal.renderers — found:\n" + "\n".join(violations)
    )


def test_core_has_no_rendering_or_renderer_imports():
    _check_package_dir(pathlib.Path(core_pkg.__file__).parent, "core")


def test_specs_has_no_rendering_or_renderer_imports():
    _check_package_dir(pathlib.Path(specs_pkg.__file__).parent, "specs")


def test_specs_does_not_import_renderers_package_by_absolute_name():
    # Belt-and-suspenders: also scan for `import bi_terminal.renderers...`
    # absolute-form imports, which the relative-import check above wouldn't
    # catch.
    for pkg_dir, label in (
        (pathlib.Path(core_pkg.__file__).parent, "core"),
        (pathlib.Path(specs_pkg.__file__).parent, "specs"),
    ):
        for py_file in pkg_dir.rglob("*.py"):
            tree = ast.parse(py_file.read_text(), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("bi_terminal.renderers"), (
                            f"{py_file} ({label}) absolute-imports bi_terminal.renderers"
                        )
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("bi_terminal.renderers"):
                        raise AssertionError(
                            f"{py_file} ({label}) imports from bi_terminal.renderers"
                        )


def test_driver_has_no_rendering_toolkit_imports():
    driver_file = pathlib.Path(driver_module.__file__)
    violations = [
        f"{driver_file}: imports forbidden module '{root}'"
        for root in _imported_module_roots(driver_file)
        if root in FORBIDDEN_TOP_LEVEL
    ]
    assert not violations, "bi_terminal.driver must never import a rendering toolkit:\n" + "\n".join(
        violations
    )


def test_driver_only_imports_renderers_base_not_a_concrete_renderer():
    # driver.py MAY import renderers.base (a zero-toolkit Protocol module,
    # used only as a type hint) but must never import a concrete renderer
    # package — that would silently reintroduce per-renderer duplication,
    # the exact problem the driver extraction eliminated.
    driver_file = pathlib.Path(driver_module.__file__)
    tree = ast.parse(driver_file.read_text(), filename=str(driver_file))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            module = node.module
            if module == "renderers.base":
                continue  # the one allowed exception
            assert "renderers" not in module, (
                f"{driver_file} imports a concrete renderer submodule: {module}"
            )
