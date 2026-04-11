import React from 'react';
import {Box, Text, useStdout} from 'ink';

import type {UiLanguage} from '../i18n.js';
import {useTheme} from '../theme/ThemeContext.js';
import type {TranscriptItem} from '../types.js';
import {renderAssistantText} from '../utils/thinking.js';
import {WelcomeBanner} from './WelcomeBanner.js';

const MAX_RESULT_LINES = 8;
const MAX_SUMMARY_LENGTH = 120;

export const ConversationView = React.memo(function ConversationView({
	items,
	assistantBuffer,
	showWelcome,
	language,
	showThinking,
}: {
	items: TranscriptItem[];
	assistantBuffer: string;
	showWelcome: boolean;
	language: UiLanguage;
	showThinking: boolean;
}): React.JSX.Element {
	const {theme} = useTheme();
	const {stdout} = useStdout();

	const grouped = groupToolItems(items.filter((item) => !isEmptyItem(item)));
	const renderedAssistantBuffer = renderAssistantText(assistantBuffer, showThinking);

	// ---------------------------------------------------------------------------
	// Virtualisation: only render items that fit within the terminal viewport.
	//
	// Root cause of flicker + auto-scroll-up:
	//   Ink re-renders the FULL conversation on every state change. When the
	//   rendered output exceeds the terminal height, Ink's cursor-up(N) scrolls
	//   the terminal viewport upward, then the new content pushes it back down.
	//   This up-down jitter produces the "old frame / new frame alternating"
	//   visual and makes the scrollbar jump.
	//
	// Fix: keep Ink's output height ≤ terminal height by rendering only the
	//      tail of the conversation that fits on screen.
	// ---------------------------------------------------------------------------

	const totalRows = stdout?.rows ?? 24;
	// Fixed chrome: status bar (~1), input box (~3), keyboard hints (~1), padding (~1) = ~6
	const fixedRows = 6;
	const availableRows = Math.max(3, totalRows - fixedRows);
	const visibleGrouped = tailToFit(grouped, availableRows);

	return (
		<Box flexDirection="column" overflow="hidden">
			{showWelcome && items.length === 0 ? <WelcomeBanner language={language} /> : null}

			{visibleGrouped.map((entry, index) => {
				const prevRole = index > 0 ? visibleGrouped[index - 1]?.role : undefined;
				if (entry.type === 'tool_group') {
					return <ToolGroupRow key={index} toolItem={entry.toolItem} resultItem={entry.resultItem} theme={theme} prevRole={prevRole} />;
				}
				return <MessageRow key={index} item={entry.item} theme={theme} prevRole={prevRole} showThinking={showThinking} />;
			})}

			{renderedAssistantBuffer ? (
				<Box flexDirection="row" marginTop={1}>
					<Text color={theme.colors.illusion} dimColor>{theme.icons.assistant} </Text>
					<Text>{renderedAssistantBuffer}</Text>
				</Box>
			) : null}
		</Box>
	);
});

/**
 * Walk the grouped entries backwards from the newest, estimating row cost,
 * and return only the tail that fits within `maxRows`.
 */
function tailToFit(entries: GroupEntry[], maxRows: number): GroupEntry[] {
	if (entries.length === 0) {
		return entries;
	}

	const cols = process.stdout?.columns ?? 80;
	let used = 0;
	let start = entries.length;

	for (let i = entries.length - 1; i >= 0; i--) {
		const cost = estimateRows(entries[i], cols);
		if (used + cost > maxRows) {
			break;
		}
		used += cost;
		start = i;
	}

	return entries.slice(start);
}

/** Rough row-cost estimate for a single entry. */
function estimateRows(entry: GroupEntry, termCols: number): number {
	if (entry.type === 'tool_group') {
		let h = 1; // tool header line
		if (entry.resultItem) {
			const textLines = (entry.resultItem.text ?? '').split('\n').filter((l: string) => l.trim() !== '').length;
			h += Math.min(textLines, MAX_RESULT_LINES) + 1; // result lines + icon line
		}
		return h;
	}
	// Single message: at least 1 row, add wrapping estimate
	const text = entry.item.text ?? '';
	const base = 1; // the line itself
	const wrap = text.length > termCols ? Math.ceil((text.length - termCols) / termCols) : 0;
	return base + wrap;
}

function isEmptyItem(item: TranscriptItem): boolean {
	if (item.role === 'assistant' && (!item.text || item.text.trim() === '')) {
		return true;
	}
	if (item.role === 'tool' && (!item.text || item.text.trim() === '') && !item.tool_name) {
		return true;
	}
	return false;
}

type GroupEntry =
	| {type: 'single'; item: TranscriptItem; role: string}
	| {type: 'tool_group'; toolItem: TranscriptItem; resultItem: TranscriptItem | null; role: string};

function groupToolItems(items: TranscriptItem[]): GroupEntry[] {
	const result: GroupEntry[] = [];
	let i = 0;
	while (i < items.length) {
		const item = items[i];
		if (item.role === 'tool') {
			let resultItem: TranscriptItem | null = null;
			if (i + 1 < items.length && items[i + 1].role === 'tool_result' && items[i + 1].tool_name === item.tool_name) {
				resultItem = items[i + 1];
				i += 2;
			} else {
				i += 1;
			}
			result.push({type: 'tool_group', toolItem: item, resultItem, role: 'tool'});
			continue;
		}
		result.push({type: 'single', item, role: item.role});
		i += 1;
	}
	return result;
}

function ToolGroupRow({
	toolItem,
	resultItem,
	theme,
	prevRole,
}: {
	toolItem: TranscriptItem;
	resultItem: TranscriptItem | null;
	theme: ReturnType<typeof useTheme>['theme'];
	prevRole?: string;
}): React.JSX.Element {
	const toolName = toolItem.tool_name ?? 'tool';
	const summary = summarizeInput(toolName, toolItem.tool_input, toolItem.text);
	const needsGap = prevRole !== undefined && prevRole !== 'tool' && prevRole !== 'tool_result';

	return (
		<Box flexDirection="column" marginTop={needsGap ? 1 : 0}>
			<Box>
				<Text color={theme.colors.subtle} dimColor>{theme.icons.tool} </Text>
				<Text color={theme.colors.info} bold>{toolName}</Text>
				{summary ? (
					<>
						<Text dimColor>{' ('}</Text>
						<Text dimColor>{summary}</Text>
						<Text dimColor>{')'}</Text>
					</>
				) : null}
			</Box>
			{resultItem ? <ToolResultBlock item={resultItem} theme={theme} /> : null}
		</Box>
	);
}

function ToolResultBlock({
	item,
	theme,
}: {
	item: TranscriptItem;
	theme: ReturnType<typeof useTheme>['theme'];
}): React.JSX.Element {
	const lines = item.text.split('\n').filter((l) => l.trim() !== '');
	const truncated = lines.length > MAX_RESULT_LINES;
	const display = truncated
		? [...lines.slice(0, MAX_RESULT_LINES), `… +${lines.length - MAX_RESULT_LINES} lines`]
		: lines;

	if (display.length === 0) {
		return (
			<Box>
				<Text dimColor>{`  ${theme.icons.resultPrefix} `}</Text>
				<Text color={theme.colors.success}>{theme.icons.check}</Text>
			</Box>
		);
	}

	const isError = item.is_error;
	const icon = isError ? theme.icons.cross : theme.icons.check;
	const iconColor = isError ? theme.colors.error : theme.colors.success;

	return (
		<Box flexDirection="column">
			{display.map((line, i) => {
				// 差异行着色：+行绿色，-行红色，@@行青色
				let lineColor: string | undefined = undefined;
				let lineDim = !isError;
				const trimmedLine = line.trimStart();
				if (trimmedLine.startsWith('+') && !trimmedLine.startsWith('+++')) {
					lineColor = theme.colors.success;
					lineDim = false;
				} else if (trimmedLine.startsWith('-') && !trimmedLine.startsWith('---')) {
					lineColor = theme.colors.error;
					lineDim = false;
				} else if (trimmedLine.startsWith('@@')) {
					lineColor = theme.colors.info;
					lineDim = false;
				}

				return (
					<Box key={i}>
						<Text dimColor>{i === 0 ? `  ${theme.icons.resultPrefix} ` : '    '}</Text>
						{i === 0 ? (
							<Text color={iconColor}>{icon} </Text>
						) : null}
						{i !== 0 ? <Text>{' '}</Text> : null}
						<Text color={isError ? theme.colors.error : lineColor} dimColor={isError ? false : lineDim}>
							{line}
						</Text>
					</Box>
				);
			})}
		</Box>
	);
}

function MessageRow({
	item,
	theme,
	prevRole,
	showThinking,
}: {
	item: TranscriptItem;
	theme: ReturnType<typeof useTheme>['theme'];
	prevRole?: string;
	showThinking: boolean;
}): React.JSX.Element {
	const assistantText = item.role === 'assistant' ? renderAssistantText(item.text, showThinking) : item.text;

	switch (item.role) {
		case 'user': {
			// 用户消息前添加分隔线，增强对话轮次区分度
			const needsDivider = prevRole !== undefined && prevRole !== 'user';
			return (
				<Box flexDirection="column" marginTop={needsDivider ? 1 : 0}>
					{needsDivider ? (
						<Box marginBottom={0}>
							<Text dimColor>{'─'.repeat(40)}</Text>
						</Box>
					) : null}
					<Box>
						<Text color={theme.colors.illusion}>{theme.icons.pointer} </Text>
						<Text bold>{item.text}</Text>
					</Box>
				</Box>
			);
		}

		case 'assistant':
			if (!assistantText) {
				return <></>;
			}
			return (
				<Box marginTop={1} flexDirection="column">
					<Text>
						<Text color={theme.colors.illusion}>{theme.icons.assistant} </Text>
						<Text>{assistantText}</Text>
					</Text>
				</Box>
			);

		case 'tool_result': {
			return <ToolResultBlock item={item} theme={theme} />;
		}

		case 'system':
			return (
				<Box marginTop={1}>
					<Text>
						<Text color={theme.colors.warning}>{theme.icons.system} </Text>
						<Text color={theme.colors.muted}>{item.text}</Text>
					</Text>
				</Box>
			);

		case 'log':
			return (
				<Box>
					<Text dimColor>{item.text}</Text>
				</Box>
			);

		default:
			return (
				<Box>
					<Text>{item.text}</Text>
				</Box>
			);
	}
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
