import time
import sys
from openai import OpenAI
from openai import APIError, APITimeoutError, RateLimitError

from .config import LMStudioConfig
from .exceptions import LMStudioError, ContextOverflowError


class LMStudioClient:
    def __init__(self, config: LMStudioConfig):
        self.config = config
        self._client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.request_timeout_seconds,
            max_retries=0,  # We handle retries ourselves
        )
        self._resolved_model_id: str | None = None

    @staticmethod
    def is_context_overflow_error(exc: Exception) -> bool:
        text = str(exc).lower()
        patterns = [
            "context length",
            "context window",
            "maximum context",
            "too many tokens",
            "prompt is too long",
            "exceeds context",
            "tokens exceed",
            "token limit",
            "maximum token",
        ]
        return any(pattern in text for pattern in patterns)

    def resolve_model_id(self) -> str:
        """Auto-detect the currently loaded model in LM Studio."""
        if self.config.model_id and self.config.model_id != "auto":
            self._resolved_model_id = self.config.model_id
            return self._resolved_model_id

        try:
            models = self._client.models.list()
        except Exception as e:
            raise LMStudioError(
                f"无法连接到 LM Studio API ({self.config.base_url})。"
                f"请确认 LM Studio 已启动 Local Server。\n{e}"
            ) from e

        model_list = list(models)
        if len(model_list) == 0:
            raise LMStudioError(
                "LM Studio 当前没有加载模型。"
                "请先在 LM Studio Developer / Local Server 中加载模型并启动服务器。"
            )

        model_id = model_list[0].id
        if len(model_list) > 1:
            print(
                f"[WARNING] LM Studio 返回多个模型，当前使用第一个：{model_id}。"
                f"如需固定模型，请在 config/default_config.json 设置 lmstudio.model_id。",
                file=sys.stderr,
            )

        self._resolved_model_id = model_id
        return model_id

    def translate(
        self,
        messages: list[dict],
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Send a chat completion request to LM Studio with retry logic."""

        if not self._resolved_model_id:
            self.resolve_model_id()

        model_id = self._resolved_model_id
        max_retries = self.config.max_retries
        retry_sleep = self.config.retry_sleep_seconds

        if max_retries < 1:
            raise LMStudioError(
                f"max_retries 必须 >= 1（总尝试次数），当前为 {max_retries}。"
            )

        request_kwargs = {
            "model": model_id,
            "messages": messages,
            "temperature": self.config.temperature if temperature is None else temperature,
            "top_p": self.config.top_p if top_p is None else top_p,
        }

        if max_tokens is not None:
            if max_tokens <= 0:
                raise LMStudioError(
                    f"max_tokens 必须大于 0，当前为 {max_tokens}。"
                )
            request_kwargs["max_tokens"] = max_tokens

        for attempt in range(max_retries):
            try:
                response = self._client.chat.completions.create(**request_kwargs)

                content = response.choices[0].message.content
                if content is None:
                    raise LMStudioError("模型返回了空内容。")

                return content

            except (APITimeoutError, RateLimitError, APIError) as e:
                if self.is_context_overflow_error(e):
                    raise ContextOverflowError(str(e)) from e

                if attempt < max_retries - 1:
                    print(
                        f"[WARNING] LM Studio 请求失败 (尝试 {attempt + 1}/{max_retries}): {e}",
                        file=sys.stderr,
                    )
                    time.sleep(retry_sleep)
                else:
                    raise LMStudioError(
                        f"LM Studio 请求在 {max_retries} 次尝试后仍然失败: {e}"
                    ) from e
            except Exception as e:
                if self.is_context_overflow_error(e):
                    raise ContextOverflowError(str(e)) from e
                raise
        raise LMStudioError("LM Studio 请求失败（未知错误）。")
