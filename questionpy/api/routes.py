from aiohttp import web


routes = web.RouteTableDef()


@routes.get('/helloworld')
async def hello(request: web.Request):
    return web.Response(text="Hello, world")
