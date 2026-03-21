from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional, Union

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field

from layoutarena.llm.base_schema import CoreModel

# Type aliases for clarity
MessageContent = Union[str, list[dict]]
OpenAIMessage = dict[str, Any]
LangChainMessage = Union[SystemMessage, HumanMessage, AIMessage]

if TYPE_CHECKING:
    # Only needed for typing; importing litellm is expensive and not required
    # for replay-only / offline runs.
    from litellm import ChatCompletionPredictionContentParam
else:
    ChatCompletionPredictionContentParam = Any  # type: ignore[misc,assignment]


class AzureOpenAIFinishReason(str, Enum):
    STOP = "stop"
    LENGTH = "length"
    FUNCTION_CALLS = "function_calls"
    RECITATION = "recitation"
    ERROR = "error"
    UNKNOWN = "unknown"


class ParseType(Enum):
    LIST = "list"
    JSON = "json"
    MARKDOWN = "markdown"
    RAW = "raw"


class AzureOpenAITokenUsage(CoreModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class MessageRole(str, Enum):
    """Message role."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(CoreModel):
    """Chat message."""

    role: MessageRole
    content: MessageContent

    def to_dict(self) -> dict:
        data = {"role": self.role.value, "content": self.content}

        return data

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        return self.get(key)


class MultiGenerationsResponse(BaseModel):
    results: List[BaseModel]
    completion_tokens: int = 0
    prompt_tokens: int = 0
    _raw_response: Any = None

    def __iter__(self) -> Iterator[BaseModel]:
        return iter(self.results)

    def __getitem__(self, index: int) -> BaseModel:
        return self.results[index]

    def __len__(self) -> int:
        return len(self.results)


class ReasoningEffort(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    NONE = "none"


DEFAULT_TEMPERATURE = 0.0001


class LiteLLMKwargs(CoreModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    api_base: Optional[str] = Field(default=None, description="API base")
    timeout: Optional[Union[float, str, httpx.Timeout]] = Field(
        default=None,
        description="Request timeout",
    )
    temperature: Optional[float] = Field(
        default=DEFAULT_TEMPERATURE,
        description="Sampling temperature",
    )
    top_p: Optional[float] = Field(
        default=None,
        description="Nucleus sampling parameter",
    )
    n: Optional[int] = Field(
        default=None,
        description="Number of completions to generate",
    )
    stream: Optional[bool] = Field(
        default=None,
        description="Whether to stream the response",
    )
    stream_options: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Stream options",
    )
    stop: Optional[Union[str, List[str]]] = Field(
        default=None,
        description="Sequences where the API will stop generating",
    )
    max_tokens: Optional[int] = Field(
        default=None,
        description="Maximum number of tokens to generate",
    )
    presence_penalty: Optional[float] = Field(
        default=None,
        description="Presence penalty parameter",
    )
    frequency_penalty: Optional[float] = Field(
        default=None,
        description="Frequency penalty parameter",
    )
    logit_bias: Optional[Dict[str, float]] = Field(
        default=None,
        description="Logit bias dictionary",
    )
    user: Optional[str] = Field(default=None, description="User identifier")
    response_format: Optional[Union[Dict[str, Any], Any]] = Field(
        default=None,
        description="Response format",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Random seed for deterministic output",
    )
    tools: Optional[List[Any]] = Field(default=None, description="List of tools")
    tool_choice: Optional[Union[str, Dict[str, Any]]] = Field(
        default=None,
        description="Tool choice",
    )
    logprobs: Optional[bool] = Field(
        default=None,
        description="Include log probabilities",
    )
    top_logprobs: Optional[int] = Field(
        default=None,
        description="Number of top log probabilities to return",
    )
    parallel_tool_calls: Optional[bool] = Field(
        default=None,
        description="Allow parallel tool calls",
    )
    deployment_id: Optional[str] = Field(
        default=None,
        description="Deployment ID for Azure OpenAI",
    )
    extra_headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Extra headers for the request",
    )
    functions: Optional[List[Any]] = Field(
        default=None,
        description="List of functions (soon to be deprecated)",
    )
    function_call: Optional[str] = Field(
        default=None,
        description="Function call (soon to be deprecated)",
    )
    base_url: Optional[str] = Field(default=None, description="Base URL for the API")
    api_version: Optional[str] = Field(default=None, description="API version")
    api_key: Optional[str] = Field(default=None, description="API key")
    model_list: Optional[List[Any]] = Field(
        default=None,
        description="List of model configurations",
    )
    aws_access_key_id: Optional[str] = Field(
        default=None,
        description="AWS access key ID",
    )
    reasoning_effort: Optional[ReasoningEffort] = Field(
        default=None,
        description="Reasoning effort for o3 models",
    )
    prediction: Optional[ChatCompletionPredictionContentParam] = Field(
        default=None,
        description="Prediction for speculative decoding",
    )

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)


class Provider(str, Enum):
    ollama = "ollama"
    openai = "openai"
    azure = "azure"
    anthropic = "anthropic"
    claude = "claude"
    groq = "groq"
    mistral = "mistral"
    llama3 = "llama3"
    llama2 = "llama2"
    ollama_chat = "ollama_chat"
    perplexity = "perplexity"
    gemini = "gemini"
    vertex_ai = "vertex_ai"


class Model(str, Enum):
    groq_llama3_1_70b_versatile = "groq/llama-3.1-70b-versatile"

    # OpenAI Models
    #     Model	Input	Cached input	Output
    # gpt-5.1	$1.25	$0.125	$10.00
    # gpt-5	$1.25	$0.125	$10.00
    # gpt-5-mini	$0.25	$0.025	$2.00
    # gpt-5-nano	$0.05	$0.005	$0.40
    # gpt-5.1-chat-latest	$1.25	$0.125	$10.00
    # gpt-5-chat-latest	$1.25	$0.125	$10.00
    # gpt-5.1-codex	$1.25	$0.125	$10.00
    # gpt-5-codex	$1.25	$0.125	$10.00
    # gpt-5-pro	$15.00	-	$120.00
    # gpt-4.1	$2.00	$0.50	$8.00
    # gpt-4.1-mini	$0.40	$0.10	$1.60
    # gpt-4.1-nano	$0.10	$0.025	$0.40
    # gpt-4o-mini	$0.15	$0.075	$0.60
    # gpt-realtime	$4.00	$0.40	$16.00
    # gpt-realtime-mini	$0.60	$0.06	$2.40
    # gpt-4o-realtime-preview	$5.00	$2.50	$20.00
    # gpt-4o-mini-realtime-preview	$0.60	$0.30	$2.40
    # gpt-audio	$2.50	-	$10.00
    # gpt-audio-mini	$0.60	-	$2.40
    # gpt-4o-audio-preview	$2.50	-	$10.00
    # gpt-4o-mini-audio-preview	$0.15	-	$0.60
    # o1	$15.00	$7.50	$60.00
    # o1-pro	$150.00	-	$600.00
    # o3-pro	$20.00	-	$80.00
    # o3	$2.00	$0.50	$8.00
    # o3-deep-research	$10.00	$2.50	$40.00
    # o4-mini	$1.10	$0.275	$4.40
    # o4-mini-deep-research	$2.00	$0.50	$8.00
    # o3-mini	$1.10	$0.55	$4.40
    # o1-mini	$1.10	$0.55	$4.40
    # gpt-5.1-codex-mini	$0.25	$0.025	$2.00
    # codex-mini-latest	$1.50	$0.375	$6.00
    # gpt-5-search-api	$1.25	$0.125	$10.00
    # gpt-4o-mini-search-preview	$0.15	-	$0.60
    # gpt-4o-search-preview	$2.50	-	$10.00
    # computer-use-preview	$3.00	-	$12.00
    # gpt-image-1	$5.00	$1.25	-
    # gpt-image-1-mini	$2.00	$0.20	-
    openai_gpt_4o = "gpt-4o"
    openai_gpt_4_1 = "gpt-4.1"
    openai_gpt_5 = "gpt-5"
    openai_gpt_5_1 = "gpt-5.1"
    openai_gpt_5_mini = "gpt-5-mini"
    openai_gpt_5_nano = "gpt-5-nano"
    openai_gpt_5_chat_latest = "gpt-5-chat-latest"
    openai_gpt_5_codex = "gpt-5-codex"
    openai_gpt_5_pro = "gpt-5-pro"
    openai_gpt_4o_2024_05_13 = "gpt-4o-2024-05-13"
    openai_gpt_4o_mini_2024_05_13 = "gpt-4o-mini-2024-05-13"
    openai_gpt_4o_audio_preview = "gpt-4o-audio-preview"
    openai_gpt_4o_mini_audio_preview = "gpt-4o-mini-audio-preview"
    openai_o1 = "o1"
    openai_o1_pro = "o1-pro"
    openai_o3_deep_research = "o3-deep-research"
    openai_o4_mini_deep_research = "o4-mini-deep-research"

    openai_gpt_5_websearch = "openai/responses/gpt-5"
    openai_gpt_4_1_mini = "gpt-4.1-mini"
    openai_gpt_4_1_nano = "gpt-4.1-nano"
    openai_gpt_3_5_turbo = "gpt-3.5-turbo"
    openai_gpt_4o_mini = "gpt-4o-mini"

    gemini_3_pro = "gemini/gemini-3-pro-preview"
    gemini_3_pro_preview = "gemini/gemini-3-pro-preview"
    gemini_2_5_pro_exp_03_25 = "gemini/gemini-2.5-pro"
    gemini_2_5_pro_preview_03_25 = "gemini/gemini-2.5-pro"
    gemini_2_5_pro = "gemini/gemini-2.5-pro"
    gemini_2_5_pro_preview_05_06_agent = "gemini-2.5-pro-preview-05-06"
    gemini_2_5_flash_agent = "gemini-2.5-flash"
    gemini_2_5_flash = "gemini/gemini-2.5-flash"
    gemini_2_5_flash_image = "gemini/gemini-2.5-flash-image"
    gemini_2_0_image = "gemini/gemini-2.0-flash-exp-image-generation"
    gemini_1_5_flash = "gemini/gemini-1.5-flash"
    openai_o3_mini = "o3-mini"
    openai_o3 = "o3"
    openai_o3_pro = "o3-pro"
    openai_o4_mini = "o4-mini"
    perplexity_sonar_deep_research = "perplexity/sonar-deep-research"
    perplexity_sonar_reasoning = "perplexity/sonar-reasoning"
    perplexity_sonar = "perplexity/sonar"
    claude_4_opus = "anthropic/claude-opus-4-20250514"
    claude_4_sonnet = "anthropic/claude-sonnet-4-20250514"
    claude_3_7_sonnet = "anthropic/claude-3-7-sonnet-latest"
    claude_3_5_sonnet = "anthropic/claude-3-5-sonnet"
    claude_3_5_haiku = "anthropic/claude-3-5-haiku-20241022"
    claude_3_haiku = "anthropic/claude-3-haiku-20240307"

    @classmethod
    def gemini_models(cls) -> List[str]:
        return list(
            set(
                [
                    model.value.split("/")[-1]
                    for model in cls
                    if model.startswith("gemini")
                ],
            ),
        )

    @classmethod
    def is_gemini_model(cls, model: str) -> bool:
        return model.startswith("gemini")

    @classmethod
    def is_anthropic_thinking_model(cls, model: str) -> bool:
        for m in [
            Model.claude_4_opus,
            Model.claude_4_sonnet,
            Model.claude_3_7_sonnet,
        ]:
            if model in m.value:
                return True
        return False

    @classmethod
    def from_text_model(cls, model: Optional[str] = None) -> Optional["Model"]:
        """
        Convert a text model string to a Model enum instance.

        First tries exact match, then falls back to substring matching.

        Args:
            model: The model string to convert

        Returns:
            Model enum instance if found, None otherwise
        """
        if model is None:
            return None

        # Try exact match first
        try:
            return cls(model)
        except ValueError:
            pass

        # Fall back to substring matching
        for enum_model in cls:
            if model in enum_model.value:
                return enum_model

        return None


class Pricing(CoreModel):
    input: float  # per 1000 input tokens
    output: float  # per 1000 output tokens
    reasoning: float = 0  # per 1000 reasoning tokens
    search: float = 0  # per search query
    cache: float = 0  # per 1000 cache tokens


PRICING_PER_1K_TOKENS: Dict[Union[Model, str], Pricing] = {
    # OpenAI Models
    Model.openai_gpt_3_5_turbo: Pricing(input=0.0005, output=0.0015),
    Model.openai_gpt_4o: Pricing(input=0.0025, output=0.01, cache=0.00125),
    Model.openai_gpt_4o_mini: Pricing(input=0.00015, output=0.0006, cache=0.000075),
    Model.openai_gpt_4_1: Pricing(input=0.002, output=0.008, cache=0.0005),
    Model.openai_gpt_4_1_mini: Pricing(input=0.0004, output=0.0016, cache=0.0001),
    Model.openai_gpt_4_1_nano: Pricing(input=0.0001, output=0.0004, cache=0.000025),
    Model.openai_o3_mini: Pricing(
        input=0.0011,
        output=0.0044,
        cache=0.00055,
        reasoning=0.0044,
    ),
    Model.openai_o3: Pricing(input=0.002, output=0.008, cache=0.0005, reasoning=0.008),
    Model.openai_o3_pro: Pricing(input=0.02, output=0.08, reasoning=0.08),
    Model.openai_o4_mini: Pricing(
        input=0.0011,
        output=0.0044,
        cache=0.000275,
        reasoning=0.0044,
    ),
    #     Model	Input	Cached input	Output
    # gpt-5.1	$1.25	$0.125	$10.00
    # gpt-5	$1.25	$0.125	$10.00
    # gpt-5-mini	$0.25	$0.025	$2.00
    # gpt-5-nano	$0.05	$0.005	$0.40
    # gpt-5.1-chat-latest	$1.25	$0.125	$10.00
    # gpt-5-chat-latest	$1.25	$0.125	$10.00
    # gpt-5.1-codex	$1.25	$0.125	$10.00
    # gpt-5-codex	$1.25	$0.125	$10.00
    # gpt-5-pro	$15.00	-	$120.00
    # gpt-4.1	$2.00	$0.50	$8.00
    # gpt-4.1-mini	$0.40	$0.10	$1.60
    # gpt-4.1-nano	$0.10	$0.025	$0.40
    # gpt-4o	$2.50	$1.25	$10.00
    # gpt-4o-2024-05-13	$5.00	-	$15.00
    Model.openai_gpt_5: Pricing(input=0.00125, output=0.01, cache=0.000125),
    Model.openai_gpt_5_1: Pricing(input=0.00125, output=0.01, cache=0.000125),
    Model.openai_gpt_5_mini: Pricing(input=0.00025, output=0.002, cache=0.000025),
    Model.openai_gpt_5_nano: Pricing(input=0.00005, output=0.0004, cache=0.000005),
    Model.openai_gpt_5_chat_latest: Pricing(input=0.00125, output=0.01, cache=0.000125),
    Model.openai_gpt_5_codex: Pricing(input=0.00125, output=0.01, cache=0.000125),
    Model.openai_gpt_5_pro: Pricing(input=15.00 / 1000, output=120.00 / 1000),
    Model.openai_gpt_4o_2024_05_13: Pricing(input=5.00 / 1000, output=15.00 / 1000),
    Model.openai_gpt_4o_mini_2024_05_13: Pricing(input=0.005, output=0.015),
    Model.openai_gpt_4o_audio_preview: Pricing(input=2.50 / 1000, output=10.00 / 1000),
    Model.openai_gpt_4o_mini_audio_preview: Pricing(
        input=0.60 / 1000,
        output=2.40 / 1000,
    ),
    Model.openai_o1: Pricing(
        input=15.00 / 1000,
        output=60.00 / 1000,
        cache=7.50 / 1000,
    ),
    Model.openai_o1_pro: Pricing(input=150.00 / 1000, output=600.00 / 1000),
    Model.openai_o3_deep_research: Pricing(
        input=10.00 / 1000,
        output=40.00 / 1000,
        cache=2.50 / 1000,
    ),
    Model.openai_o4_mini_deep_research: Pricing(
        input=2.00 / 1000,
        output=8.00 / 1000,
        cache=0.50 / 1000,
    ),
    # Anthropic Claude Models
    Model.claude_4_opus: Pricing(input=0.015, output=0.075, cache=0.0015),
    Model.claude_4_sonnet: Pricing(input=0.003, output=0.015, cache=0.0003),
    Model.claude_3_7_sonnet: Pricing(input=0.003, output=0.015, cache=0.0003),
    Model.claude_3_5_haiku: Pricing(input=0.0008, output=0.004, cache=0.00008),
    Model.claude_3_haiku: Pricing(input=0.00025, output=0.00125, cache=0.000025),
    # Google Gemini Models
    Model.gemini_3_pro: Pricing(input=0.004, output=0.018, cache=0.0045),
    Model.gemini_3_pro_preview: Pricing(input=0.004, output=0.018, cache=0.0045),
    Model.gemini_2_5_pro_exp_03_25: Pricing(input=0.00125, output=0.01, cache=0.00031),
    Model.gemini_2_5_pro_preview_03_25: Pricing(
        input=0.00125,
        output=0.01,
        cache=0.00031,
    ),
    Model.gemini_2_5_pro: Pricing(input=0.00125, output=0.01, cache=0.00031),
    Model.gemini_2_5_pro_preview_05_06_agent: Pricing(
        input=0.00125,
        output=0.01,
        cache=0.00031,
    ),
    Model.gemini_2_5_flash: Pricing(input=0.0003, output=0.0025, cache=0.000075),
    Model.gemini_2_5_flash_agent: Pricing(input=0.0003, output=0.0025, cache=0.000075),
    Model.gemini_1_5_flash: Pricing(input=0.000075, output=0.0003, cache=0.00001875),
    # Groq Models
    Model.groq_llama3_1_70b_versatile: Pricing(input=0.00059, output=0.00079),
    # Perplexity Models
    Model.perplexity_sonar_deep_research: Pricing(
        input=0.002,
        output=0.008,
        search=0.005,
        reasoning=0.003,
    ),
    Model.perplexity_sonar: Pricing(input=0.001, output=0.001, search=0.005),
    Model.perplexity_sonar_reasoning: Pricing(input=0.001, output=0.005, search=0.005),
}

token_cap_per_model = {
    # OpenAI Models
    Model.openai_gpt_4o: 100_000,
    Model.openai_gpt_4_1: 120_000,
    Model.openai_gpt_4_1_mini: 100_000,
    Model.openai_gpt_4o_mini: 100_000,
    Model.openai_o3_mini: 120_000,
    Model.openai_o4_mini: 120_000,
    Model.openai_o3: 120_000,
    Model.openai_o3_pro: 120_000,
    # Google Gemini Models
    Model.gemini_2_5_pro_exp_03_25: 700_000,
    Model.gemini_2_5_pro_preview_03_25: 700_000,
    Model.gemini_2_5_pro: 700_000,
    Model.gemini_2_5_pro_preview_05_06_agent: 700_000,
    Model.gemini_2_5_flash: 300_000,
    Model.gemini_2_5_flash_agent: 300_000,
    Model.gemini_1_5_flash: 300_000,
    # Groq Models
    Model.groq_llama3_1_70b_versatile: 100_000,
    # Perplexity Models
    Model.perplexity_sonar_deep_research: 100_000,
    Model.perplexity_sonar: 100_000,
    Model.perplexity_sonar_reasoning: 100_000,
    # Anthropic Claude Models
    Model.claude_4_opus: 120_000,
    Model.claude_4_sonnet: 120_000,
    Model.claude_3_7_sonnet: 120_000,
    Model.claude_3_5_haiku: 120_000,
    Model.claude_3_haiku: 120_000,
}


class TokenType(str, Enum):
    INPUT = "input"
    OUTPUT = "output"
    REASONING = "reasoning"
    SEARCH = "search"
    ALL = "all"
    CACHE = "cache"


class Modality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    TABLE = "table"
    CODE = "code"
    PDF = "pdf"
    JSON = "json"
    YAML = "yaml"
    MARKDOWN = "markdown"
