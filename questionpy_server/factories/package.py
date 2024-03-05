#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>


from faker import Faker
from polyfactory.factories.pydantic_factory import ModelFactory

from questionpy_server.api.models import PackageInfo

languages = ["en", "de"]
fake = Faker()


class PackageInfoFactory(ModelFactory):
    __model__ = PackageInfo

    @staticmethod
    def author() -> str:
        return fake.name()

    @staticmethod
    def languages() -> list[str]:
        return languages

    @staticmethod
    def name() -> dict[str, str]:
        return {language: fake.text(20) for language in languages}

    @staticmethod
    def description() -> dict[str, str]:
        return {language: f"{language}: {fake.text()}" for language in languages}

    @staticmethod
    def icon() -> str:
        return f"https://placehold.jp/{fake.hex_color()[1:]}/{fake.hex_color()[1:]}/150x150.png"
