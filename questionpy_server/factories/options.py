from pydantic_factories import ModelFactory

from questionpy_server.api.models import Form


class FormFactory(ModelFactory):
    __model__ = Form
