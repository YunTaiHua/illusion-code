"""
LLM 提供商注册表模块
===================

本模块作为 LLM 提供商元数据的单一事实来源。

添加新提供商：
    1. 在下面的 PROVIDERS 中添加 ProviderSpec。
    完成。检测、显示和配置都由此派生。

顺序很重要 - 它控制匹配优先级。网关和云提供商优先，
标准提供商按关键字，本地/特殊提供商最后。

类型说明：
    - ProviderSpec: 提供商元数据数据类

函数说明：
    - find_by_name: 按名称查找提供商
    - detect_provider_from_registry: 检测最佳匹配的 ProviderSpec

使用示例：
    >>> from illusion.api.registry import PROVIDERS, detect_provider_from_registry
    >>> spec = detect_provider_from_registry("claude-3-sonnet", None, None)
    >>> print(f"检测到的提供商: {spec.name}")
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSpec:
    """LLM 提供商元数据
    
    Attributes:
        name: 规范名称，如 "dashscope"
        keywords: 模型名称关键字元组，用于检测（小写）
        env_key: 主要 API 密钥环境变量
        display_name: 状态/诊断中显示的名称
        backend_type: 后端类型（"anthropic"、"openai_compat"、"copilot"）
        default_base_url: 该提供商的备用基础 URL
        detect_by_key_prefix: 匹配 api_key 前缀，如 "sk-or-"
        detect_by_base_keyword: 匹配 base_url 中的子字符串
        is_gateway: 是否为网关（OpenRouter、AiHubMix 等）
        is_local: 是否为本地部署（vLLM、Ollama）
        is_oauth: 是否使用 OAuth 而非 API 密钥
    """
    name: str
    keywords: tuple[str, ...]
    env_key: str
    display_name: str
    backend_type: str
    default_base_url: str
    detect_by_key_prefix: str
    detect_by_base_keyword: str
    is_gateway: bool
    is_local: bool
    is_oauth: bool

    @property
    def label(self) -> str:
        """返回显示标签"""
        return self.display_name or self.name.title()


# ---------------------------------------------------------------------------
# PROVIDERS 注册表 — 顺序 = 检测优先级。
# ---------------------------------------------------------------------------

PROVIDERS: tuple[ProviderSpec, ...] = (
    # === GitHub Copilot (OAuth，通过 api_format="copilot" 检测) ============
    ProviderSpec(
        name="github_copilot",
        keywords=("copilot",),
        env_key="",
        display_name="GitHub Copilot",
        backend_type="copilot",
        default_base_url="",
        detect_by_key_prefix="",
        detect_by_base_keyword="",
        is_gateway=False,
        is_local=False,
        is_oauth=True,
    ),
    # === 网关（通过 api_key 前缀 / base_url 关键字检测） ============
    # OpenRouter：全局网关，密钥以 "sk-or-" 开头
    ProviderSpec(
        name="openrouter",
        keywords=("openrouter",),
        env_key="OPENROUTER_API_KEY",
        display_name="OpenRouter",
        backend_type="openai_compat",
        default_base_url="https://openrouter.ai/api/v1",
        detect_by_key_prefix="sk-or-",
        detect_by_base_keyword="openrouter",
        is_gateway=True,
        is_local=False,
        is_oauth=False,
    ),
    # AiHubMix：OpenAI 兼容网关
    ProviderSpec(
        name="aihubmix",
        keywords=("aihubmix",),
        env_key="OPENAI_API_KEY",
        display_name="AiHubMix",
        backend_type="openai_compat",
        default_base_url="https://aihubmix.com/v1",
        detect_by_key_prefix="",
        detect_by_base_keyword="aihubmix",
        is_gateway=True,
        is_local=False,
        is_oauth=False,
    ),
    # SiliconFlow（硅基流动）：OpenAI 兼容网关
    ProviderSpec(
        name="siliconflow",
        keywords=("siliconflow",),
        env_key="OPENAI_API_KEY",
        display_name="SiliconFlow",
        backend_type="openai_compat",
        default_base_url="https://api.siliconflow.cn/v1",
        detect_by_key_prefix="",
        detect_by_base_keyword="siliconflow",
        is_gateway=True,
        is_local=False,
        is_oauth=False,
    ),
    # VolcEngine（火山引擎 / Ark）：OpenAI 兼容网关
    ProviderSpec(
        name="volcengine",
        keywords=("volcengine", "volces", "ark"),
        env_key="OPENAI_API_KEY",
        display_name="VolcEngine",
        backend_type="openai_compat",
        default_base_url="https://ark.cn-beijing.volces.com/api/v3",
        detect_by_key_prefix="",
        detect_by_base_keyword="volces",
        is_gateway=True,
        is_local=False,
        is_oauth=False,
    ),
    # === 标准云提供商（按模型名称关键字匹配） ============
    # Anthropic：claude-* 模型的原生 SDK
    ProviderSpec(
        name="anthropic",
        keywords=("anthropic", "claude"),
        env_key="ANTHROPIC_API_KEY",
        display_name="Anthropic",
        backend_type="anthropic",
        default_base_url="",
        detect_by_key_prefix="",
        detect_by_base_keyword="",
        is_gateway=False,
        is_local=False,
        is_oauth=False,
    ),
    # OpenAI：gpt-* 模型
    ProviderSpec(
        name="openai",
        keywords=("openai", "gpt", "o1", "o3", "o4"),
        env_key="OPENAI_API_KEY",
        display_name="OpenAI",
        backend_type="openai_compat",
        default_base_url="",
        detect_by_key_prefix="",
        detect_by_base_keyword="",
        is_gateway=False,
        is_local=False,
        is_oauth=False,
    ),
    # DeepSeek
    ProviderSpec(
        name="deepseek",
        keywords=("deepseek",),
        env_key="DEEPSEEK_API_KEY",
        display_name="DeepSeek",
        backend_type="openai_compat",
        default_base_url="https://api.deepseek.com/v1",
        detect_by_key_prefix="",
        detect_by_base_keyword="deepseek",
        is_gateway=False,
        is_local=False,
        is_oauth=False,
    ),
    # Google Gemini
    ProviderSpec(
        name="gemini",
        keywords=("gemini",),
        env_key="GEMINI_API_KEY",
        display_name="Gemini",
        backend_type="openai_compat",
        default_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        detect_by_key_prefix="",
        detect_by_base_keyword="googleapis",
        is_gateway=False,
        is_local=False,
        is_oauth=False,
    ),
    # DashScope（Qwen / 阿里云）
    ProviderSpec(
        name="dashscope",
        keywords=("qwen", "dashscope"),
        env_key="DASHSCOPE_API_KEY",
        display_name="DashScope",
        backend_type="openai_compat",
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        detect_by_key_prefix="",
        detect_by_base_keyword="dashscope",
        is_gateway=False,
        is_local=False,
        is_oauth=False,
    ),
    # Moonshot / Kimi
    ProviderSpec(
        name="moonshot",
        keywords=("moonshot", "kimi"),
        env_key="MOONSHOT_API_KEY",
        display_name="Moonshot",
        backend_type="openai_compat",
        default_base_url="https://api.moonshot.ai/v1",
        detect_by_key_prefix="",
        detect_by_base_keyword="moonshot",
        is_gateway=False,
        is_local=False,
        is_oauth=False,
    ),
    # MiniMax
    ProviderSpec(
        name="minimax",
        keywords=("minimax",),
        env_key="MINIMAX_API_KEY",
        display_name="MiniMax",
        backend_type="openai_compat",
        default_base_url="https://api.minimax.io/v1",
        detect_by_key_prefix="",
        detect_by_base_keyword="minimax",
        is_gateway=False,
        is_local=False,
        is_oauth=False,
    ),
    # Zhipu AI / GLM
    ProviderSpec(
        name="zhipu",
        keywords=("zhipu", "glm", "chatglm"),
        env_key="ZHIPUAI_API_KEY",
        display_name="Zhipu AI",
        backend_type="openai_compat",
        default_base_url="https://open.bigmodel.cn/api/paas/v4",
        detect_by_key_prefix="",
        detect_by_base_keyword="bigmodel",
        is_gateway=False,
        is_local=False,
        is_oauth=False,
    ),
    # Groq
    ProviderSpec(
        name="groq",
        keywords=("groq",),
        env_key="GROQ_API_KEY",
        display_name="Groq",
        backend_type="openai_compat",
        default_base_url="https://api.groq.com/openai/v1",
        detect_by_key_prefix="gsk_",
        detect_by_base_keyword="groq",
        is_gateway=False,
        is_local=False,
        is_oauth=False,
    ),
    # Mistral
    ProviderSpec(
        name="mistral",
        keywords=("mistral", "mixtral", "codestral"),
        env_key="MISTRAL_API_KEY",
        display_name="Mistral",
        backend_type="openai_compat",
        default_base_url="https://api.mistral.ai/v1",
        detect_by_key_prefix="",
        detect_by_base_keyword="mistral",
        is_gateway=False,
        is_local=False,
        is_oauth=False,
    ),
    # StepFun（阶跃星辰）
    ProviderSpec(
        name="stepfun",
        keywords=("step-", "stepfun"),
        env_key="STEPFUN_API_KEY",
        display_name="StepFun",
        backend_type="openai_compat",
        default_base_url="https://api.stepfun.com/v1",
        detect_by_key_prefix="",
        detect_by_base_keyword="stepfun",
        is_gateway=False,
        is_local=False,
        is_oauth=False,
    ),
    # Baidu / ERNIE
    ProviderSpec(
        name="baidu",
        keywords=("ernie", "baidu"),
        env_key="QIANFAN_ACCESS_KEY",
        display_name="Baidu",
        backend_type="openai_compat",
        default_base_url="https://qianfan.baidubce.com/v2",
        detect_by_key_prefix="",
        detect_by_base_keyword="baidubce",
        is_gateway=False,
        is_local=False,
        is_oauth=False,
    ),
    # === 云平台提供商（通过 base_url 检测） ====================
    # AWS Bedrock
    ProviderSpec(
        name="bedrock",
        keywords=("bedrock",),
        env_key="AWS_ACCESS_KEY_ID",
        display_name="AWS Bedrock",
        backend_type="openai_compat",
        default_base_url="",
        detect_by_key_prefix="",
        detect_by_base_keyword="bedrock",
        is_gateway=False,
        is_local=False,
        is_oauth=False,
    ),
    # Google Vertex AI
    ProviderSpec(
        name="vertex",
        keywords=("vertex",),
        env_key="GOOGLE_APPLICATION_CREDENTIALS",
        display_name="Vertex AI",
        backend_type="openai_compat",
        default_base_url="",
        detect_by_key_prefix="",
        detect_by_base_keyword="aiplatform",
        is_gateway=False,
        is_local=False,
        is_oauth=False,
    ),
    # === 本地部署（按关键字或 base_url 匹配） =================
    # Ollama
    ProviderSpec(
        name="ollama",
        keywords=("ollama",),
        env_key="",
        display_name="Ollama",
        backend_type="openai_compat",
        default_base_url="http://localhost:11434/v1",
        detect_by_key_prefix="",
        detect_by_base_keyword="localhost:11434",
        is_gateway=False,
        is_local=True,
        is_oauth=False,
    ),
    # vLLM / 任意 OpenAI 兼容本地服务器
    ProviderSpec(
        name="vllm",
        keywords=("vllm",),
        env_key="",
        display_name="vLLM/Local",
        backend_type="openai_compat",
        default_base_url="",
        detect_by_key_prefix="",
        detect_by_base_keyword="",
        is_gateway=False,
        is_local=True,
        is_oauth=False,
    ),
)


# ---------------------------------------------------------------------------
# 查找辅助函数
# ---------------------------------------------------------------------------


def find_by_name(name: str) -> ProviderSpec | None:
    """按规范名称查找提供商规格，如 "dashscope"。
    
    Args:
        name: 提供商名称
    
    Returns:
        ProviderSpec | None: 提供商规格，如果未找到则返回 None
    """
    for spec in PROVIDERS:
        if spec.name == name:
            return spec
    return None


def _match_by_model(model: str) -> ProviderSpec | None:
    """按模型名称关键字匹配标准/网关提供商（不区分大小写）。
    
    Args:
        model: 模型名称
    
    Returns:
        ProviderSpec | None: 提供商规格，如果未找到则返回 None
    """
    model_lower = model.lower()
    model_normalized = model_lower.replace("-", "_")
    model_prefix = model_lower.split("/", 1)[0] if "/" in model_lower else ""
    normalized_prefix = model_prefix.replace("-", "_")

    # 过滤非本地非 OAuth 的规格
    std_specs = [s for s in PROVIDERS if not s.is_local and not s.is_oauth]

    # 优先显式提供商前缀匹配（如 "deepseek/..." → deepseek 规格）
    for spec in std_specs:
        if model_prefix and normalized_prefix == spec.name:
            return spec

    # 回退到关键字扫描
    for spec in std_specs:
        if any(
            kw in model_lower or kw.replace("-", "_") in model_normalized
            for kw in spec.keywords
        ):
            return spec
    return None


def detect_provider_from_registry(
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> ProviderSpec | None:
    """检测给定输入的最佳匹配 ProviderSpec。
    
    检测优先级：
        1. api_key 前缀（如 "sk-or-" → OpenRouter）
        2. base_url 关键字（如 URL 中的 "aihubmix" → AiHubMix）
        3. 模型名称关键字（如 "qwen" → DashScope）
    
    Args:
        model: 模型名称
        api_key: API 密钥（可选）
        base_url: 基础 URL（可选）
    
    Returns:
        ProviderSpec | None: 最佳匹配的提供商规格
    """
    # 1. api_key 前缀
    if api_key:
        for spec in PROVIDERS:
            if spec.detect_by_key_prefix and api_key.startswith(spec.detect_by_key_prefix):
                return spec

    # 2. base_url 关键字
    if base_url:
        base_lower = base_url.lower()
        for spec in PROVIDERS:
            if spec.detect_by_base_keyword and spec.detect_by_base_keyword in base_lower:
                return spec

    # 3. 模型关键字
    if model:
        return _match_by_model(model)

    return None
