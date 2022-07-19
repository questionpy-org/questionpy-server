from aiohttp import web


routes = web.RouteTableDef()


@routes.get('/helloworld')
async def hello(_request: web.Request) -> web.Response:
    return web.Response(text="Hello, world")
