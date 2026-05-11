from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4

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
from chinatravel.config import get_bool_env, get_env_value


def chat_template(messages):
    formatted = ""
    for msg in messages:
        formatted += f"<|{msg['role']}|>\n{msg['content']}\n"
    formatted += "<|assistant|>\n"
    return formatted


def trace_llm_call(
    *,
    call_id: str,
    model: str,
    messages,
    response: str | None,
    duration_sec: float,
    input_tokens: int,
    output_tokens: int,
    error: str | None,
) -> None:
    if not get_bool_env("CHINATRAVEL_LLM_TRACE_ENABLED", True):
        return

    request_id = os.getenv("CHINATRAVEL_REQUEST_ID") or "unknown-request"
    trace_root = Path(get_env_value("CHINATRAVEL_LLM_TRACE_DIR") or "cache/traces")
    trace_dir = trace_root / request_id
    trace_dir.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "call_id": call_id,
        "model": model,
        "duration_sec": duration_sec,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "messages": messages,
        "response": response,
        "error": error,
    }
    with (trace_dir / "llm_calls.jsonl").open("a", encoding="utf-8") as trace_file:
        trace_file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    if not get_bool_env("CHINATRAVEL_LLM_TRACE_CONSOLE", True):
        return

    console = sys.__stdout__
    console.write(
        "\n"
        f"[LLM TRACE] request_id={request_id} call_id={call_id} "
        f"model={model} duration={duration_sec:.2f}s "
        f"input_tokens={input_tokens} output_tokens={output_tokens}\n"
    )
    if get_bool_env("CHINATRAVEL_LLM_TRACE_CONSOLE_PROMPTS", False):
        console.write("[LLM PROMPT]\n")
        console.write(json.dumps(messages, ensure_ascii=False, default=str) + "\n")
    if response is not None:
        console.write("[LLM RESPONSE]\n")
        console.write(response + "\n")
    if error is not None:
        console.write("[LLM ERROR]\n")
        console.write(error + "\n")
    console.flush()


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
        call_id = uuid4().hex[:12]
        started = time.time()
        text = (
            chat_template(messages)
            if self.tokenizer is None
            else self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        )
        input_tokens = self._count_tokens(text)
        self.input_token_count += input_tokens
        self.input_token_maxx = max(self.input_token_maxx, input_tokens)

        try:
            res_str = self.llm.chat.completions.create(messages=messages, **kwargs).choices[0].message.content
        except Exception as exc:
            trace_llm_call(
                call_id=call_id,
                model=kwargs.get("model", self.config.model),
                messages=messages,
                response=None,
                duration_sec=time.time() - started,
                input_tokens=input_tokens,
                output_tokens=0,
                error=str(exc),
            )
            raise

        output_tokens = self._count_tokens(res_str)
        self.output_token_count += output_tokens
        res_str = res_str.strip()
        trace_llm_call(
            call_id=call_id,
            model=kwargs.get("model", self.config.model),
            messages=messages,
            response=res_str,
            duration_sec=time.time() - started,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            error=None,
        )
        return res_str

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
