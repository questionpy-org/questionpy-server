from unittest.mock import patch, AsyncMock

import aiohttp
import pytest
from pytest import MonkeyPatch

from aiohttp import ClientSession, ClientResponse, ClientError

from questionpy_server.repository.helper import download, DownloadError


async def test_raises_download_error_on_client_error() -> None:
    with patch.object(ClientSession, 'get', side_effect=ClientError):
        with pytest.raises(DownloadError):
            await download('https://example.com')


async def test_raises_download_error_on_hash_missmatch(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(aiohttp, 'ClientSession', AsyncMock(spec=ClientSession))
    with patch.object(ClientResponse, 'content') as mock:
        mock.return_value = AsyncMock(return_value=b'data')
        with pytest.raises(DownloadError, match='hash does not match expected hash'):
            await download('https://example.com', expected_hash='expected hash')
