const THINK_TAG_REGEX = /<\/?think\b[^>]*>/gi;

export function renderAssistantText(raw: string, showThinking: boolean): string {
	if (!raw) {
		return '';
	}

	if (showThinking) {
		return raw.replace(THINK_TAG_REGEX, '').trim();
	}

	return stripThinkBlocks(raw).trim();
}

function stripThinkBlocks(input: string): string {
	let output = '';
	let depth = 0;
	let cursor = 0;

	for (const match of input.matchAll(THINK_TAG_REGEX)) {
		const index = match.index ?? 0;
		if (depth === 0 && index > cursor) {
			output += input.slice(cursor, index);
		}

		const token = (match[0] || '').toLowerCase();
		if (token.startsWith('</think')) {
			depth = Math.max(0, depth - 1);
		} else {
			depth += 1;
		}

		cursor = index + (match[0]?.length ?? 0);
	}

	if (depth === 0 && cursor < input.length) {
		output += input.slice(cursor);
	}

	return output;
}
