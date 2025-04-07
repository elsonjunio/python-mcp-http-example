from typing import List, Dict, Any, Optional, Union
from mcp import Tool
from llm_controls.mcp_http_client import MCPClient
from llm_controls.llm_client import LLMClient
import logging
from dataclasses import dataclass
import re
import json


# Configure logging
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)


@dataclass
class ToolResponse:
    """Estrutura para respostas de ferramentas."""

    content: Any
    is_progress: bool = False
    progress: Optional[float] = None
    total: Optional[float] = None


class ChatSession:
    """Orchestrates the interaction between user, LLM, and tools."""

    def __init__(
        self,
        mcp_clients: list[MCPClient],
        llm_client: LLMClient,
        system_prompt_template: Optional[str] = None,
    ) -> None:
        self.mcp_clients: list[MCPClient] = mcp_clients
        self.llm_client: LLMClient = llm_client
        self.system_prompt_template = (
            system_prompt_template or self._default_system_prompt()
        )

    def _default_system_prompt(self) -> str:
        """Generate the default system prompt."""
        return """
Você é um assistente atencioso com acesso a algumas ferramentas (tools):

{tools_description}

Com base no diálogo com o usuário, use uma tool **somente se for solicitado explicitamente**.
Quando isso ocorrer, responda **apenas** com um objeto JSON seguindo exatamente o formato abaixo:

{{
  "tool": "nome-da-tool",
  "arguments": {{
    "nome-do-argumento": "valor"
  }}
}}

⚠️ **IMPORTANTE**: Não adicione explicações, comentários ou qualquer texto fora do JSON.
**A resposta deve conter somente o JSON.** Nenhum texto antes ou depois.
Identifique se o texto é uma resposta da Tool somente então converta a resposta bruta em um texto formal para o usuário.
"""

    def clean_json_response(self, json_text: str) -> str:
        """Extract and clean JSON from LLM response.

        Args:
            json_text: Raw response text from LLM

        Returns:
            Cleaned JSON string

        Raises:
            ValueError: If no valid JSON is found
        """
        # Remove code block markers
        cleaned_text = re.sub(
            r'```(?:json)?', '', json_text, flags=re.IGNORECASE
        ).strip('` \n')

        # Find first valid JSON block
        match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
        if not match:
            raise ValueError('No valid JSON found in response')

        return match.group(0)

    async def _execute_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> ToolResponse:
        """Execute a tool and handle the response.

        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments for the tool

        Returns:
            ToolResponse object with results

        Raises:
            ValueError: If tool is not found
            Exception: For tool execution errors
        """
        for mcp_client in self.mcp_clients:
            tools = await mcp_client.list_tools()
            if any(tool.name == tool_name for tool in tools):
                try:
                    result = await mcp_client.execute_tool(
                        tool_name, arguments
                    )

                    if isinstance(result, dict) and 'progress' in result:
                        progress = result['progress']
                        total = result.get('total', 1)
                        return ToolResponse(
                            content=result,
                            is_progress=True,
                            progress=progress,
                            total=total,
                        )
                    return ToolResponse(content=result)

                except Exception as e:
                    logging.error(
                        f'Tool execution error: {str(e)}', exc_info=True
                    )
                    raise

        raise ValueError(f'No available client has tool: {tool_name}')

    async def process_llm_response(
        self, llm_response: str
    ) -> Union[str, ToolResponse]:
        """Process LLM response and handle tool execution if needed.

        Args:
            llm_response: Raw response from LLM

        Returns:
            Either the original response or tool execution result
        """
        try:
            json_response = self.clean_json_response(llm_response)
            tool_call = json.loads(json_response)

            if not all(key in tool_call for key in ('tool', 'arguments')):
                return llm_response

            logging.info(f"Executing tool: {tool_call['tool']}")
            logging.debug(f"With arguments: {tool_call['arguments']}")

            return await self._execute_tool(
                tool_call['tool'], tool_call['arguments']
            )

        except (ValueError, json.JSONDecodeError) as e:
            logging.debug(f'No tool call detected: {str(e)}')
            return llm_response
        except Exception as e:
            logging.error(
                f'Error processing tool call: {str(e)}', exc_info=True
            )
            return f'Error executing tool: {str(e)}'

    def format_for_llm(self, tool: Tool) -> str:
        """Format tool information for LLM consumption.

        Args:
            tool: Tool object to format

        Returns:
            Formatted string with tool description
        """
        args_desc = []
        properties = tool.inputSchema.get('properties', {})

        for param_name, param_info in properties.items():
            arg_desc = f"- {param_name}: {param_info.get('description', 'No description')}"
            if param_name in tool.inputSchema.get('required', []):
                arg_desc += ' (required)'
            args_desc.append(arg_desc)

        return (
            f'\nTool: {tool.name}\n'
            f'Description: {tool.description}\n'
            f'Arguments:\n{chr(10).join(args_desc)}'
        )

    async def initialize_clients(self) -> None:
        """Initialize all MCP clients with error handling."""
        for client in self.mcp_clients:
            try:
                await client.initialization()
                logging.info(f'Initialized MCP client: {client.name}')
            except Exception as e:
                logging.error(f'Failed to initialize MCP client: {str(e)}')
                await self.cleanup_clients()
                raise

    async def get_available_tools(self) -> List[Tool]:
        """Retrieve all available tools from all clients."""
        all_tools = []
        for client in self.mcp_clients:
            try:
                tools = await client.list_tools()
                all_tools.extend(tools)
                logging.debug(f'Found {len(tools)} tools in {client.name}')
            except Exception as e:
                logging.warning(
                    f'Failed to list tools from {client.name}: {str(e)}'
                )
        return all_tools

    def build_system_message(self, tools: List[Tool]) -> Dict[str, str]:
        """Construct the system message with tool descriptions."""
        tools_description = '\n'.join(
            [self.format_for_llm(tool) for tool in tools]
        )

        return {
            'role': 'system',
            'content': self.system_prompt_template.format(
                tools_description=f'\n\nAvailable tools:\n{tools_description}'
            ),
        }

    async def chat_loop(
        self, initial_messages: Optional[List[Dict[str, str]]] = None
    ) -> None:
        """Main chat loop with user interaction.

        Args:
            initial_messages: Optional initial conversation history
        """
        try:
            await self.initialize_clients()
            tools = await self.get_available_tools()

            messages = initial_messages or [self.build_system_message(tools)]

            while True:
                try:
                    user_input = input('You: ').strip()
                    if not user_input:
                        continue

                    if user_input.lower() in ('quit', 'exit', 'stop'):
                        logging.info('Ending chat session...')
                        break

                    messages.append({'role': 'user', 'content': user_input})

                    # Get initial LLM response
                    llm_response = self.llm_client.chat(
                        messages, temperature=0.1
                    )
                    logging.info(f'\nAssistant: {llm_response}')

                    # Process potential tool call
                    tool_result = await self.process_llm_response(llm_response)

                    if isinstance(tool_result, ToolResponse):
                        messages.append(
                            {'role': 'assistant', 'content': llm_response}
                        )

                        if tool_result.is_progress:
                            progress_msg = (
                                f'Progress: {tool_result.progress}/{tool_result.total} '
                                f'({(tool_result.progress/tool_result.total)*100:.1f}%)'
                            )
                            logging.info(progress_msg)
                            messages.append(
                                {'role': 'system', 'content': progress_msg}
                            )

                        # Get final response after tool execution
                        final_response = self.llm_client.chat(
                            messages
                            + [
                                {
                                    'role': 'system',
                                    'content': str(tool_result.content),
                                }
                            ]
                        )
                        logging.info(f'\nFinal response: {final_response}')
                        if final_response:
                            messages.append(
                                {
                                    'role': 'assistant',
                                    'content': final_response,
                                }
                            )
                    else:
                        messages.append(
                            {'role': 'assistant', 'content': tool_result}
                        )

                except KeyboardInterrupt:
                    logging.info('\nEnding chat session...')
                    break
                except Exception as e:
                    logging.error(
                        f'Error in chat loop: {str(e)}', exc_info=True
                    )
                    messages.append(
                        {
                            'role': 'system',
                            'content': f'Error occurred: {str(e)}',
                        }
                    )

        finally:
            await self.cleanup_clients()

    async def cleanup_clients(self) -> None:
        """Clean up all client properly."""

        for mcp_client in self.mcp_clients:
            try:
                await mcp_client.cleanup()
            except Exception as e:
                logging.warning(f'Warning during final cleanup: {e}')
