#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from polyfactory.factories.pydantic_factory import ModelFactory

from questionpy_server.models import RequestBaseData


class RequestBaseDataFactory(ModelFactory):
    __model__ = RequestBaseData
