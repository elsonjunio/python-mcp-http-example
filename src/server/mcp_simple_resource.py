from starlette.applications import Starlette
from starlette.routing import Mount, Host
from mcp.server.fastmcp import FastMCP
import uvicorn

# Create an MCP server
mcp = FastMCP('Demo')


# Add an addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


# Add a dynamic greeting resource
@mcp.resource('greeting://{name}')
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f'Hello, {name}!'


# Static configuration data
@mcp.resource('config://app')
def get_config() -> str:
    """Static configuration data"""
    return 'App configuration here'


# Dynamic user data
@mcp.resource('users://{user_id}/profile')
def get_user_profile(user_id: str) -> str:
    """Dynamic user data"""
    return f'Profile data for user {user_id}'


if __name__ == '__main__':

    # Create the SSE server
    app = Starlette(
        routes=[
            Mount('/', app=mcp.sse_app()),
        ]
    )

    uvicorn.run(app, host='0.0.0.0', port=8000)
