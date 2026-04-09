import React from 'react';
import {Box, Text} from 'ink';

import type {UiLanguage} from '../i18n.js';
import {t} from '../i18n.js';
import {useTheme} from '../theme/ThemeContext.js';
import type {TranscriptItem} from '../types.js';

const MAX_OUTPUT_LINES = 8;
const MAX_SUMMARY_LENGTH = 100;

export function ToolCallDisplay({item, language}: {item: TranscriptItem; language: UiLanguage}): React.JSX.Element {
	const {theme} = useTheme();

	if (item.role === 'tool') {
		return <ToolUseMessage item={item} language={language} theme={theme} />;
	}

	if (item.role === 'tool_result') {
		return <ToolResultMessage item={item} theme={theme} />;
	}

	return <Text>{item.text}</Text>;
}

function ToolUseMessage({
	item,
	language,
	theme,
}: {
	item: TranscriptItem;
	language: UiLanguage;
	theme: ReturnType<typeof useTheme>['theme'];
}): React.JSX.Element {
	const toolName = item.tool_name ?? 'tool';
	const summary = summarizeInput(toolName, item.tool_input, item.text);

	return (
		<Box marginLeft={2} marginTop={0} marginBottom={0}>
			<Text color={theme.colors.muted}>{theme.icons.tool} </Text>
			<Text color={theme.colors.accent} bold>{toolName}</Text>
			{summary ? (
				<>
					<Text dimColor> (</Text>
					<Text dimColor>{summary}</Text>
					<Text dimColor>)</Text>
				</>
			) : null}
		</Box>
	);
}

function ToolResultMessage({
	item,
	theme,
}: {
	item: TranscriptItem;
	theme: ReturnType<typeof useTheme>['theme'];
}): React.JSX.Element {
	const lines = item.text.split('\n');
	const truncated = lines.length > MAX_OUTPUT_LINES;
	const display = truncated
		? [...lines.slice(0, MAX_OUTPUT_LINES), `  ... ${lines.length - MAX_OUTPUT_LINES} more lines`]
		: lines;

	const color = item.is_error ? theme.colors.error : theme.colors.muted;
	const icon = item.is_error ? theme.icons.error : theme.icons.check;

	return (
		<Box marginLeft={4} flexDirection="column" marginTop={0} marginBottom={0}>
			{display.map((line, i) => (
				<Text key={i} color={color} dimColor={!item.is_error}>
					{i === 0 ? `${icon} ` : '  '}
					{line}
				</Text>
			))}
		</Box>
	);
}

function summarizeInput(toolName: string, toolInput?: Record<string, unknown>, fallback?: string): string {
	if (!toolInput) {
		return truncate(fallback ?? '', MAX_SUMMARY_LENGTH);
	}

	const lower = toolName.toLowerCase();

	if (lower === 'bash' && toolInput.command) {
		return truncate(String(toolInput.command), MAX_SUMMARY_LENGTH);
	}

	if ((lower === 'read' || lower === 'fileread' || lower === 'read_file') && (toolInput.path || toolInput.file_path)) {
		return String(toolInput.path ?? toolInput.file_path);
	}

	if ((lower === 'write' || lower === 'filewrite' || lower === 'write_file') && (toolInput.path || toolInput.file_path)) {
		return String(toolInput.path ?? toolInput.file_path);
	}

	if ((lower === 'edit' || lower === 'fileedit' || lower === 'edit_file') && (toolInput.path || toolInput.file_path)) {
		return String(toolInput.path ?? toolInput.file_path);
	}

	if (lower === 'grep' && toolInput.pattern) {
		return `/${String(toolInput.pattern)}/`;
	}

	if (lower === 'glob' && toolInput.pattern) {
		return String(toolInput.pattern);
	}

	if (lower === 'agent' && toolInput.description) {
		return truncate(String(toolInput.description), MAX_SUMMARY_LENGTH);
	}

	if (lower === 'todowrite' && Array.isArray(toolInput.todos)) {
		const total = toolInput.todos.length;
		const completed = toolInput.todos.filter((t: {status: string}) => t.status === 'completed').length;
		return `${completed}/${total} tasks`;
	}

	const entries = Object.entries(toolInput);
	if (entries.length > 0) {
		const [key, val] = entries[0];
		return truncate(`${key}=${String(val)}`, MAX_SUMMARY_LENGTH);
	}

	return truncate(fallback ?? '', MAX_SUMMARY_LENGTH);
}

function truncate(str: string, maxLength: number): string {
	if (str.length <= maxLength) {
		return str;
	}
	return str.slice(0, maxLength - 1) + '…';
}
