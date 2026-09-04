"""Guards against drift between the places django-helpdesk settings live.

The settings surface is spread across ``src/helpdesk``, two example
configurations and the documentation, and until now nothing tied those together.
``HELPDESK_PUBLIC_ENABLED`` sat in both configuration files and in the standalone
documentation, described as the switch that enables the public portal, while no
code in the package ever read it. See #1416.

These checks are static analysis over files that are already in the repository.
They cost nothing at runtime and fail as soon as a name is orphaned again. They
are tripwires rather than proofs: a name mentioned only in a comment counts as
used, which is the right trade for a check meant to catch whole settings falling
out of use.

They need the repository layout, so they skip when django-helpdesk is being
tested from an installed distribution rather than from a checkout.
"""

import ast
import re
import unittest
from pathlib import Path

from django.test import SimpleTestCase

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = REPO_ROOT / "src" / "helpdesk"
EXAMPLE_CONFIGS = (
    REPO_ROOT / "standalone" / "config" / "settings.py",
    REPO_ROOT / "demodesk" / "config" / "settings.py",
)
STANDALONE_CONFIG = EXAMPLE_CONFIGS[0]
STANDALONE_DOCS = REPO_ROOT / "docs" / "standalone.rst"

HELPDESK_SETTING = re.compile(r"^(HELPDESK|QUEUE)_")

requires_checkout = unittest.skipUnless(
    PACKAGE.is_dir() and all(p.is_file() for p in EXAMPLE_CONFIGS),
    "needs the repository layout, not an installed distribution",
)


def _assigned_settings(path):
    """HELPDESK_/QUEUE_ names a configuration file assigns at module level."""
    tree = ast.parse(path.read_text())
    return {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and HELPDESK_SETTING.match(target.id)
    }


def _default_user_settings_keys(path):
    """Keys of the HELPDESK_DEFAULT_SETTINGS dict a configuration file defines."""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "HELPDESK_DEFAULT_SETTINGS"
            for t in node.targets
        ):
            return {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
    return set()


def _environment_variables_read(path):
    """Names a configuration file looks up in os.environ."""
    tree = ast.parse(path.read_text())
    names = set()
    for node in ast.walk(tree):
        # os.environ.get("NAME", default)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "environ"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            names.add(node.args[0].value)
        # os.environ["NAME"]
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "environ"
            and isinstance(node.slice, ast.Constant)
        ):
            names.add(node.slice.value)
    return names


def _package_sources():
    for pattern in ("*.py", "*.html"):
        yield from PACKAGE.rglob(pattern)


class SettingsDriftTests(SimpleTestCase):
    """The settings layers agree on which names exist."""

    @requires_checkout
    def test_example_configurations_only_set_settings_that_are_read(self):
        """A name set by an example config is a name the package looks at.

        This is the check that HELPDESK_PUBLIC_ENABLED failed.
        """
        package_text = "\n".join(
            p.read_text(errors="replace") for p in _package_sources()
        )

        orphans = {}
        for config in EXAMPLE_CONFIGS:
            for name in _assigned_settings(config):
                if not re.search(rf"\b{re.escape(name)}\b", package_text):
                    orphans.setdefault(name, []).append(
                        config.relative_to(REPO_ROOT).as_posix()
                    )

        self.assertEqual(
            orphans,
            {},
            "these settings are assigned by an example configuration but no code "
            "in src/helpdesk reads them, so setting them does nothing",
        )

    @requires_checkout
    def test_documented_standalone_variables_are_read_by_the_image(self):
        """Every variable the standalone docs promise is read by its settings file.

        This is the check that HELPDESK_KANBAN_ENABLED failed: the tables listed
        it under Feature Toggles while the configuration never looked at the
        environment for it.
        """
        documented = set(
            re.findall(r"^   ``(\w+)``,", STANDALONE_DOCS.read_text(), re.MULTILINE)
        )
        self.assertTrue(documented, "no variables found in the standalone tables")

        # Read from the environment, specifically: a name hardcoded in the
        # configuration would satisfy a plain text search while still ignoring
        # whatever the operator puts in docker.env.
        from_environment = _environment_variables_read(STANDALONE_CONFIG)
        unread = sorted(documented - from_environment)

        self.assertEqual(
            unread,
            [],
            "docs/standalone.rst documents these environment variables but "
            "standalone/config/settings.py never reads them",
        )

    @requires_checkout
    def test_default_user_settings_keys_are_user_settings_fields(self):
        """HELPDESK_DEFAULT_SETTINGS only carries keys UserSettings has.

        DEFAULT_USER_SETTINGS.update() merges whatever it is given, so an
        unknown key is absorbed in silence and never surfaces anywhere.
        """
        from helpdesk.models import UserSettings

        fields = {f.name for f in UserSettings._meta.get_fields()}

        unknown = {}
        for config in EXAMPLE_CONFIGS:
            for key in _default_user_settings_keys(config) - fields:
                unknown.setdefault(key, []).append(
                    config.relative_to(REPO_ROOT).as_posix()
                )

        self.assertEqual(
            unknown,
            {},
            "these HELPDESK_DEFAULT_SETTINGS keys are not fields on the "
            "UserSettings model, so nothing ever reads them",
        )
