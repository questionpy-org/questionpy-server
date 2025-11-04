#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from questionpy_common.error import QPyBaseError
from questionpy_server.settings import EnvironmentVariablesSettings, SpecificPackageEnvironmentVariables
from questionpy_server.worker.selector import Selector, SelectorQuery


class PackageEnvironmentVariablesError(QPyBaseError):
    pass


class EnvironmentVariablesHandler(Selector[SpecificPackageEnvironmentVariables, dict[str, str]]):
    """Handles environment variables for a request."""

    def __init__(self, settings: EnvironmentVariablesSettings):
        super().__init__(settings.packages)

        self._global_environment_variables = settings.global_.root

    def _get(self, query: SelectorQuery) -> dict[str, str]:
        environment_variables = self._global_environment_variables.copy()

        if (specific := self._get_matching(query)) and specific.environment_variables:
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

        return environment_variables
