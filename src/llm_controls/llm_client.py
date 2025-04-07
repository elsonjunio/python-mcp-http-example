from typing import List, Dict, Any, Iterator, Optional
import httpx
import json


class LLMClient:
    """Client for interacting with LLM API with support for both regular and streaming responses."""

    def __init__(self, base_url: str = 'http://localhost:1234/v1') -> None:
        """Initialize the LLM client."""
        self.base_url = base_url
        self.client = httpx.Client(timeout=None)

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model: str = 'local-model',
    ) -> str:
        """Send chat messages and get a single completion response.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Controls randomness (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            model: Model identifier to use

        Returns:
            Generated content from the LLM

        Raises:
            httpx.HTTPStatusError: If the API request fails
            KeyError: If the response format is unexpected
        """

        url = f'{self.base_url}/chat/completions'
        headers = {'Content-Type': 'application/json'}
        payload = {
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'stream': False,
            'model': model,
        }
        response = self.client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model: str = 'local-model',
    ) -> Iterator[str]:
        """Stream chat completions from the LLM.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Controls randomness (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            model: Model identifier to use

        Yields:
            Chunks of generated content as they become available

        Raises:
            httpx.HTTPStatusError: If the API request fails
            json.JSONDecodeError: If the streaming response is malformed
            RuntimeError: LLM API request failed without response
        """
        url = f'{self.base_url}/chat/completions'
        headers = {'Content-Type': 'application/json'}
        payload = {
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'stream': True,
            'model': model,
        }
        try:
            with self.client.stream(
                'POST', url, headers=headers, json=payload
            ) as response:
                response.raise_for_status()

                for line in response.iter_lines():
                    if line.strip():
                        clean = line.lstrip('data: ').strip()
                        if clean == '[DONE]':
                            break
                        try:
                            data = json.loads(clean)
                            delta = (
                                data.get('choices', [{}])[0]
                                .get('delta', {})
                                .get('content', '')
                            )
                            yield delta
                        except json.JSONDecodeError as e:
                            raise json.JSONDecodeError(
                                f'Failed to decode LLM stream data: {clean}',
                                e.doc,
                                e.pos,
                            )
        except httpx.HTTPError as e:
            request = getattr(e, 'request', None)
            response_e = getattr(e, 'response', None)

            if isinstance(request, httpx.Request) and isinstance(
                response_e, httpx.Response
            ):
                raise httpx.HTTPStatusError(
                    f'LLM API request failed: {str(e)}',
                    request=request,
                    response=response_e,
                ) from e
            else:
                raise RuntimeError(
                    f'LLM API request failed without response: {str(e)}'
                ) from e
