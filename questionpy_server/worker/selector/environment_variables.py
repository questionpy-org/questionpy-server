#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from questionpy_common.error import QPyBaseError
from questionpy_server.cache import LRUCacheMemory
from questionpy_server.settings import EnvironmentVariablesSettings
from questionpy_server.worker.selector import SelectorQuery, get_matching


class PackageEnvironmentVariablesError(QPyBaseError):
    pass


class EnvironmentVariablesHandler:
    """Handles environment variables for a request."""

    def __init__(self, settings: EnvironmentVariablesSettings):
        self._cache: LRUCacheMemory[SelectorQuery, dict[str, str]] = LRUCacheMemory(max_size=128)
        self._environment_variables = settings.packages
        self._global_environment_variables = settings.global_.root

    def get(self, query: SelectorQuery) -> dict[str, str]:
        if cached_environment_variables := self._cache.get(query):
            return cached_environment_variables

        environment_variables = self._global_environment_variables.copy()

        if (specific := get_matching(self._environment_variables, query)) and specific.environment_variables:
            environment_variables.update(specific.environment_variables.root)

        requested_environment_variables = query.package.manifest.environment_variables
        if requested_environment_variables and not requested_environment_variables.issubset(
            environment_variables.keys()
        ):
            msg = (
                f"The package '{query.package.hash}' requested environment variables that are not provided by the "
                "server."
            )
            raise PackageEnvironmentVariablesError(msg)

        self._cache.put(query, environment_variables)
        return environment_variables
