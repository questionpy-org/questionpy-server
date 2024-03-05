#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>


from aiohttp import ClientError, ClientSession

from questionpy_server.misc import calculate_hash


class DownloadError(Exception):
    pass


async def download(url: str, size: int = -1, expected_hash: str | None = None) -> bytes:
    """Downloads data from the given `url` and validates it.

    Downloads data if `expected_hash` is not `None`. The download size can be limited by setting `size`.

    Args:
        url (str): url of the data
        size (int): maximum amount of bytes to be
        expected_hash (Optional[str]): data must have this hash. Defaults to None.

    Returns:
        bytes: data
    """
    async with ClientSession(auto_decompress=False, raise_for_status=True) as session:
        try:
            async with session.get(url) as response:
                data = await response.content.read(size)
        except ClientError as error:
            raise DownloadError(error) from error

    if expected_hash is not None and expected_hash != calculate_hash(data):
        msg = "hash does not match expected hash"
        raise DownloadError(msg)

    return data
