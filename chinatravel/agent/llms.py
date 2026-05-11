from __future__ import annotations

from abc import ABC, abstractmethod
import os

import httpx
from openai import OpenAI

try:
    from json_repair import repair_json
except ImportError:  # pragma: no cover
    def repair_json(value, ensure_ascii=False):
        return value

try:
    from transformers import AutoTokenizer
except ImportError:  # pragma: no cover
    AutoTokenizer = None

from chinatravel.agent.llm_config import DeepSeekConfig, get_deepseek_config


def chat_template(messages):
    formatted = ""
    for msg in messages:
        formatted += f"<|{msg['role']}|>\n{msg['content']}\n"
    formatted += "<|assistant|>\n"
    return formatted


class AbstractLLM(ABC):
    class ModeError(Exception):
        pass

    def __init__(self):
        self.input_token_count = 0
        self.output_token_count = 0
        self.input_token_maxx = 0

    def __call__(self, messages, one_line=True, json_mode=False):
        if one_line and json_mode:
            raise self.ModeError("one_line and json_mode cannot be True at the same time")
        return self._get_response(messages, one_line, json_mode)

    @abstractmethod
    def _get_response(self, messages, one_line, json_mode):
        pass


class Deepseek(AbstractLLM):
    def __init__(self, config: DeepSeekConfig | None = None):
        super().__init__()
        self.config = config or get_deepseek_config()
        self.llm = OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            http_client=httpx.Client(trust_env=self.config.trust_env_proxy),
        )
        self.name = "DeepSeek-V3"
        self.path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "chinatravel",
            "local_llm",
            "deepseek_v3_tokenizer",
        )
        self.tokenizer = (
            AutoTokenizer.from_pretrained(self.path)
            if AutoTokenizer is not None and os.path.exists(self.path)
            else None
        )

    def _count_tokens(self, value):
        if self.tokenizer is None:
            return len(str(value))
        return len(self.tokenizer(value)["input_ids"])

    def _send_request(self, messages, kwargs):
        text = (
            chat_template(messages)
            if self.tokenizer is None
            else self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        )
        input_tokens = self._count_tokens(text)
        self.input_token_count += input_tokens
        self.input_token_maxx = max(self.input_token_maxx, input_tokens)

        res_str = self.llm.chat.completions.create(messages=messages, **kwargs).choices[0].message.content
        self.output_token_count += self._count_tokens(res_str)
        return res_str.strip()

    def _get_response(self, messages, one_line, json_mode):
        try:
            res_str = self._send_request(messages, self.config.request_kwargs(one_line, json_mode))
            if json_mode:
                res_str = repair_json(res_str, ensure_ascii=False)
        except Exception as exc:
            print(exc)
            res_str = '{"error": "Request failed, please try again."}'
        return res_str


class EmptyLLM(AbstractLLM):
    def __init__(self):
        super().__init__()
        self.name = "EmptyLLM"

    def _get_response(self, messages, one_line, json_mode):
        return "Empty LLM response"
