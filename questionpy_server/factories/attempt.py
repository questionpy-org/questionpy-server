from pydantic_factories import ModelFactory

from questionpy_server.api.models import Attempt, AttemptGraded, AttemptStarted


class AttemptStartedFactory(ModelFactory):
    __model__ = AttemptStarted


class AttemptFactory(ModelFactory):
    __model__ = Attempt


class AttemptGradedFactory(ModelFactory):
    __model__ = AttemptGraded
