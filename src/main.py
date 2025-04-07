from llm_controls.llm_client import LLMClient
from llm_controls.mcp_http_client import MCPClient
from llm_controls.chat_session import ChatSession
import asyncio

import logging

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)


async def main() -> None:
    """Initialize and run the chat session."""

    mcp_clients = [MCPClient('Demo', 'http://localhost:8000/sse')]
    llm_client = LLMClient()
    chat_session = ChatSession(mcp_clients, llm_client)
    await chat_session.chat_loop()


if __name__ == '__main__':
    asyncio.run(main())
