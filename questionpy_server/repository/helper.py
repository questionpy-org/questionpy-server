from typing import Optional

from aiohttp import ClientSession, ClientError

from questionpy_server.misc import calculate_hash


class DownloadError(Exception):
    pass


async def download(url: str, size: int = -1, expected_hash: Optional[str] = None) -> bytes:
    """
    Downloads data from the given `url` and validates it if `expected_hash` is not `None`.
    The download size can be limited by setting `size`.

    :param url: url of the data
    :param size: maximum amount of bytes to be downloaded
    :param expected_hash: data must have this hash
    :return:
    """
    async with ClientSession(auto_decompress=False, raise_for_status=True) as session:
        try:
            async with session.get(url) as response:
                data = await response.content.read(size)
        except ClientError as error:
            raise DownloadError(error) from error

    if expected_hash is not None and expected_hash != calculate_hash(data):
        raise DownloadError("hash does not match expected hash")

    return data
