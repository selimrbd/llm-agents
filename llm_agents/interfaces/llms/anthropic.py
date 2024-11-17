import asyncio
import json
from typing import Any, Optional

import aiohttp

from llm_agents.config import get_environment_variable

from ._base import LLMClient, LLMModel, Prompt

ANTHROPIC_API_KEY: str = get_environment_variable("ANTHROPIC_API_KEY")

URL_ANTHROPIC_MESSAGE = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = ""


class ClaudeSendMessageError(Exception): ...


class ClaudeModel(LLMModel):
    """Claude Models available through their API."""

    HAIKU3 = "claude-3-haiku-20240307"
    SONNET3 = "claude-3-sonnet-20240229"
    SONNET3P5 = "claude-3-5-sonnet-20241022"


class ClaudeClient(LLMClient):

    def __init__(
        self,
        system_prompt: Optional[Prompt] = None,
        model: ClaudeModel = ClaudeModel.SONNET3P5,
    ):
        self.system_prompt = Prompt("") if system_prompt is None else system_prompt
        self.model = model
        self.headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        self.history: list[list[dict[str, str]]] = []

    async def send(
        self,
        message: str,
        is_stream: bool = False,
        stream_delay_sec: float = 0.1,
        limit_history: Optional[int] = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model.value,
            "max_tokens": 1024,
        }
        recent_history = (
            self.history[-limit_history:] if limit_history is not None else self.history
        )
        messages = [msg for list_msg in recent_history for msg in list_msg] + [
            {"role": "user", "content": message}
        ]
        payload["messages"] = messages

        if self.system_prompt:
            payload["system"] = self.system_prompt()
        if is_stream:
            payload["stream"] = True

        async with aiohttp.ClientSession() as session:
            async with session.post(
                URL_ANTHROPIC_MESSAGE, json=payload, headers=self.headers
            ) as res:
                if res.status != 200:
                    error_message = f"Error (status={res.status}): {await res.text()}"
                    raise ClaudeSendMessageError(error_message)

                if is_stream:
                    answer = ""
                    current_event = ""

                    async for line in res.content:
                        line = line.decode("utf-8").strip()
                        if not line:
                            continue

                        # Handle event lines
                        if line.startswith("event: "):
                            current_event = line[7:]  # Remove 'event: ' prefix
                            continue
                        # Handle data lines
                        if not line.startswith("data: "):
                            continue
                        data = json.loads(line[6:])

                        if current_event == "content_block_delta":
                            if data["type"] == "content_block_delta":
                                new_content = data["delta"]["text"]
                                answer += new_content

                                # Update display
                                # clear_output(wait=True)
                                # display(Markdown(answer))
                                await asyncio.sleep(stream_delay_sec)
                        elif current_event == "message_stop":
                            break

                    self.history.append(
                        [
                            {"role": "user", "content": message},
                            {"role": "assistant", "content": answer},
                        ]
                    )
                    return answer

                # no stream
                response_data = await res.json()
                answer = response_data["content"][0]["text"]
                self.history.append(
                    [
                        {"role": "user", "content": message},
                        {"role": "assistant", "content": answer},
                    ]
                )
                return answer

    # def send_sync(
    #     self,
    #     message: str,
    #     is_stream: bool = False,
    #     stream_delay_sec: float = 0.1,
    #     limit_history: Optional[int] = None,
    # ) -> str:
    #     payload: dict[str, Any] = {
    #         "model": self.model.value,
    #         "max_tokens": 1024,
    #     }
    #     recent_history = (
    #         self.history[-limit_history:] if limit_history is not None else self.history
    #     )
    #     messages = [msg for list_msg in recent_history for msg in list_msg] + [
    #         {"role": "user", "content": message}
    #     ]
    #     payload["messages"] = messages

    #     if self.system:
    #         payload["system"] = self.system
    #     if is_stream:
    #         payload["stream"] = True

    #     res = requests.post(URL_ANTHROPIC_MESSAGE, json=payload, headers=self.headers)

    #     if res.status_code == 200:
    #         if is_stream:

    #             answer = ""
    #             current_event = ""

    #             for line in res.iter_lines():
    #                 if not line:
    #                     continue
    #                 line = line.decode("utf-8")

    #                 # Handle event lines
    #                 if line.startswith("event: "):
    #                     current_event = line[7:]  # Remove 'event: ' prefix
    #                     continue
    #                 # Handle data lines
    #                 if not line.startswith("data: "):
    #                     continue
    #                 data = json.loads(line[6:])

    #                 if current_event == "content_block_delta":
    #                     if data["type"] == "content_block_delta":
    #                         new_content = data["delta"]["text"]
    #                         answer += new_content

    #                         # Update display
    #                         clear_output(wait=True)
    #                         display(Markdown(answer))
    #                         time.sleep(stream_delay_sec)
    #                 elif current_event == "message_stop":
    #                     break

    #             self.history.append(
    #                 [
    #                     {"role": "user", "content": message},
    #                     {"role": "assistant", "content": answer},
    #                 ]
    #             )
    #             return answer

    #         else:
    #             answer = res.json()["content"][0]["text"]
    #             self.history.append(
    #                 [
    #                     {"role": "user", "content": message},
    #                     {"role": "assistant", "content": answer},
    #                 ]
    #             )
    #             return answer
    #     else:
    #         print(f"Error: {res.status_code}")
    #         print(res.text)
    #         return None
