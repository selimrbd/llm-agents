from enum import Enum
from typing import Optional, Protocol, Union


class Prompt:

    def __init__(
        self, text: Optional[Union[str, "Prompt", list[Union[str, "Prompt"]]]] = None
    ):
        self.lines: list[str]
        if isinstance(text, str):
            self.lines = [text]
        elif isinstance(text, Prompt):
            self.lines = text.lines
        elif isinstance(text, list):
            self.lines = []
            for t in text:
                if isinstance(t, str):
                    self.lines += [t]
                elif isinstance(t, Prompt):
                    self.lines += t.lines
                else:
                    raise NotImplementedError
        else:
            raise NotImplementedError

    def display(self) -> str:
        """exclude: lines to exclude in the prompt. 1-indexed"""
        max_pad = len(str(len(self.lines)))
        out = [
            f"{i+1} " + " " * (max_pad - len(str(i + 1))) + f" | {l}"
            for i, l in enumerate(self.lines)
        ]
        return "\n".join(out)

    def filter(self, exclude_lines: Optional[list[int]] = None):
        exclude_lines = [] if exclude_lines is None else exclude_lines
        return [l for i, l in enumerate(self.lines) if (i + 1) not in exclude_lines]

    def __call__(self, exclude_lines: Optional[list[int]] = None):
        filtered_lines = self.filter(exclude_lines)
        return "\n".join(filtered_lines)

    def __add__(self, other: Union[str, "Prompt"]) -> "Prompt":
        if isinstance(other, str):
            return Prompt(self.lines + [other])
        return Prompt(self.lines + other.lines)

    def __radd__(self, other: Union[str, "Prompt"]) -> "Prompt":
        return self.__add__(other)

    def __repr__(self):
        return self.display()


class LLMModel(Enum): ...


class LLMClient(Protocol):

    def __init__(
        self,
        system_prompt: Optional[Prompt] = None,
        model: Optional[LLMModel] = None,
    ):
        self.system_prompt: Prompt
        self.model: LLMModel

    async def send(
        self,
        message: str,
        is_stream: bool = False,
        stream_delay_sec: float = 0.1,
        limit_history: Optional[int] = None,
    ) -> str: ...
