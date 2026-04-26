import stripAnsi from 'strip-ansi';
import stringWidth from 'string-width';
import wrapAnsi from 'wrap-ansi';

export {stripAnsi, stringWidth, wrapAnsi};

export function padAligned(
	content: string,
	displayWidth: number,
	targetWidth: number,
	align: 'left' | 'center' | 'right' | null | undefined,
): string {
	const padding = Math.max(0, targetWidth - displayWidth);
	if (align === 'center') {
		const leftPad = Math.floor(padding / 2);
		return ' '.repeat(leftPad) + content + ' '.repeat(padding - leftPad);
	}
	if (align === 'right') {
		return ' '.repeat(padding) + content;
	}
	return content + ' '.repeat(padding);
}

export function wrapText(text: string, width: number, options?: {hard?: boolean}): string[] {
	if (width <= 0) return [text];
	const trimmedText = text.trimEnd();
	const wrapped = wrapAnsi(trimmedText, width, {
		hard: options?.hard ?? false,
		trim: false,
	});
	const lines = wrapped.split('\n').filter((line) => line.length > 0);
	return lines.length > 0 ? lines : [''];
}
