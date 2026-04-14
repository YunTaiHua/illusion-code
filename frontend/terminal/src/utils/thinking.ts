/**
 * 思考过程处理工具
 *
 * 处理两种思考过程来源：
 * 1. XML 标签包裹：`<think...</think` （DeepSeek、MiniMax 等模型）
 * 2. 独立 reasoning 文本：通过后端 reasoning_content 字段传输（Kimi k2.5 等 OpenAI 兼容模型）
 */

// 匹配完整的 <think...> 和 </think...> 标签
const THINK_OPEN_TAG = /<think\b[^>]*>/gi;
const THINK_CLOSE_TAG = /<\/think\b[^>]*>/gi;
// 匹配未闭合的 <think 开头标签（流式传输时标签可能被截断）
const THINK_OPEN_INCOMPLETE = /<th(?:i(?:n(?:k)?)?)?\s*$/i;
// 匹配完整的开闭标签对及其内容
const THINK_BLOCK_FULL = /<think\b[^>]*>[\s\S]*?<\/think\b[^>]*>/gi;

/**
 * 清除 `<think` 标签包裹的思考块（保留标签外的内容）
 * 处理完整标签、嵌套标签和流式截断的不完整标签
 */
export function stripThinkTags(raw: string): string {
	if (!raw) return '';

	// 先移除完整的 <think...</think 块（包括内容）
	let result = raw.replace(THINK_BLOCK_FULL, '');

	// 移除孤立的闭合标签
	result = result.replace(THINK_CLOSE_TAG, '');

	// 移除孤立的开标签（可能是不完整的块）
	result = result.replace(THINK_OPEN_TAG, '');

	// 移除被截断的不完整开标签（如 "<th"、"<thi"、"<thin"）
	result = result.replace(THINK_OPEN_INCOMPLETE, '');

	return result.trim();
}

/**
 * 从包含 `<think` 标签的文本中提取思考过程内容
 * 返回标签内的文本（去除标签本身）
 */
export function extractThinkContent(raw: string): string {
	if (!raw) return '';

	const parts: string[] = [];
	let remaining = raw;

	// 提取所有完整 <think...</think 块的内容
	let match: RegExpExecArray | null;
	THINK_BLOCK_FULL.lastIndex = 0;
	let lastIndex = 0;

	while ((match = THINK_BLOCK_FULL.exec(remaining)) !== null) {
		// 标签前的内容中检查是否有孤立的开标签
		const before = remaining.slice(lastIndex, match.index);
		if (THINK_OPEN_TAG.test(before)) {
			// 孤立开标签后的内容也是思考过程
			THINK_OPEN_TAG.lastIndex = 0;
			const openMatch = THINK_OPEN_TAG.exec(before);
			if (openMatch) {
				parts.push(before.slice(openMatch.index + openMatch[0].length));
			}
		}

		// 提取标签对内的内容
		const inner = match[0].replace(THINK_OPEN_TAG, '').replace(THINK_CLOSE_TAG, '');
		parts.push(inner.trim());

		lastIndex = match.index + match[0].length;
		THINK_OPEN_TAG.lastIndex = 0;
		THINK_CLOSE_TAG.lastIndex = 0;
	}

	// 检查剩余文本中是否有未闭合的开标签（流式截断场景）
	const tail = remaining.slice(lastIndex);
	THINK_OPEN_TAG.lastIndex = 0;
	const openInTail = THINK_OPEN_TAG.exec(tail);
	if (openInTail) {
		parts.push(tail.slice(openInTail.index + openInTail[0].length).trim());
	} else if (THINK_OPEN_INCOMPLETE.test(tail)) {
		// 不完整标签，忽略
	} else {
		// 如果没有匹配到任何 think 块，检查是否有推理文本
		// （不会走到这里如果没有 think 标签）
	}

	return parts.filter(Boolean).join('\n');
}

/**
 * 判断文本是否包含 `<think` 标签
 */
export function hasThinkTags(raw: string): boolean {
	if (!raw) return false;
	return /<think\b/i.test(raw);
}

/**
 * 渲染助手消息文本，根据 showThinking 决定是否显示思考过程
 *
 * @param raw 原始文本（可能包含 `<think` 标签）
 * @param showThinking 是否显示思考过程
 * @param reasoning 独立的推理文本（来自 reasoning_content 字段，无标签）
 * @returns 显示给用户的文本
 */
export function renderAssistantText(
	raw: string,
	showThinking: boolean,
	reasoning?: string,
): string {
	if (!raw && !reasoning) return '';

	const hasTags = hasThinkTags(raw);
	let cleanText = raw;
	let thinkContent = '';

	if (hasTags) {
		thinkContent = extractThinkContent(raw);
		cleanText = stripThinkTags(raw);
	}

	if (showThinking) {
		const parts: string[] = [];
		if (reasoning) parts.push(reasoning);
		if (thinkContent && thinkContent !== reasoning) parts.push(thinkContent);
		if (cleanText) parts.push(cleanText);
		return parts.filter(Boolean).join('\n\n').trim();
	}

	return cleanText.trim();
}
