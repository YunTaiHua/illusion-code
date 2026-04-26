import React, {useMemo} from 'react';
import {Box, Static, Text} from 'ink';

import type {UiLanguage} from '../i18n.js';
import {useTheme} from '../theme/ThemeContext.js';
import type {TranscriptItem} from '../types.js';
import {renderAssistantText} from '../utils/thinking.js';
import {MarkdownContent} from './MarkdownContent.js';
import {WelcomeBanner} from './WelcomeBanner.js';

const MAX_RESULT_LINES = 8;
const MAX_SUMMARY_LENGTH = 120;

export function ConversationView({
	staticItems,
	clearCount,
	assistantBuffer,
	showWelcome,
	showThinking,
	language,
}: {
	staticItems: TranscriptItem[];
	clearCount: number;
	assistantBuffer: string;
	showWelcome: boolean;
	showThinking: boolean;
	language: UiLanguage;
}): React.JSX.Element {
	const {theme} = useTheme();
	const filtered = useMemo(() => staticItems.filter((item) => !isEmptyItem(item)), [staticItems]);
	const grouped = useMemo(() => groupToolItems(filtered), [filtered]);
	const displayedBuffer = useMemo(() => renderAssistantText(assistantBuffer, showThinking, undefined), [assistantBuffer, showThinking]);
	const isSuppressedByStatic = useMemo(() => {
		if (!displayedBuffer) return false;
		const lastAssistant = [...grouped].reverse().find((entry) => entry.role === 'assistant');
		if (!lastAssistant) return false;
		const item = lastAssistant.type === 'single' ? lastAssistant.item : null;
		if (!item) return false;
		const staticDisplayText = renderAssistantText(item.text, showThinking, item.reasoning);
		return isTextSubsetOrEqual(staticDisplayText, displayedBuffer);
	}, [grouped, displayedBuffer, showThinking]);

	return (
		<>
			{showWelcome && grouped.length === 0 ? <WelcomeBanner language={language} /> : null}

			<Static key={clearCount} items={grouped}>
				{(entry, index) => {
					const prevRole = index > 0 ? grouped[index - 1]?.role : undefined;
					if (entry.type === 'tool_group') {
						return <ToolGroupRow key={`s-${index}`} toolItem={entry.toolItem} resultItem={entry.resultItem} theme={theme} prevRole={prevRole} />;
					}
					return <MessageRow key={`s-${index}`} item={entry.item} theme={theme} language={language} prevRole={prevRole} showThinking={showThinking} />;
				}}
			</Static>

			{displayedBuffer && !isSuppressedByStatic ? renderAssistantBlock(displayedBuffer, theme) : null}
		</>
	);
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
				<Text color={theme.colors.info}>{theme.icons.tool}</Text>
				<Text bold>{' '}{toolName}</Text>
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
	language,
	prevRole,
	showThinking = true,
}: {
	item: TranscriptItem;
	theme: ReturnType<typeof useTheme>['theme'];
	language: UiLanguage;
	prevRole?: string;
	showThinking?: boolean;
}): React.JSX.Element {
	switch (item.role) {
		case 'user': {
			const needsDivider = prevRole !== undefined && prevRole !== 'user';
			return (
				<Box flexDirection="column" marginTop={needsDivider ? 1 : 0}>
					{needsDivider ? (
						<Box marginBottom={0}>
							<Text color={theme.colors.text}>{' '}{'─'.repeat(60)}</Text>
						</Box>
					) : null}
					<Box>
						<Text color={theme.colors.illusion}>{theme.icons.pointer}</Text>
						<Text bold>{' '}{item.text}</Text>
					</Box>
				</Box>
			);
		}

		case 'assistant': {
				const displayText = renderAssistantText(item.text, showThinking, item.reasoning);
				return renderAssistantBlock(displayText, theme) ?? <Box />;
			}

		case 'tool_result': {
			return <ToolResultBlock item={item} theme={theme} />;
		}

		case 'system':
			return (
				<Box marginTop={1}>
					<Text>
						<Text color={theme.colors.warning}>{theme.icons.system}</Text>
						<Text color={theme.colors.muted}>{' '}{item.text}</Text>
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

function renderAssistantBlock(text: string, theme: ReturnType<typeof useTheme>['theme']): React.JSX.Element | null {
	if (!text) return null;
	const firstNewline = text.indexOf('\n');
	const firstLine = firstNewline >= 0 ? text.slice(0, firstNewline) : text;
	const restText = firstNewline >= 0 ? text.slice(firstNewline + 1) : '';
	return (
		<Box marginTop={1} flexDirection="column">
			<Text>
				<Text color={theme.colors.illusion}>{theme.icons.assistant}</Text>
				<Text>{' '}{firstLine}</Text>
			</Text>
			{restText ? (
				<Box marginLeft={2} flexDirection="column">
					<MarkdownContent text={restText} />
				</Box>
			) : null}
		</Box>
	);
}

function normalizeTextForCompare(raw: string): string {
	return raw.replace(/\s+/g, ' ').trim();
}

function isTextSubsetOrEqual(a: string, b: string): boolean {
	const normA = normalizeTextForCompare(a);
	const normB = normalizeTextForCompare(b);
	if (!normA || !normB) return false;
	return normA === normB || normA.includes(normB) || normB.includes(normA);
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
