#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import logging

from questionpy_common.environment import PackagePermissions as EnvironmentPackagePermissions
from questionpy_common.error import QPyBaseError
from questionpy_server.cache import LRUCacheMemory
from questionpy_server.package import Package
from questionpy_server.settings import (
    CompletePackagePermissions,
    MainProcessExecutionModeValues,
    PackagePermissionsSettings,
    SpecificPackagePermissions,
)
from questionpy_server.worker.selector import SelectorQuery, get_matching

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


class PackagePermissionsHandler:
    """Handles package permissions for a request."""

    def __init__(self, settings: PackagePermissionsSettings):
        self._cache: LRUCacheMemory[SelectorQuery, EnvironmentPackagePermissions] = LRUCacheMemory(max_size=128)
        self._package_permissions = settings.packages
        self._default_permissions = CompletePackagePermissions()
        self._auto_grant_permissions = settings.auto_grant_permissions

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

    def get(self, query: SelectorQuery) -> EnvironmentPackagePermissions:
        if cached_permissions := self._cache.get(query):
            return cached_permissions

        auto_grant_permissions = self._auto_grant_permissions
        requested_permissions = self._get_requested_permissions(query.package)

        if specific_permissions := get_matching(self._package_permissions, query):
            auto_grant_permissions = self._get_actual_auto_grant_permissions(specific_permissions)

            if specific_permissions.override_permissions:
                overrides = specific_permissions.override_permissions.model_dump(exclude_none=True)

                auto_grant_permissions = auto_grant_permissions.model_copy(update=overrides)
                requested_permissions = requested_permissions.model_copy(update=overrides)

        if not _has_enough_permissions(auto_grant_permissions, requested_permissions):
            msg = f"The package '{query.package.hash}' requested permissions that are not granted by the server."
            raise PackagePermissionError(msg)

        # Only keep explicitly allowed lms attributes.
        requested_permissions.lms_attributes.intersection_update(auto_grant_permissions.lms_attributes)

        environment_package_permissions = EnvironmentPackagePermissions(**requested_permissions.model_dump())
        self._cache.put(query, environment_package_permissions)

        return environment_package_permissions
