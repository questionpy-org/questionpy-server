#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from typing import NamedTuple

from questionpy_common.environment import WorkerPermissions as EnvironmentWorkerPermissions
from questionpy_common.error import QPyBaseError
from questionpy_server.cache import LRUCacheMemory
from questionpy_server.package import Package
from questionpy_server.settings import (
    CompleteWorkerPermissions,
    MainProcessExecutionModeValues,
    PackageSelector,
    SpecificWorkerPermissions,
    WorkerPermissionsSettings,
)


class WorkerPermissionError(QPyBaseError):
    pass


def _has_enough_permissions(allowed: CompleteWorkerPermissions, requested: CompleteWorkerPermissions) -> bool:
    return (
        requested.cpus <= allowed.cpus
        and requested.memory <= allowed.memory
        and requested.request_timeout <= allowed.request_timeout
        and requested.bootstrap_timeout <= allowed.bootstrap_timeout
        and not requested.main_process_execution_modes.isdisjoint(allowed.main_process_execution_modes)
    )


def _is_wildcard_matching(selector_value: str, package_value: str) -> bool:
    return selector_value in {package_value, "*"}


def _is_selector_matching(selector: PackageSelector, package: Package, context: int | None) -> bool:
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
        and _is_wildcard_matching(selector.request_context, str(context) if context else "")
    )


class _WorkerPermissionIdentifier(NamedTuple):
    package: Package
    context: int | None


class WorkerPermissionsHandler:
    """Handles package permissions for a request."""

    def __init__(self, settings: WorkerPermissionsSettings):
        self._default_permissions = CompleteWorkerPermissions()

        self._auto_grant_permissions = settings.auto_grant_permissions
        self._specific_package_permissions = settings.packages

        self._cache: LRUCacheMemory[_WorkerPermissionIdentifier, EnvironmentWorkerPermissions] = LRUCacheMemory(
            max_size=128
        )

    def _get_requested_permissions(self, package: Package) -> CompleteWorkerPermissions:
        requested_permissions = package.manifest.permissions
        if requested_permissions is None:
            # If the package requests no permissions, we use the default ones.
            actual_permissions = self._default_permissions
        else:
            if modes := requested_permissions.main_process_execution_modes:
                requested_permissions.main_process_execution_modes = (
                    modes.intersection(MainProcessExecutionModeValues)
                    or self._default_permissions.main_process_execution_modes
                )
            requested_permissions_dict = requested_permissions.model_dump(exclude_none=True)
            actual_permissions = CompleteWorkerPermissions(**requested_permissions_dict)
        return actual_permissions

    def _get_actual_auto_grant_permissions(self, permissions: SpecificWorkerPermissions) -> CompleteWorkerPermissions:
        if permissions.auto_grant_permissions is None:
            return self._auto_grant_permissions

        specific_auto_grant_permissions = permissions.auto_grant_permissions.model_dump(exclude_none=True)
        return self._auto_grant_permissions.model_copy(update=specific_auto_grant_permissions)

    def _get_specific_permissions(self, package: Package, context: int | None) -> SpecificWorkerPermissions | None:
        # We want to select the last defined one if multiple selectors match.
        for permissions in reversed(self._specific_package_permissions):
            if _is_selector_matching(permissions.package_selector, package, context):
                return permissions
        return None

    def get_effective_permissions(self, package: Package, context: int | None) -> EnvironmentWorkerPermissions:
        """Gets the effective permissions for a package.

        TODO: also account for the current user

        Raises:
            WorkerPermissionError: If the package does not have enough permissions.
        """
        key = _WorkerPermissionIdentifier(package, context)
        if cached_permissions := self._cache.get(key):
            return cached_permissions

        auto_grant_permissions = self._auto_grant_permissions
        requested_permissions = self._get_requested_permissions(package)

        if specific_permissions := self._get_specific_permissions(package, context):
            auto_grant_permissions = self._get_actual_auto_grant_permissions(specific_permissions)

            if specific_permissions.override_permissions:
                overrides = specific_permissions.override_permissions.model_dump(exclude_none=True)

                auto_grant_permissions = auto_grant_permissions.model_copy(update=overrides)
                requested_permissions = requested_permissions.model_copy(update=overrides)

        if not _has_enough_permissions(auto_grant_permissions, requested_permissions):
            msg = f"The package '{package.hash}' requested more permissions than allowed."
            raise WorkerPermissionError(msg)

        effective_permissions = EnvironmentWorkerPermissions(**requested_permissions.model_dump())
        self._cache.put(key, effective_permissions)
        return effective_permissions
