from pydantic_factories import ModelFactory

from questionpy_server.api.models import QuestionStateHash


class QuestionStateHashFactory(ModelFactory):
    __model__ = QuestionStateHash
