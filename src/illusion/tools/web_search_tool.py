"""
简单网页搜索工具
================

本模块提供执行网络搜索并返回紧凑顶部结果的功能。

主要组件：
    - WebSearchTool: 执行网页搜索的工具

使用示例：
    >>> from illusion.tools import WebSearchTool
    >>> tool = WebSearchTool()
"""

from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class WebSearchToolInput(BaseModel):
    """网页搜索参数。

    属性：
        query: 搜索查询
        max_results: 最大结果数量（1-10）
        search_url: 可选的搜索端点覆盖
    """

    query: str = Field(description="Search query")
    max_results: int = Field(default=5, ge=1, le=10, description="Maximum number of results")
    search_url: str | None = Field(
        default=None,
        description="Optional override for the HTML search endpoint, useful for private search backends or testing.",
    )


class WebSearchTool(BaseTool):
    """运行网络搜索并返回紧凑的顶部结果。

    用于获取超出 Illusion 知识截止日期的最新信息。
    """

    name = "web_search"
    description = """- Allows Illusion to search the web and use the results to inform responses
- Provides up-to-date information for current events and recent data
- Returns search result information formatted as search result blocks, including links as markdown hyperlinks
- Use this tool for accessing information beyond Illusion's knowledge cutoff
- Searches are performed automatically within a single API call

CRITICAL REQUIREMENT - You MUST follow this:
  - After answering the user's question, you MUST include a "Sources:" section at the end of your response
  - In the Sources section, list all relevant URLs from the search results as markdown hyperlinks: [Title](URL)
  - This is MANDATORY - never skip including sources in your response
  - Example format:

    [Your answer here]

    Sources:
    - [Source Title 1](https://example.com/1)
    - [Source Title 2](https://example.com/2)

Usage notes:
  - Domain filtering is supported to include or block specific websites
  - Web search is only available in the US

IMPORTANT - Use the correct year in search queries:
  - The current month is <currentMonthYear>. You MUST use this year when searching for recent information, documentation, or current events.
  - Example: If the user asks for "latest React docs", search for "React documentation" with the current year, NOT last year"""
    input_model = WebSearchToolInput

    def is_read_only(self, arguments: WebSearchToolInput) -> bool:
        del arguments
        return True

    async def execute(
        self,
        arguments: WebSearchToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        del context
        # 确定搜索端点
        endpoint = arguments.search_url or "https://html.duckduckgo.com/html/"
        try:
            # 发起搜索请求
            async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
                response = await client.get(
                    endpoint,
                    params={"q": arguments.query},
                    headers={"User-Agent": "IllusionCode/0.1"},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            return ToolResult(output=f"web_search failed: {exc}", is_error=True)

        # 解析搜索结果
        results = _parse_search_results(response.text, limit=arguments.max_results)
        if not results:
            return ToolResult(output="No search results found.", is_error=True)

        # 构建输出
        lines = [f"Search results for: {arguments.query}"]
        for index, result in enumerate(results, start=1):
            lines.append(f"{index}. {result['title']}")
            lines.append(f"   URL: {result['url']}")
            if result["snippet"]:
                lines.append(f"   {result['snippet']}")
        return ToolResult(output="\n".join(lines))


def _parse_search_results(body: str, *, limit: int) -> list[dict[str, str]]:
    """解析搜索结果页面。

    参数：
        body: 搜索结果页面的 HTML 内容
        limit: 最大返回结果数

    返回：
        搜索结果字典列表
    """
    # 提取摘要片段
    snippets = [
        _clean_html(match.group("snippet"))
        for match in re.finditer(
            r'<(?:a|div|span)[^>]+class="[^"]*(?:result__snippet|result-snippet)[^"]*"[^>]*>(?P<snippet>.*?)</(?:a|div|span)>',
            body,
            flags=re.IGNORECASE | re.DOTALL,
        )
    ]

    results: list[dict[str, str]] = []
    # 查找所有链接
    anchor_matches = re.finditer(
        r"<a(?P<attrs>[^>]+)>(?P<title>.*?)</a>",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for index, match in enumerate(anchor_matches):
        attrs = match.group("attrs")
        # 检查是否为结果链接
        class_match = re.search(r'class="(?P<class>[^"]+)"', attrs, flags=re.IGNORECASE)
        if class_match is None:
            continue
        class_names = class_match.group("class")
        if "result__a" not in class_names and "result-link" not in class_names:
            continue
        # 提取 href
        href_match = re.search(r'href="(?P<href>[^"]+)"', attrs, flags=re.IGNORECASE)
        if href_match is None:
            continue
        # 解析标题和 URL
        title = _clean_html(match.group("title"))
        url = _normalize_result_url(href_match.group("href"))
        snippet = snippets[index] if index < len(snippets) else ""
        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= limit:
            break
    return results


def _normalize_result_url(raw_url: str) -> str:
    """规范化 DuckDuckGo 重定向 URL。

    将 /l/ 路径下的重定向 URL 解析为目标 URL。
    """
    parsed = urlparse(raw_url)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target) if target else raw_url
    return raw_url


def _clean_html(fragment: str) -> str:
    """清理 HTML 片段，提取纯文本。"""
    # 移除 HTML 标签
    text = re.sub(r"(?s)<[^>]+>", " ", fragment)
    # 解码 HTML 实体
    text = html.unescape(text)
    # 规范化空白
    text = re.sub(r"\s+", " ", text).strip()
    return text
