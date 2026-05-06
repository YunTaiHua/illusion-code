import React from 'react';
import {Box, Text} from 'ink';

import type {UiLanguage} from '../i18n.js';
import type {ThemeConfig} from '../theme/ThemeContext.js';
import {useTheme} from '../theme/ThemeContext.js';
import type {TranscriptItem} from '../types.js';

const MAX_OUTPUT_LINES = 8;
const MAX_SUMMARY_LENGTH = 120;

export function ToolCallDisplay({item, language}: {item: TranscriptItem; language: UiLanguage}): React.JSX.Element {
	const theme = useTheme();

	if (item.role === 'tool') {
		return <ToolUseMessage item={item} theme={theme} />;
	}

	if (item.role === 'tool_result') {
		return <ToolResultMessage item={item} theme={theme} />;
	}

	return <Text>{item.text}</Text>;
}

function ToolUseMessage({
	item,
	theme,
}: {
	item: TranscriptItem;
	theme: ThemeConfig;
}): React.JSX.Element {
	const toolName = item.tool_name ?? 'tool';
	const summary = summarizeInput(toolName, item.tool_input, item.text);

	return (
		<Box>
			<Text color={theme.colors.info}>{theme.icons.tool} </Text>
			<Text color={theme.colors.info} bold>{toolName}</Text>
			{summary ? (
				<>
					<Text dimColor>{' ('}</Text>
					<Text dimColor>{summary}</Text>
					<Text dimColor>{')'}</Text>
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
	theme: ThemeConfig;
}): React.JSX.Element {
	const lines = item.text.split('\n');
	const truncated = lines.length > MAX_OUTPUT_LINES;
	const display = truncated
		? [...lines.slice(0, MAX_OUTPUT_LINES), `… +${lines.length - MAX_OUTPUT_LINES} lines`]
		: lines;

	const isError = item.is_error;
	const icon = isError ? theme.icons.cross : theme.icons.check;
	const iconColor = isError ? theme.colors.error : theme.colors.success;

	return (
		<Box flexDirection="column">
			{display.map((line, i) => (
				<Box key={i}>
					<Text dimColor>{i === 0 ? `  ${theme.icons.resultPrefix} ` : '    '}</Text>
					{i === 0 ? (
						<Text color={iconColor}>{icon} </Text>
					) : null}
					{i !== 0 ? <Text>{' '}</Text> : null}
					<Text color={isError ? theme.colors.error : undefined} dimColor={!isError}>
						{line}
					</Text>
				</Box>
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
	if (lower === 'todowrite' || lower === 'todo_write') {
		const todos = toolInput.todos;
		if (Array.isArray(todos)) {
			const total = todos.length;
			const completed = todos.filter((t: {status: string}) => t.status === 'completed').length;
			return `${completed}/${total} tasks`;
		}
	}
	if (lower === 'ask_user_question') {
		const questions = toolInput.questions;
		if (Array.isArray(questions) && questions.length > 0) {
			const q = questions[0] as Record<string, unknown>;
			return truncate(String(q.question ?? ''), MAX_SUMMARY_LENGTH);
		}
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
