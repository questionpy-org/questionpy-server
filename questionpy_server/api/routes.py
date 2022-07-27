from aiohttp import web

from questionpy_server.dev.factories import PackageFactory


routes = web.RouteTableDef()


@routes.get('/helloworld')
async def hello(_request: web.Request) -> web.Response:
    return web.Response(text="Hello, world")


@routes.get('/packages')
async def get_packages(_request: web.Request) -> web.Response:
    package_list = [PackageFactory.get(raw=True) for _ in range(5)]
    response = web.json_response(package_list)
    return response


@routes.get(r'/packages/{package_hash:\w+}')
async def get_package(_request: web.Request) -> web.Response:
    response = web.json_response(PackageFactory.get(_request.match_info['package_hash'], raw=True))
    return response



