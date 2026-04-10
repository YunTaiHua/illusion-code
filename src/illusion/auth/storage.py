"""
安全凭据存储模块
================

本模块为 IllusionCode 提供安全的凭据存储功能。

默认后端：~/.illusion/credentials.json，权限 600
可选后端：系统 keyring（如果安装了 keyring 包）

函数说明：
    - store_credential: 存储凭据
    - load_credential: 加载凭据
    - clear_provider_credentials: 清除提供商凭据
    - store_external_binding/load_external_binding: 外部绑定存储/加载
    - encrypt/decrypt: 轻量级混淆加密

使用示例：
    >>> from illusion.auth.storage import store_credential, load_credential
    >>> store_credential("anthropic", "api_key", "sk-...")
    >>> key = load_credential("anthropic", "api_key")
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from illusion.config.paths import get_config_dir

# 模块级日志记录器
log = logging.getLogger(__name__)

# 常量定义
_CREDS_FILE_NAME = "credentials.json"  # 凭据文件名
_KEYRING_SERVICE = "illusion"  # keyring 服务名


@dataclass(frozen=True)
class ExternalAuthBinding:
    """指向外部 CLI 管理的凭据的指针
    
    Attributes:
        provider: 提供商名称
        source_path: 源路径
        source_kind: 源类型
        managed_by: 管理程序
        profile_label: 配置标签
    """

    provider: str
    source_path: str
    source_kind: str
    managed_by: str
    profile_label: str = ""


# ---------------------------------------------------------------------------
# 文件后端（始终可用）
# ---------------------------------------------------------------------------


def _creds_path() -> Path:
    """获取凭据文件路径"""
    return get_config_dir() / _CREDS_FILE_NAME


def _load_creds_file() -> dict[str, Any]:
    """加载凭据文件
    
    Returns:
        dict[str, Any]: 凭据数据字典
    """
    path = _creds_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Failed to read credentials file: %s", exc)
        return {}


def _save_creds_file(data: dict[str, Any]) -> None:
    """保存凭据文件
    
    Args:
        data: 凭据数据字典
    """
    path = _creds_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Keyring 后端（可选）
# ---------------------------------------------------------------------------


def _keyring_available() -> bool:
    """检查 keyring 是否可用
    
    Returns:
        bool: keyring 是否可用
    """
    try:
        import keyring  # noqa: F401

        return True
    except ImportError:
        return False


def _keyring_key(provider: str, key: str) -> str:
    """生成 keyring 键
    
    Args:
        provider: 提供商名称
        key: 键名
    
    Returns:
        str: 组合键名
    """
    return f"{provider}:{key}"


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------


def store_credential(provider: str, key: str, value: str, *, use_keyring: bool | None = None) -> None:
    """持久化 provider 下的凭据
    
    如果未设置 use_keyring，在可用时使用 keyring。
    
    Args:
        provider: 提供商名称
        key: 键名
        value: 凭据值
        use_keyring: 是否使用 keyring（可选）
    """
    if use_keyring is None:
        use_keyring = _keyring_available()

    if use_keyring:
        try:
            import keyring

            keyring.set_password(_KEYRING_SERVICE, _keyring_key(provider, key), value)
            log.debug("Stored %s/%s in keyring", provider, key)
            return
        except Exception as exc:
            log.warning("Keyring store failed, falling back to file: %s", exc)

    data = _load_creds_file()
    data.setdefault(provider, {})[key] = value
    _save_creds_file(data)
    log.debug("Stored %s/%s in credentials file", provider, key)


def load_credential(provider: str, key: str, *, use_keyring: bool | None = None) -> str | None:
    """返回存储的凭据，未找到返回 None
    
    Args:
        provider: 提供商名称
        key: 键名
        use_keyring: 是否使用 keyring（可选）
    
    Returns:
        str | None: 凭据值或 None
    """
    if use_keyring is None:
        use_keyring = _keyring_available()

    if use_keyring:
        try:
            import keyring

            value = keyring.get_password(_KEYRING_SERVICE, _keyring_key(provider, key))
            if value is not None:
                return value
        except Exception as exc:
            log.warning("Keyring load failed, falling back to file: %s", exc)

    data = _load_creds_file()
    return data.get(provider, {}).get(key)


def clear_provider_credentials(provider: str, *, use_keyring: bool | None = None) -> None:
    """删除 provider 的所有存储凭据
    
    Args:
        provider: 提供商名称
        use_keyring: 是否使用 keyring（可选）
    """
    if use_keyring is None:
        use_keyring = _keyring_available()

    if use_keyring:
        try:
            import keyring
            from keyring.errors import PasswordDeleteError

            # 尝试常见键；静默忽略缺失的
            for key in ("api_key", "token", "github_token"):
                try:
                    keyring.delete_password(_KEYRING_SERVICE, _keyring_key(provider, key))
                except (PasswordDeleteError, Exception):
                    pass
        except ImportError:
            pass

    data = _load_creds_file()
    if provider in data:
        del data[provider]
        _save_creds_file(data)
    log.debug("Cleared credentials for provider: %s", provider)


def list_stored_providers() -> list[str]:
    """返回文件中存储了凭据的提供商列表
    
    Returns:
        list[str]: 提供商名称列表
    """
    return list(_load_creds_file().keys())


def store_external_binding(binding: ExternalAuthBinding) -> None:
    """持久化描述 provider 外部认证源的元数据
    
    Args:
        binding: 外部认证绑定
    """
    data = _load_creds_file()
    entry = data.setdefault(binding.provider, {})
    entry["external_binding"] = asdict(binding)
    _save_creds_file(data)
    log.debug("Stored external auth binding for provider: %s", binding.provider)


def load_external_binding(provider: str) -> ExternalAuthBinding | None:
    """如果存在，加载 provider 的外部认证绑定元数据
    
    Args:
        provider: 提供商名称
    
    Returns:
        ExternalAuthBinding | None: 外部绑定或 None
    """
    entry = _load_creds_file().get(provider, {})
    if not isinstance(entry, dict):
        return None
    raw = entry.get("external_binding")
    if not isinstance(raw, dict):
        return None
    try:
        return ExternalAuthBinding(
            provider=str(raw["provider"]),
            source_path=str(raw["source_path"]),
            source_kind=str(raw["source_kind"]),
            managed_by=str(raw["managed_by"]),
            profile_label=str(raw.get("profile_label", "") or ""),
        )
    except KeyError:
        log.warning("Ignoring malformed external auth binding for provider: %s", provider)
        return None


# ---------------------------------------------------------------------------
# 加密/解密辅助函数（轻量级 XOR 混淆，非真正加密）
# ---------------------------------------------------------------------------


def _obfuscation_key() -> bytes:
    """返回从主目录路径派生的每用户混淆密钥
    
    Returns:
        bytes: 32 字节混淆密钥
    """
    seed = str(Path.home()).encode() + b"illusion-v1"
    # 通过 SHA-256 简单重复密钥拉伸到 32 字节以保持确定性
    import hashlib

    return hashlib.sha256(seed).digest()


def encrypt(plaintext: str) -> str:
    """轻量级混淆 plaintext（base64 编码 XOR）。非加密。
    
    Args:
        plaintext: 明文
    
    Returns:
        str: 混淆后的字符串
    """
    import base64

    key = _obfuscation_key()
    data = plaintext.encode("utf-8")
    xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return base64.urlsafe_b64encode(xored).decode("ascii")


def decrypt(ciphertext: str) -> str:
    """encrypt 的反向操作
    
    Args:
        ciphertext: 混淆的字符串
    
    Returns:
        str: 明文
    """
    import base64

    key = _obfuscation_key()
    data = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
    xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return xored.decode("utf-8")
