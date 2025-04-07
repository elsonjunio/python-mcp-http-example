# 🧠 Model Context Protocol (MCP) - Hello World

Este projeto é uma implementação de exemplo do Model Context Protocol (MCP), criado para fins de estudo e como material de referência para desenvolvedores.

## Visão Geral

O projeto demonstra como:

    Implementar um servidor MCP simples com ferramentas e recursos

    Criar um cliente MCP para interagir com o servidor

    Integrar um modelo de linguagem (LLM) para orquestrar chamadas de ferramentas


## 📦 Estrutura do Projeto

```
.
├── poetry.lock
├── pyproject.toml
├── README.md
└── src
    ├── __init__.py
    ├── llm_controls
    │   ├── __init__.py
    │   ├── chat_session.py
    │   ├── llm_client.py
    │   └── mcp_http_client.py
    ├── main.py
    └── server
        ├── __init__.py
        └── mcp_simple_resource.py
```
## 🔧 Pré-requisitos

- Python 3.12+
- Poetry
- Servidor MCP rodando e acessível via HTTP/SSE
- Dependências Python instaladas

### Instalação

```bash
git clone https://github.com/elsonjunio/python-mcp-http-example.git
cd python-mcp-http-example
poetry install
```

### Componentes Principais

1. Servidor MCP (src/server/mcp_simple_resource.py)

- Um servidor MCP simples que expõe:

    - Uma ferramenta add para somar dois números
    - Vários recursos dinâmicos e estáticos

Como executar:

```bash
python src/server/mcp_simple_resource.py
```
O servidor estará disponível em http://localhost:8000


2. Cliente MCP (src/llm_controls/mcp_http_client.py)

- Implementa a comunicação com o servidor MCP via HTTP/SSE, permitindo:

    - Listar ferramentas disponíveis
    - Executar ferramentas remotamente
    - Gerenciar recursos


3. Integração com LLM (src/llm_controls/chat_session.py)

- Orquestra a interação entre:

    - O usuário humano
    - O modelo de linguagem (LLM)
    - As ferramentas disponíveis no servidor MCP


4. Ponto de Entrada Principal (src/main.py)

Configura e inicia a sessão de chat integrada.

```bash
python src/main.py
```

## Testando o Sistema
Pré-requisitos

    1 - Servidor MCP em execução (src/server/mcp_simple_resource.py)

    2 - LM Studio (ou outro servidor LLM compatível) executando o modelo Phi-3

## Fluxo de Interação

    1 - Inicie o chat (python src/main.py)

    2 - Digite sua mensagem

    3 - O LLM irá:

        - Responder diretamente quando apropriado

        - Chamar a ferramenta add quando solicitado explicitamente


Exemplo de interação:

```
You: use a ferramenta `add` com os valores 2 e 100
Final response: 
A resposta formal para o usuário seria: A soma dos números 2 e 100 é igual a 102.
```

## Baseado em

Este projeto foi desenvolvido com base em:

[Python SDK do MCP](https://github.com/modelcontextprotocol/python-sdk)

[Exemplo de cliente HTTP MCP](https://github.com/slavashvets/mcp-http-client-example/tree/main)


---
## Testando Componentes Individualmente

Cada classe do projeto pode ser instanciada e testada separadamente, o que facilita o debug e o entendimento do funcionamento de cada parte:

1. Testando o LLMClient (Cliente de Modelo de Linguagem)
```python
from llm_controls.llm_client import LLMClient
import asyncio

def test_llm_client():
    """Exemplo completo para testar o LLMClient com diferentes modos de operação"""
    client = LLMClient()
    
    print("\n🔵 Modos de teste disponíveis:")
    print("1 - Resposta completa (uma única resposta)")
    print("2 - Resposta em streaming (token por token)")
    print("3 - Ambos os modos")
    choice = input("Escolha o modo de teste (1-3): ").strip()
    
    while True:
        try:
            prompt = input("\nDigite sua pergunta (ou 'sair' para encerrar): ")
            if prompt.lower() in ('sair', 'exit', 'quit'):
                break

            messages = [{"role": "user", "content": prompt}]
            
            if choice in ('1', '3'):
                print("\n🔵 Resposta completa:")
                resposta = client.chat(messages)
                print(resposta)
            
            if choice in ('2', '3'):
                print("\n🟢 Resposta em streaming:")
                for chunk in client.chat_stream(messages):
                    print(chunk, end="", flush=True)
                print()  # Nova linha após streaming
            
        except Exception as e:
            print(f"❌ Erro: {str(e)}")

if __name__ == '__main__':
    test_llm_client()

```

2. Testando o MCPClient (Cliente do Servidor MCP)
```python
from llm_controls.mcp_http_client import MCPClient
import asyncio
import logging
from pprint import pprint

# Configuração básica de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_mcp_client():
    """Exemplo completo para testar todas as funcionalidades do MCPClient"""
    try:
        # Inicialização do cliente
        mcp_client = MCPClient('test-client', 'http://localhost:8000/sse')
        await mcp_client.initialization()
        print("\n🟢 Conexão com o servidor MCP estabelecida com sucesso!")
        
        # Listar todas as entidades disponíveis
        print("\n🔍 Listando ferramentas disponíveis:")
        tools = await mcp_client.list_tools()
        pprint([tool.name for tool in tools])
        
        print("\n📦 Listando recursos disponíveis:")
        resources = await mcp_client.list_resources()
        pprint([resource.uri for resource in resources])
        
        print("\n📝 Listando prompts disponíveis:")
        prompts = await mcp_client.list_prompts()
        pprint([prompt.name for prompt in prompts])
        
        # Testar execução de ferramenta (se disponível)
        if tools and tools[0].name == 'add':
            print("\n🧪 Testando execução da ferramenta 'add':")
            result = await mcp_client.execute_tool('add', {'a': 5, 'b': 3})
            print(f"Resultado de 5 + 3 = {result}")
        
    except Exception as e:
        logging.error(f"❌ Erro durante os testes: {str(e)}")
    finally:
        try:
            await mcp_client.cleanup()
            print("\n🛑 Conexão encerrada corretamente")
        except Exception as e:
            logging.warning(f"Aviso durante o cleanup: {str(e)}")

if __name__ == '__main__':
    asyncio.run(test_mcp_client())
```

### Comparação com redes multiagente (arquitetura baseada em múltiplos graphs)

Nos últimos meses, tenho desenvolvido sistemas de agentes utilizando [LangChain](https://python.langchain.com/docs/introduction/), observando padrões comuns em implementações corporativas:

- **Arquitetura típica**: 
  - Dados distribuídos por setores/departamentos
  - Agentes especializados por domínio
  - Processos complexos para consolidação de relatórios

**Principais características do LangChain**:

✔ Framework maduro com ampla adoção  
✔ Capacidade de integrar diversas APIs e fontes de dados  
✔ Mecanismos robustos para orquestração de agentes  
✔ Prompts especializados por contexto/domínio  

**Sobre o MCP** ([Model Context Protocol](https://spec.modelcontextprotocol.io/specification/2025-03-26/)):

🔧 Protocolo aberto para padronização de comunicação LLM-serviços  
🚀 Foco em interoperabilidade entre sistemas  
🧩 Permite construção de agentes complexos com orquestração nativa  

**Cenários de uso complementares**:
1. **Migração gradual**: Adicionar novos componentes via MCP em sistemas LangChain existentes
2. **Arquitetura híbrida**: 
   - LangChain para orquestração principal
   - MCP para integração com serviços especializados
3. **Padronização**: Utilizar MCP como camada de abstração para serviços heterogêneos

**Vantagens da abordagem combinada**:
- Redução de technical debt em integrações customizadas
- Maior flexibilidade para substituir componentes
- Possibilidade de reutilização entre diferentes frameworks

