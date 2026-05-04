import {lexer} from 'marked';
import React, {type ReactNode, useMemo} from 'react';
import {Box, Text} from 'ink';
import type {Token, Tokens} from 'marked';
import {MarkdownTable} from './MarkdownTable.js';
import {useTheme} from '../theme/ThemeContext.js';
import {useTerminalSize} from '../hooks/useTerminalSize.js';
import {stringWidth, padAligned, wrapText} from '../utils/markdown.js';

type ThemeConfig = ReturnType<typeof useTheme>['theme'];

const INLINE_CODE_COLOR = '#b1b9f9';

const NAMED_COLORS: Record<string, [number, number, number]> = {
	black: [0, 0, 0], red: [205, 0, 0], green: [0, 205, 0], yellow: [205, 205, 0],
	blue: [0, 0, 238], magenta: [205, 0, 205], cyan: [0, 205, 205], white: [229, 229, 229],
	gray: [128, 128, 128], grey: [128, 128, 128],
};

function colorToAnsi(color: string): string {
	if (color.startsWith('#')) {
		const r = parseInt(color.slice(1, 3), 16);
		const g = parseInt(color.slice(3, 5), 16);
		const b = parseInt(color.slice(5, 7), 16);
		return `38;2;${r};${g};${b}`;
	}
	const rgb = NAMED_COLORS[color.toLowerCase()];
	if (rgb) return `38;2;${rgb[0]};${rgb[1]};${rgb[2]}`;
	return '39';
}

function renderInline(
	tokens: Token[] | undefined,
	theme: ThemeConfig,
	prefix: string,
): ReactNode[] {
	if (!tokens || tokens.length === 0) return [];
	const result: ReactNode[] = [];

	for (let i = 0; i < tokens.length; i++) {
		const t = tokens[i];
		const k = `${prefix}-${i}`;

		switch (t.type) {
			case 'strong': {
				const st = t as Tokens.Strong;
				result.push(
					<Text key={k} bold>{renderInline(st.tokens, theme, k)}</Text>,
				);
				break;
			}
			case 'em': {
				const et = t as Tokens.Em;
				result.push(
					<Text key={k} italic>{renderInline(et.tokens, theme, k)}</Text>,
				);
				break;
			}
			case 'codespan': {
				const ct = t as Tokens.Codespan;
				result.push(
					<Text key={k} color={INLINE_CODE_COLOR}>{ct.text}</Text>,
				);
				break;
			}
			case 'link': {
				const lt = t as Tokens.Link;
				result.push(
					<Text key={k} color={theme.colors.info} underline>
						{renderInline(lt.tokens, theme, k)}
					</Text>,
				);
				break;
			}
			case 'text': {
				const tt = t as Tokens.Text;
				if (tt.tokens && tt.tokens.length > 0) {
					result.push(...renderInline(tt.tokens, theme, k));
				} else {
					result.push(<Text key={k}>{tt.raw ?? tt.text}</Text>);
				}
				break;
			}
			case 'escape': {
				result.push(<Text key={k}>{t.text}</Text>);
				break;
			}
			case 'br': {
				result.push(<Text key={k}>{'\n'}</Text>);
				break;
			}
			default: {
				const raw = (t as {raw?: string}).raw ?? (t as {text?: string}).text ?? '';
				result.push(<Text key={k}>{raw}</Text>);
				break;
			}
		}
	}

	return result;
}

function renderItemContent(item: Tokens.ListItem, theme: ThemeConfig, prefix: string): ReactNode {
	if (!item.tokens || item.tokens.length === 0) {
		return <Text>{item.text}</Text>;
	}

	const parts: ReactNode[] = [];
	for (let i = 0; i < item.tokens.length; i++) {
		const t = item.tokens[i];
		const k = `${prefix}-${i}`;

		if (t.type === 'text') {
			const tt = t as Tokens.Text;
			if (tt.tokens && tt.tokens.length > 0) {
				parts.push(...renderInline(tt.tokens, theme, k));
			} else {
				parts.push(<Text key={k}>{tt.text}</Text>);
			}
		} else if (t.type === 'paragraph') {
			const pt = t as Tokens.Paragraph;
			parts.push(...renderInline(pt.tokens, theme, k));
		} else {
			const raw = (t as {raw?: string}).raw ?? (t as {text?: string}).text ?? '';
			parts.push(<Text key={k}>{raw}</Text>);
		}
	}
	return <>{parts}</>;
}

function tokensToElements(
	tokens: Token[],
	theme: ThemeConfig,
	terminalWidth: number,
): ReactNode[] {
	const elements: ReactNode[] = [];
	let ki = 0;

	for (const token of tokens) {
		switch (token.type) {
			case 'table': {
				elements.push(
					<MarkdownTable key={`t-${ki++}`} token={token as Tokens.Table} />,
				);
				break;
			}

			case 'code': {
				const ct = token as Tokens.Code;
				const codeLines = ct.text.split('\n');
				if (codeLines.length > 0 && codeLines[codeLines.length - 1] === '') {
					codeLines.pop();
				}
				if (codeLines.length === 0) break;

				const numWidth = String(codeLines.length).length;

				// Border width: based on content, capped at terminal width
				let maxContentWidth = 0;
				for (const line of codeLines) {
					const w = stringWidth(line || ' ');
					if (w > maxContentWidth) maxContentWidth = w;
				}
				if (ct.lang) {
					const lw = stringWidth(`${ct.lang}: ${codeLines.length} lines`);
					if (lw > maxContentWidth) maxContentWidth = lw;
				}
				maxContentWidth = Math.max(maxContentWidth, 1);

				// │ numStr │ code │ = numWidth + codeWidth + 7
				const borderWidth = Math.min(numWidth + maxContentWidth + 7, terminalWidth - 4);
				const codeWidth = borderWidth - numWidth - 7;
				const lineDash = '─'.repeat(Math.max(borderWidth - 2, 0));

				const innerLines: string[] = [];

				// Language label + line count inside the border
				if (ct.lang) {
					const labelText = `${ct.lang}: ${codeLines.length} lines`;
					const labelW = stringWidth(labelText);
					const labelPad = ' '.repeat(Math.max(borderWidth - 3 - labelW, 0));
					const gold = `\x1b[1m\x1b[${colorToAnsi(theme.colors.illusion)}m`;
					const rst = '\x1b[39m\x1b[22m';
					innerLines.push(`│ ${gold}${labelText}${rst}${labelPad}│`);
				}

				// Code lines: fully closed borders, wrap long lines only
				if (codeWidth > 0) {
					for (let li = 0; li < codeLines.length; li++) {
						const line = codeLines[li] || ' ';
						const lineNum = numWidth > 1
							? String(li + 1).padStart(numWidth, '0')
							: String(li + 1);
						const trimmed = line.trimStart();

						let color = theme.colors.subtle;
						if (trimmed.startsWith('+') && !trimmed.startsWith('+++')) {
							color = theme.colors.success;
						} else if (trimmed.startsWith('-') && !trimmed.startsWith('---')) {
							color = theme.colors.error;
						} else if (trimmed.startsWith('@@')) {
							color = theme.colors.info;
						}

						const wrapped = wrapText(line, codeWidth, {hard: true});
						for (let wi = 0; wi < wrapped.length; wi++) {
							const segment = wrapped[wi]!;
							const numStr = wi === 0 ? lineNum : ' '.repeat(numWidth);
							const padded = padAligned(segment, stringWidth(segment), codeWidth, 'left');
							const colored = `\x1b[${colorToAnsi(color)}m${padded}\x1b[39m`;
							innerLines.push(`│ ${numStr} │ ${colored} │`);
						}
					}
				}

				const allLines = [`╭${lineDash}╮`, ...innerLines, `╰${lineDash}╯`];
				elements.push(
					<Text key={`t-${ki++}`}>{allLines.join('\n')}</Text>,
				);
				break;
			}

			case 'heading': {
				const ht = token as Tokens.Heading;
				const content = renderInline(ht.tokens, theme, `h-${ki}`);

				if (ht.depth === 1) {
					elements.push(
						<Text key={`t-${ki++}`} bold underline color={theme.colors.highlight}>
							{content}
						</Text>,
					);
				} else if (ht.depth === 2) {
					elements.push(
						<Text key={`t-${ki++}`} bold color={theme.colors.highlight}>
							{content}
						</Text>,
					);
				} else {
					elements.push(
						<Text key={`t-${ki++}`} bold color={theme.colors.subtle}>
							{content}
						</Text>,
					);
				}
				break;
			}

			case 'list': {
				const lt = token as Tokens.List;
				for (let li = 0; li < lt.items.length; li++) {
					const item = lt.items[li];
					const content = renderItemContent(item, theme, `l-${ki}-${li}`);
					elements.push(
						<Text key={`t-${ki++}`}>
							<Text color={theme.colors.muted}>{`  ${theme.icons.arrow} `}</Text>
							{content}
						</Text>,
					);
				}
				break;
			}

			case 'hr': {
				elements.push(
					<Text key={`t-${ki++}`} color={theme.colors.muted}>{'─'.repeat(40)}</Text>,
				);
				break;
			}

			case 'blockquote': {
				const bt = token as Tokens.Blockquote;
				for (const inner of bt.tokens ?? []) {
					if (inner.type === 'paragraph') {
						const pt = inner as Tokens.Paragraph;
						const content = renderInline(pt.tokens, theme, `bq-${ki}`);
						elements.push(
							<Text key={`t-${ki++}`} italic color={theme.colors.muted}>
								<Text>{'  │ '}</Text>
								{content}
							</Text>,
						);
					} else if (inner.type === 'text') {
						const tt = inner as Tokens.Text;
						const content = renderInline(tt.tokens, theme, `bq-${ki}`);
						elements.push(
							<Text key={`t-${ki++}`} italic color={theme.colors.muted}>
								<Text>{'  │ '}</Text>
								{content}
							</Text>,
						);
					}
				}
				break;
			}

			case 'paragraph': {
				const pt = token as Tokens.Paragraph;
				elements.push(
					<Text key={`t-${ki++}`}>
						{renderInline(pt.tokens, theme, `p-${ki}`)}
					</Text>,
				);
				break;
			}

			case 'text': {
				const tt = token as Tokens.Text;
				if (tt.tokens && tt.tokens.length > 0) {
					elements.push(
						<Text key={`t-${ki++}`}>
							{renderInline(tt.tokens, theme, `tx-${ki}`)}
						</Text>,
					);
				} else {
					const raw = tt.raw ?? tt.text ?? '';
					raw.replace(/\n+$/, '').split('\n').forEach((line) => {
						elements.push(<Text key={`t-${ki++}`}>{line}</Text>);
					});
				}
				break;
			}

			default: {
				const raw = (token as {raw?: string}).raw;
				if (raw) {
					raw.replace(/\n+$/, '').split('\n').forEach((line) => {
						elements.push(<Text key={`t-${ki++}`}>{line}</Text>);
					});
				}
				break;
			}
		}
	}

	return elements;
}

export function MarkdownContent({text}: {text: string}): React.JSX.Element {
	const {theme} = useTheme();
	const {columns: terminalWidth} = useTerminalSize();
	const elements = useMemo(() => {
		if (!text.trim()) return [];
		try {
			const tokens = lexer(text);
			return tokensToElements(tokens, theme, terminalWidth);
		} catch {
			return text.split('\n').map((line, i) => <Text key={`f-${i}`}>{line}</Text>);
		}
	}, [text, theme, terminalWidth]);

	return (
		<Box flexDirection="column">
			{elements}
		</Box>
	);
}
