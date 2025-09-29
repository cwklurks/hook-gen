"""Minimal pkg_resources shim for environments without setuptools.

Only implements the tiny subset pretty_midi requires (resource_filename).
"""
from __future__ import annotations

import importlib
from importlib import resources
from pathlib import Path
from types import ModuleType
from typing import Union


class ResolutionError(Exception):
    """Placeholder matching setuptools' ResolutionError."""


class DistributionNotFound(ResolutionError):
    """Placeholder matching setuptools' DistributionNotFound."""


PackageLike = Union[str, ModuleType]


def _resolve_package(package_or_requirement: PackageLike) -> ModuleType:
    if isinstance(package_or_requirement, ModuleType):
        return package_or_requirement
    if isinstance(package_or_requirement, str):
        # Incoming strings are usually module names (e.g. 'pretty_midi').
        try:
            return importlib.import_module(package_or_requirement)
        except ModuleNotFoundError as exc:  # pragma: no cover - defensive guard
            raise DistributionNotFound(str(exc)) from exc
    raise TypeError("Invalid package identifier: %r" % (package_or_requirement,))


def resource_filename(package_or_requirement: PackageLike, resource_name: str) -> str:
    """Return an on-disk path for a packaged resource.

    Mirrors the setuptools API for the small usage footprint inside pretty_midi.
    Falls back to joining the package folder with the desired file if the
    importlib.resources machinery cannot provide a concrete path (e.g. in
    zipimport environments).
    """

    package = _resolve_package(package_or_requirement)
    try:
        return str(resources.files(package) / resource_name)
    except (FileNotFoundError, AttributeError):
        package_path = Path(getattr(package, "__file__", "")).parent
        return str(package_path / resource_name)
