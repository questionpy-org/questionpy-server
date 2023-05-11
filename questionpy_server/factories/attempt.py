from pydantic_factories import ModelFactory

from questionpy_server.api.models import Attempt, AttemptScored, AttemptStarted


class AttemptStartedFactory(ModelFactory):
    __model__ = AttemptStarted


class AttemptFactory(ModelFactory):
    __model__ = Attempt


class AttemptScoredFactory(ModelFactory):
    __model__ = AttemptScored
