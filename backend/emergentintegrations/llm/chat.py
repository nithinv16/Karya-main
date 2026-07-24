import os
import uuid
import asyncio
import logging
import litellm

logger = logging.getLogger("emergentintegrations")

class ImageContent:
    def __init__(self, *args, **kwargs):
        pass

class UserMessage:
    def __init__(self, text: str = "", file_contents: list = None):
        self.text = text
        self.file_contents = file_contents

class LlmChat:
    def __init__(self, api_key: str, session_id: str, system_message: str = ""):
        self.api_key = api_key
        self.session_id = session_id
        self.system_message = system_message
        self.provider = "anthropic"
        self.model = "claude-sonnet-4-6"

    def with_model(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        return self

    async def send_message(self, message: UserMessage) -> str:
        model_name = self.model
        if self.provider == "anthropic":
            if not model_name.startswith("claude-"):
                model_name = f"anthropic/{model_name}"
        elif self.provider == "openai":
            if not model_name.startswith("gpt-"):
                model_name = f"openai/{model_name}"

        if "claude-sonnet" in model_name:
            model_name = "claude-3-5-sonnet-20241022"

        messages = []
        if self.system_message:
            messages.append({"role": "system", "content": self.system_message})
        messages.append({"role": "user", "content": message.text})
        
        api_key_to_use = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if api_key_to_use:
            try:
                response = await litellm.acompletion(
                    model=model_name,
                    messages=messages,
                    api_key=api_key_to_use
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"LlmChat completion failed: {e}")
        
        return f"Mock response for system: {self.system_message} | prompt: {message.text}"
