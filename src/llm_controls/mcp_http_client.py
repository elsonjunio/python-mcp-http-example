import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession
import logging
from typing import Any
from mcp.types import Tool, Resource, ResourceTemplate, Prompt
from mcp.client.sse import sse_client
from typing import TypeVar, Type

T = TypeVar('T')

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)


class MCPClient:
    """Client for interacting with MCP (Model Context Protocol) server.

    This class provides an asynchronous interface to communicate with an MCP server,
    managing connections, executing tools, and listing available resources.

    Attributes:
        name (str): Identifier for the server connection
        server_url (str): URL of the MCP server
        session (Optional[ClientSession]): Active client session
        _cleanup_lock (asyncio.Lock): Lock for thread-safe cleanup
        exit_stack (AsyncExitStack): Resource management context stack
    """

    def __init__(self, name: str, server_url: str):
        """Initialize the MCP client.

        Args:
            name: A unique name identifier for this server connection
            server_url: Complete URL of the MCP server (e.g., 'https://server:port')
        """
        self.name = name
        self.server_url = server_url
        self.session: ClientSession | None = None
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        self.exit_stack: AsyncExitStack = AsyncExitStack()

    async def initialization(self) -> None:
        """Initialize the connection to the MCP server.

        Establishes SSE connection and initializes a client session.

        Raises:
            ConnectionError: If the connection to the server fails
            Exception: For any other initialization errors
        """
        try:
            streams = await self.exit_stack.enter_async_context(
                sse_client(self.server_url)
            )

            session = await self.exit_stack.enter_async_context(
                ClientSession(streams[0], streams[1])
            )

            await session.initialize()
            self.session = session
        except Exception as e:
            logging.error(f'Error initializing server {self.name}: {e}')
            await self.cleanup()
            raise

    async def _list_entities(
        self, session_method: str, entity_type: Type[T], response_key: str
    ) -> list[T]:
        """Internal generic method for listing server entities.

        Args:
            session_method: Name of the session method to call
            entity_type: Type class for the entities being listed
            response_key: Expected key in the server response

        Returns:
            List of entities of the specified type

        Raises:
            RuntimeError: If the client is not initialized
        """
        if not self.session:
            raise RuntimeError(f'Server {self.name} not initialized')

        response = await getattr(self.session, session_method)()
        entities = []

        for item in response:
            if isinstance(item, tuple) and item[0] == response_key:
                for entity in item[1]:
                    entities.append(entity_type(**entity.dict()))

        return entities

    async def list_tools(self) -> list[Tool]:
        """List all available tools on the server.

        Returns:
            List of Tool objects containing tool definitions

        Example:
            >>> tools = await client.list_tools()
            >>> print([t.name for t in tools])
        """
        return await self._list_entities('list_tools', Tool, 'tools')

    async def list_resources(self) -> list[Resource]:
        """List all available resources on the server.

        Returns:
            List of Resource objects with resource metadata
        """
        return await self._list_entities(
            'list_resources', Resource, 'resources'
        )

    async def list_resource_templates(self) -> list[ResourceTemplate]:
        """List all resource templates available on the server.

        Returns:
            List of ResourceTemplate objects
        """
        return await self._list_entities(
            'list_resource_templates', ResourceTemplate, 'resourceTemplates'
        )

    async def list_prompts(self) -> list[Prompt]:
        """List all predefined prompts on the server.

        Returns:
            List of Prompt objects with prompt definitions
        """
        return await self._list_entities('list_prompts', Prompt, 'prompts')

    async def cleanup(self) -> None:
        """Clean up all client resources safely.

        Closes the exit stack and resets the session. This method is thread-safe
        and can be called multiple times.
        """
        async with self._cleanup_lock:
            try:
                await self.exit_stack.aclose()
                self.session = None
                self.stdio_context = None
            except Exception as e:
                logging.error(
                    f'Error during cleanup of server {self.name}: {e}'
                )

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        retries: int = 2,
        delay: float = 1.0,
    ) -> Any:
        """Execute a tool on the server with automatic retry logic.

        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments for the tool
            retries: Maximum number of retry attempts (default: 2)
            delay: Delay between retries in seconds (default: 1.0)

        Returns:
            The execution result from the server

        Raises:
            RuntimeError: If the client is not initialized
            Exception: If all retry attempts fail

        Example:
            >>> result = await client.execute_tool(
            ...     "text_analyzer",
            ...     {"text": "sample", "mode": "full"}
            ... )
        """
        if not self.session:
            raise RuntimeError(f'Server {self.name} not initialized')

        attempt = 0
        while attempt < retries:
            try:
                logging.info(f'Executing {tool_name}...')
                result = await self.session.call_tool(tool_name, arguments)

                return result

            except Exception as e:
                attempt += 1
                logging.warning(
                    f'Error executing tool: {e}. Attempt {attempt} of {retries}.'
                )
                if attempt < retries:
                    logging.info(f'Retrying in {delay} seconds...')
                    await asyncio.sleep(delay)
                else:
                    logging.error('Max retries reached. Failing.')
                    raise
