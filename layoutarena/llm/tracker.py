from __future__ import annotations

from typing import Any, Dict, Union

from langchain_core.messages import BaseMessage

from layoutarena.llm.schema import PRICING_PER_1K_TOKENS, Model


def get_input_output_tokens(
    response: Any,
) -> tuple[int, int]:
    try:
        # LiteLLM's ModelResponse shape (duck-typing to avoid importing litellm).
        usage = getattr(response, "usage", None)
        if usage is not None:
            prompt = getattr(usage, "prompt_tokens", None)
            completion = getattr(usage, "completion_tokens", None)
            if isinstance(prompt, int) and isinstance(completion, int):
                return (prompt, completion)

        if hasattr(response, "response_metadata"):
            return (
                response.response_metadata["token_usage"].prompt_tokens,
                response.response_metadata["token_usage"].completion_tokens,
            )
    except Exception as e:
        print(f"Error getting input/output tokens: {e}")
    return (0, 0)


def calculate_cost(response: BaseMessage, model: Union[Model, str]) -> Dict[str, float]:
    input_tokens, output_tokens = get_input_output_tokens(response)

    try:
        pricing = PRICING_PER_1K_TOKENS[model]
    except Exception as e:
        try:
            pricing = None
            for k, v in PRICING_PER_1K_TOKENS.items():
                if model.lower() in k.lower():
                    input_cost = (input_tokens / 1000) * v.input
                    output_cost = (output_tokens / 1000) * v.output
                    return {
                        "total_cost": input_cost + output_cost,
                        "input_cost": input_cost,
                        "output_cost": output_cost,
                    }
        except Exception as e:
            print(f"Error getting pricing for model {model}: {e}. Return 0 cost.")

        print(f"Error getting pricing for model {model}: {e}. Return 0 cost.")
        return {
            "total_cost": 0,
            "input_cost": 0,
            "output_cost": 0,
        }

    input_cost = (input_tokens / 1000) * pricing.input
    output_cost = (output_tokens / 1000) * pricing.output

    return {
        "total_cost": input_cost + output_cost,
        "input_cost": input_cost,
        "output_cost": output_cost,
    }


class ResourceTracker:
    def __init__(self):
        # self.input_tokens = 0
        # self.output_tokens = 0
        # self.total_cost = 0
        self.data_by_model: Dict[Model, Dict[str, float]] = {}
        self.total_data: Dict[str, float] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0,
        }

    def update_usage(self, response: BaseMessage, model: Union[Model, str]) -> None:
        try:
            input_tokens, output_tokens = get_input_output_tokens(response)
            cost = calculate_cost(response, model)
            if model not in self.data_by_model:
                self.data_by_model[model] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_cost": 0,
                    "num_responses": 0,
                }

            self.data_by_model[model]["input_tokens"] += input_tokens
            self.data_by_model[model]["output_tokens"] += output_tokens
            self.data_by_model[model]["total_cost"] += cost["total_cost"]
            self.data_by_model[model]["num_responses"] += 1

            # Update total data
            self.total_data["input_tokens"] += input_tokens
            self.total_data["output_tokens"] += output_tokens
            self.total_data["total_cost"] += cost["total_cost"]
            self.total_data["num_responses"] += 1
        except Exception as e:
            print(f"Error updating usage: {e}")

    def get_summary(self) -> Dict[str, float]:
        return {
            "total_cost": self.total_data["total_cost"],
            "input_tokens": self.total_data["input_tokens"],
            "output_tokens": self.total_data["output_tokens"],
            "num_responses": self.total_data["num_responses"],
        }

    def get_summary_by_model(self, model: Model) -> Dict[str, float]:
        return {
            "input_tokens": self.data_by_model[model]["input_tokens"],
            "output_tokens": self.data_by_model[model]["output_tokens"],
            "total_cost": self.data_by_model[model]["total_cost"],
            "num_responses": self.data_by_model[model]["num_responses"],
        }
