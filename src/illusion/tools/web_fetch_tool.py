"""
网页抓取和摘要工具
==================

本模块提供获取和摘要远程网页内容的功能。

主要组件：
    - WebFetchTool: 抓取并摘要网页的工具

使用示例：
    >>> from illusion.tools import WebFetchTool
    >>> tool = WebFetchTool()
"""

from __future__ import annotations

import re

import httpx
from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class WebFetchToolInput(BaseModel):
    """网页抓取参数。

    属性：
        url: 要抓取的 HTTP 或 HTTPS URL
        max_chars: 最大返回字符数（500-50000）
    """

    url: str = Field(description="HTTP or HTTPS URL to fetch")
    max_chars: int = Field(default=12000, ge=500, le=50000)


class WebFetchTool(BaseTool):
    """抓取一个网页并返回紧凑的文本摘要。

    用于获取和分析网络内容。
    """

    name = "web_fetch"
    description = """- Fetches content from a specified URL and processes it using an AI model
- Takes a URL and a prompt as input
- Fetches the URL content, converts HTML to markdown
- Processes the content with the prompt using a small, fast model
- Returns the model's response about the content
- Use this tool when you need to retrieve and analyze web content

Usage notes:
  - IMPORTANT: If an MCP-provided web fetch tool is available, prefer using that tool instead of this one, as it may have fewer restrictions.
  - The URL must be a fully-formed valid URL
  - HTTP URLs will be automatically upgraded to HTTPS
  - The prompt should describe what information you want to extract from the page
  - This tool is read-only and does not modify any files
  - Results may be summarized if the content is very large
  - Includes a self-cleaning 15-minute cache for faster responses when repeatedly accessing the same URL
  - When a URL redirects to a different host, the tool will inform you and provide the redirect URL in a special format. You should then make a new WebFetch request with the redirect URL to fetch the content.
  - For GitHub URLs, prefer using the gh CLI via Bash instead (e.g., gh pr view, gh issue view, gh api)."""
    input_model = WebFetchToolInput

    async def execute(self, arguments: WebFetchToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        try:
            # 发起 HTTP 请求
            async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
                response = await client.get(arguments.url, headers={"User-Agent": "IllusionCode/0.1"})
                response.raise_for_status()
        except httpx.HTTPError as exc:
            return ToolResult(output=f"web_fetch failed: {exc}", is_error=True)

        # 处理响应内容
        content_type = response.headers.get("content-type", "")
        body = response.text
        # 如果是 HTML，转换为纯文本
        if "html" in content_type:
            body = _html_to_text(body)
        body = body.strip()
        # 截断过长的内容
        if len(body) > arguments.max_chars:
            body = body[: arguments.max_chars].rstrip() + "\n...[truncated]"
        return ToolResult(
            output=(
                f"URL: {response.url}\n"
                f"Status: {response.status_code}\n"
                f"Content-Type: {content_type or '(unknown)'}\n\n"
                f"{body}"
            )
        )

    def is_read_only(self, arguments: BaseModel) -> bool:
        del arguments
        return True


def _html_to_text(html: str) -> str:
    """将 HTML 转换为纯文本。"""
    # 移除 script 和 style 标签
    text = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", html)
    # 移除所有 HTML 标签
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    # 替换 HTML 实体
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    # 规范化空白
    return re.sub(r"[ \t\r\f\v]+", " ", text).replace(" \n", "\n").strip()
