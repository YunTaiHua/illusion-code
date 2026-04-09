import React from 'react';
import {Box, Text} from 'ink';

import type {UiLanguage} from '../i18n.js';
import {t} from '../i18n.js';
import {useTheme} from '../theme/ThemeContext.js';
import type {TranscriptItem} from '../types.js';

export function ToolCallDisplay({item, language}: {item: TranscriptItem; language: UiLanguage}): React.JSX.Element {
	const {theme} = useTheme();

	if (item.role === 'tool') {
		const toolName = item.tool_name ?? 'tool';
		const summary = summarizeInput(toolName, item.tool_input, item.text);
		return (
			<Box marginLeft={2}>
				<Text>
					<Text color={theme.colors.muted}>{theme.icons.tool} {t(language, 'statusExecuting')} </Text>
					<Text color={theme.colors.accent} bold>{toolName}</Text>
					<Text color={theme.colors.muted}> {summary}</Text>
				</Text>
			</Box>
		);
	}

	if (item.role === 'tool_result') {
		const lines = item.text.split('\n');
		const maxLines = 12;
		const truncated = lines.length > maxLines;
		const display = truncated
			? [...lines.slice(0, maxLines), `  ... (${lines.length - maxLines} more lines)`]
			: lines;
		const color = item.is_error ? theme.colors.error : theme.colors.muted;
		return (
			<Box marginLeft={4} flexDirection="column" marginTop={0} marginBottom={0}>
				{display.map((line, i) => (
					<Text key={i} color={color} dimColor={!item.is_error}>
						{line}
					</Text>
				))}
			</Box>
		);
	}

	return <Text>{item.text}</Text>;
}

function summarizeInput(toolName: string, toolInput?: Record<string, unknown>, fallback?: string): string {
	if (!toolInput) {
		return fallback?.slice(0, 80) ?? '';
	}
	const lower = toolName.toLowerCase();
	if (lower === 'bash' && toolInput.command) {
		return String(toolInput.command).slice(0, 120);
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
		return String(toolInput.description);
	}
	// Fallback: show first key=value
	const entries = Object.entries(toolInput);
	if (entries.length > 0) {
		const [key, val] = entries[0];
		return `${key}=${String(val).slice(0, 60)}`;
	}
	return fallback?.slice(0, 80) ?? '';
}
