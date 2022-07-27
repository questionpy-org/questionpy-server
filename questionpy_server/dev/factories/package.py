import random
from random import randint
import uuid
from typing import Optional

from questionpy_server.api.models import PackageInfo


class PackageFactory:
    """Create random PackageInfo and return it as dict or BaseModel."""

    @staticmethod
    def get(package_hash: Optional[str] = None, raw: bool = False):
        random.seed(package_hash)
        number = randint(0, 100)

        package_info = {
            'package_hash': package_hash or uuid.uuid4().hex,
            'short_name': f'ext{number}',
            'name': {
                'en': f'ExampleType {number}',
                'de': f'BeispielTyp {number}'
            },
            'version': f'0.0.{number}',
            'type': 'questiontype',
            'author': f'Author {number}',
            'url': f'https://questionpy.org/{number}',
            'languages': [
                'en',
                'de'
            ],
            'description': {
                'en': f'This describes the package ExampleType {number}. ' * number,
                'de': f'Hier wird das Paket BeispielTyp {number} beschrieben. ' * number
            },
            'icon': 'https://placeimg.com/48/48/tech/grayscale',
            'license': 'MIT'
        }

        if raw:
            return package_info
        return PackageInfo(**package_info)
