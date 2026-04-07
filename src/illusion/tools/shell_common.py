"""共享 shell 工具：错误码、输出归一化、命令执行器。"""

from __future__ import annotations

import asyncio
import locale
from dataclasses import dataclass, field
from typing import Any


class ShellErrorCode:
    """标准化 shell 退出码常量。"""

    SUCCESS = 0
    GENERAL_ERROR = 1
    COMMAND_NOT_FOUND = 127
    TIMEOUT = -1
    PERMISSION_DENIED = 126
    SIGNAL_BASE = 128  # 128 + signal_number


@dataclass(frozen=True)
class NormalizedResult:
    """标准化命令执行结果。"""

    output: str
    is_error: bool
    return_code: int
    metadata: dict[str, Any] = field(default_factory=dict)


class OutputNormalizer:
    """输出解码与归一化处理。"""

    @staticmethod
    def decode_output(data: bytes) -> str:
        """健壮解码：UTF-8 → UTF-16LE（如含 null 字节）→ locale → replace。"""
        if not data:
            return ""

        encodings: list[str] = ["utf-8"]

        # Windows PowerShell 经常输出 UTF-16LE —— 含 null 字节时优先尝试
        if b"\x00" in data:
            encodings.append("utf-16-le")

        preferred = locale.getpreferredencoding(False)
        if preferred and preferred.lower() not in {"utf-8", "utf8"}:
            encodings.append(preferred)

        for encoding in encodings:
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue

        return data.decode("utf-8", errors="replace")

    @staticmethod
    def format_result(
        *,
        stdout: bytes,
        stderr: bytes,
        return_code: int,
        timed_out: bool,
        timeout_seconds: int,
    ) -> NormalizedResult:
        """生成上下文相关的输出消息，消除 '(no output)' 歧义。"""
        if timed_out:
            output = f"Command timed out after {timeout_seconds}s"
            return NormalizedResult(
                output=output,
                is_error=True,
                return_code=-1,
                metadata={"returncode": -1, "timed_out": True},
            )

        decoded_stdout = OutputNormalizer.decode_output(stdout).rstrip()
        decoded_stderr = OutputNormalizer.decode_output(stderr).rstrip()

        parts = []
        if decoded_stdout:
            parts.append(decoded_stdout)
        if decoded_stderr:
            parts.append(decoded_stderr)

        text = "\n".join(parts).strip()

        if not text:
            # 上下文相关的空输出消息
            if return_code == 0:
                text = "Command completed successfully (no output produced)\nExit code: 0"
            else:
                text = (
                    f"Process exited with code {return_code} but produced no output\n"
                    f"Exit code: {return_code}"
                )

        if len(text) > 12000:
            text = f"{text[:12000]}\n...[truncated]..."

        return NormalizedResult(
            output=text,
            is_error=return_code != 0,
            return_code=return_code,
            metadata={"returncode": return_code},
        )


class CommandExecutor:
    """统一命令执行器，处理超时、解码、归一化。"""

    @staticmethod
    async def run_and_normalize(
        process: asyncio.subprocess.Process,
        *,
        timeout: int,
    ) -> NormalizedResult:
        """等待进程完成，捕获输出，归一化结果。

        调用方负责创建 process（保留各自的 shell/sandbox 逻辑），
        本方法负责统一的超时、解码、截断和上下文化消息。
        """
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return NormalizedResult(
                output=f"Command timed out after {timeout}s",
                is_error=True,
                return_code=-1,
                metadata={"returncode": -1, "timed_out": True},
            )

        return OutputNormalizer.format_result(
            stdout=stdout or b"",
            stderr=stderr or b"",
            return_code=process.returncode if process.returncode is not None else -1,
            timed_out=False,
            timeout_seconds=timeout,
        )
