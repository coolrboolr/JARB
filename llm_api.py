import anthropic
import openai
from typing import Literal
import os

def llm_call(query: str, context: str = None, api_choice: Literal['openai', 'anthropic'] = 'openai') -> str:
    if api_choice == 'anthropic':
        client = anthropic.Anthropic(api_key="your_anthropic_api_key_here")
        messages = [{"role": "human", "content": query}]
        if context:
            messages.insert(0, {"role": "assistant", "content": context})

        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            messages=messages
        )
        return response.content[0].text

    elif api_choice == 'openai':
        openai.api_key = os.environ['OPENAI_KEY']
        messages = [{"role": "user", "content": query}]
        if context:
            messages.insert(0, {"role": "assistant", "content": context})

        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()

    else:
        raise ValueError("Invalid API choice. Choose either 'anthropic' or 'openai'.")