#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import logging
from typing import NamedTuple

from questionpy_common.environment import PackagePermissions as EnvironmentPackagePermissions
from questionpy_common.error import QPyBaseError
from questionpy_server.cache import LRUCacheMemory
from questionpy_server.package import Package
from questionpy_server.settings import (
    CompletePackagePermissions,
    MainProcessExecutionModeValues,
    PackagePermissionsSettings,
    PackageSelector,
    SpecificPackagePermissions,
)

_log = logging.getLogger(__name__)


class PackagePermissionError(QPyBaseError):
    pass


def _has_enough_permissions(allowed: CompletePackagePermissions, requested: CompletePackagePermissions) -> bool:
    return (
        requested.cpus <= allowed.cpus
        and requested.memory <= allowed.memory
        and requested.request_timeout <= allowed.request_timeout
        and requested.bootstrap_timeout <= allowed.bootstrap_timeout
        and not requested.main_process_execution_modes.isdisjoint(allowed.main_process_execution_modes)
    )


def _is_wildcard_matching(selector_value: str, package_value: str) -> bool:
    return selector_value in {package_value, "*"}


def _is_selector_matching(selector: PackageSelector, package: Package, user: str | None, context: str) -> bool:
    return (
        # Package data.
        _is_wildcard_matching(selector.hash, package.hash)
        and _is_wildcard_matching(selector.namespace, package.manifest.namespace)
        and _is_wildcard_matching(selector.short_name, package.manifest.short_name)
        and (selector.version == "*" or package.manifest.version.match(selector.version))
        # Package origin.
        and _is_wildcard_matching(selector.origin.repositories, "*")  # TODO: handle repositories
        and (selector.origin.local is None or selector.origin.local == package.sources.is_local())
        and _is_wildcard_matching(selector.origin.users, "*")  # TODO: handle users
        # Request data.
        and _is_wildcard_matching(selector.request_user, str(user) if user else "")
        and _is_wildcard_matching(selector.request_context, context)
    )


class _PackagePermissionIdentifier(NamedTuple):
    package: Package
    user: str | None
    context: str


class PackagePermissionsHandler:
    """Handles package permissions for a request."""

    def __init__(self, settings: PackagePermissionsSettings):
        self._default_permissions = CompletePackagePermissions()

        self._auto_grant_permissions = settings.auto_grant_permissions
        self._specific_package_permissions = settings.packages

        self._cache: LRUCacheMemory[_PackagePermissionIdentifier, EnvironmentPackagePermissions] = LRUCacheMemory(
            max_size=128
        )

    def _get_requested_permissions(self, package: Package) -> CompletePackagePermissions:
        requested_permissions = package.manifest.permissions
        if requested_permissions is None:
            # If the package requests no permissions, we use the default ones.
            actual_permissions = self._default_permissions.model_copy()
        else:
            if requested_modes := requested_permissions.main_process_execution_modes:
                if intersection := requested_modes.intersection(MainProcessExecutionModeValues):
                    requested_permissions.main_process_execution_modes = intersection
                else:
                    # The package requests unknown execution modes.
                    default_modes = self._default_permissions.main_process_execution_modes
                    requested_permissions.main_process_execution_modes = default_modes
                    _log.info(
                        f"The package '{package.hash}' requested unknown execution modes: {requested_modes}. "
                        f"Falling back to: {default_modes}."
                    )

            requested_permissions_dict = requested_permissions.model_dump(exclude_none=True)
            actual_permissions = CompletePackagePermissions(**requested_permissions_dict)
        return actual_permissions

    def _get_actual_auto_grant_permissions(self, permissions: SpecificPackagePermissions) -> CompletePackagePermissions:
        if permissions.auto_grant_permissions is None:
            return self._auto_grant_permissions

        specific_auto_grant_permissions = permissions.auto_grant_permissions.model_dump(exclude_none=True)
        return self._auto_grant_permissions.model_copy(update=specific_auto_grant_permissions)

    def _get_specific_permissions(
        self, package: Package, user: str | None, context: str
    ) -> SpecificPackagePermissions | None:
        # We want to select the last defined one if multiple selectors match.
        for permissions in reversed(self._specific_package_permissions):
            if _is_selector_matching(permissions.package_selector, package, user, context):
                return permissions
        return None

    def get_effective_permissions(
        self, package: Package, user: str | None, context: str
    ) -> EnvironmentPackagePermissions:
        """Gets the effective permissions for a package.

        Raises:
            PackagePermissionError: If the package does not have enough permissions.
        """
        key = _PackagePermissionIdentifier(package, user, context)
        if cached_permissions := self._cache.get(key):
            return cached_permissions

        auto_grant_permissions = self._auto_grant_permissions
        requested_permissions = self._get_requested_permissions(package)

        if specific_permissions := self._get_specific_permissions(package, user, context):
            auto_grant_permissions = self._get_actual_auto_grant_permissions(specific_permissions)

            if specific_permissions.override_permissions:
                overrides = specific_permissions.override_permissions.model_dump(exclude_none=True)

                auto_grant_permissions = auto_grant_permissions.model_copy(update=overrides)
                requested_permissions = requested_permissions.model_copy(update=overrides)

        if not _has_enough_permissions(auto_grant_permissions, requested_permissions):
            msg = f"The package '{package.hash}' requested more permissions than allowed."
            raise PackagePermissionError(msg)

        # Only keep explicitly allowed lms attributes.
        requested_permissions.lms_attributes.intersection_update(auto_grant_permissions.lms_attributes)

        effective_permissions = EnvironmentPackagePermissions(**requested_permissions.model_dump())
        self._cache.put(key, effective_permissions)
        return effective_permissions
