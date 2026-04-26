import {lexer} from 'marked';
import React, {useMemo} from 'react';
import {Box, Text} from 'ink';
import type {Token, Tokens} from 'marked';
import {MarkdownTable} from './MarkdownTable.js';
import {useTheme} from '../theme/ThemeContext.js';

function tokensToElements(
	tokens: Token[],
	theme: ReturnType<typeof useTheme>['theme'],
): React.ReactNode[] {
	const elements: React.ReactNode[] = [];
	let keyIndex = 0;

	for (const token of tokens) {
		if (token.type === 'table') {
			elements.push(
				<MarkdownTable key={`t-${keyIndex++}`} token={token as Tokens.Table} />,
			);
		} else if (token.type === 'code') {
			const codeToken = token as Tokens.Code;
			codeToken.text.split('\n').forEach((line) => {
				elements.push(
					<Text key={`t-${keyIndex++}`}>{line}</Text>,
				);
			});
		} else if (token.type === 'heading') {
			const headingToken = token as Tokens.Heading;
			elements.push(
				<Text key={`t-${keyIndex++}`} bold>{headingToken.text}</Text>,
			);
		} else if (token.type === 'list') {
			const listToken = token as Tokens.List;
			for (const item of listToken.items) {
				const itemText = item.tokens
					?.map((t) => ('text' in t ? (t as {text: string}).text : ''))
					.join('') ?? item.text;
				elements.push(
					<Text key={`t-${keyIndex++}`}>{`  ${theme.icons.arrow} ${itemText}`}</Text>,
				);
			}
		} else if (token.type === 'hr') {
			elements.push(
				<Text key={`t-${keyIndex++}`} color={theme.colors.muted}>{'─'.repeat(40)}</Text>,
			);
		} else if (token.type === 'blockquote') {
			const bqToken = token as Tokens.Blockquote;
			const bqText = bqToken.tokens
				?.map((t) => ('text' in t ? (t as {text: string}).text : ''))
				.join('') ?? '';
			elements.push(
				<Text key={`t-${keyIndex++}`} color={theme.colors.muted}>{`  │ ${bqText}`}</Text>,
			);
		} else if (token.type === 'paragraph' || token.type === 'text') {
			const raw = (token as {raw?: string}).raw ?? (token as {text?: string}).text ?? '';
			raw.replace(/\n+$/, '').split('\n').forEach((line) => {
				elements.push(
					<Text key={`t-${keyIndex++}`}>{line}</Text>,
				);
			});
		} else {
			const raw = (token as {raw?: string}).raw;
			if (raw) {
				raw.replace(/\n+$/, '').split('\n').forEach((line) => {
					elements.push(
						<Text key={`t-${keyIndex++}`}>{line}</Text>,
					);
				});
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
