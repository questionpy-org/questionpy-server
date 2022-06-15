from pytest_aiohttp.plugin import TestClient


async def test_hello(client: TestClient) -> None:
    res = await client.request("GET", "/helloworld")

    assert res.status == 200
    assert await res.text() == "Hello, world"
