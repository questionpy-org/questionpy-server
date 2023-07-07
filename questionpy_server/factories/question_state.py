#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from pydantic_factories import ModelFactory

from questionpy_server.api.models import RequestBaseData


class RequestBaseDataFactory(ModelFactory):
    __model__ = RequestBaseData
