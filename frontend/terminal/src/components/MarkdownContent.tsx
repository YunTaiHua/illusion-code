import {lexer} from 'marked';
import React, {type ReactNode, useMemo} from 'react';
import {Box, Text} from 'ink';
import type {Token, Tokens} from 'marked';
import {MarkdownTable} from './MarkdownTable.js';
import {useTheme} from '../theme/ThemeContext.js';

type ThemeConfig = ReturnType<typeof useTheme>['theme'];

// Claude Code dark theme permission color (used for inline code)
const INLINE_CODE_COLOR = '#b1b9f9';

/**
 * Recursively render inline tokens (bold, italic, code spans, links, text).
 */
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
				const code = i === 0 ? `${ct.text} ` : ` ${ct.text} `;
				result.push(
					<Text key={k} color={INLINE_CODE_COLOR}>{code}</Text>,
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

/** Render a list item's content with inline token processing */
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

				// Right-aligned line number width based on total lines
				const numWidth = String(codeLines.length).length;

				elements.push(
					<Box key={`t-${ki++}`} flexDirection="column">
						{codeLines.map((line, li) => {
							const lineNum = String(li + 1).padStart(numWidth);
							const trimmed = line.trimStart();

							// Diff syntax coloring
							let lineColor = theme.colors.subtle;
							if (trimmed.startsWith('+') && !trimmed.startsWith('+++')) {
								lineColor = theme.colors.success;
							} else if (trimmed.startsWith('-') && !trimmed.startsWith('---')) {
								lineColor = theme.colors.error;
							} else if (trimmed.startsWith('@@')) {
								lineColor = theme.colors.info;
							}

							return (
								<Text key={li} color={lineColor}>
									<Text dimColor>{`  ${lineNum} │ `}</Text>
									{line || ' '}
								</Text>
							);
						})}
					</Box>,
				);
				break;
			}

			case 'heading': {
				const ht = token as Tokens.Heading;
				const content = renderInline(ht.tokens, theme, `h-${ki}`);

				if (ht.depth === 1) {
					// h1: bold + underline + highlight
					elements.push(
						<Text key={`t-${ki++}`} bold underline color={theme.colors.highlight}>
							{content}
						</Text>,
					);
				} else if (ht.depth === 2) {
					// h2: bold + highlight
					elements.push(
						<Text key={`t-${ki++}`} bold color={theme.colors.highlight}>
							{content}
						</Text>,
					);
				} else {
					// h3+: bold + subtle
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
	const elements = useMemo(() => {
		if (!text.trim()) return [];
		try {
			const tokens = lexer(text);
			return tokensToElements(tokens, theme);
		} catch {
			return text.split('\n').map((line, i) => <Text key={`f-${i}`}>{line}</Text>);
		}
	}, [text, theme]);

	return (
		<Box flexDirection="column">
			{elements}
		</Box>
	);
}
