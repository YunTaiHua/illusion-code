import React, {useEffect, useState} from 'react';
import {Box, Text} from 'ink';

import {useTheme} from '../theme/ThemeContext.js';
import type {TaskSnapshot} from '../types.js';

const SEP = ' · ';

const WRITE_TOOLS = new Set([
	'Write', 'Edit', 'MultiEdit', 'NotebookEdit',
	'Bash', 'computer', 'str_replace_editor',
]);

function PlanModeIndicator({
	mode,
	activeToolName,
}: {
	mode: string;
	activeToolName?: string;
}): React.JSX.Element | null {
	const {theme} = useTheme();
	const [flash, setFlash] = useState(false);
	const [prevMode, setPrevMode] = useState(mode);

	useEffect(() => {
		if (prevMode === 'plan' && mode !== 'plan' && prevMode !== mode) {
			setFlash(true);
			const timer = setTimeout(() => setFlash(false), 800);
			setPrevMode(mode);
			return () => clearTimeout(timer);
		}
		setPrevMode(mode);
	}, [mode]);

	if (mode !== 'plan' && mode !== 'Plan Mode') {
		if (flash) {
			return (
				<Box marginLeft={1}>
					<Text color={theme.colors.success} bold>
						{' PLAN OFF '}
					</Text>
				</Box>
			);
		}
		return null;
	}

	const isBlockedTool = activeToolName != null && WRITE_TOOLS.has(activeToolName);

	return (
		<Box marginLeft={1}>
			<Text backgroundColor={theme.colors.warning} color={theme.colors.background} bold>
				{' PLAN '}
			</Text>
			{isBlockedTool ? (
				<Box marginLeft={1}>
					<Text color={theme.colors.error}>{theme.icons.cross} </Text>
					<Text color={theme.colors.error} bold>{activeToolName}</Text>
					<Text color={theme.colors.error}> blocked</Text>
				</Box>
			) : null}
		</Box>
	);
}

function AutoModeIndicator(): React.JSX.Element {
	const {theme} = useTheme();
	return (
		<Box marginLeft={1}>
			<Text backgroundColor={theme.colors.success} color={theme.colors.background} bold>
				{' AUTO '}
			</Text>
		</Box>
	);
}

function TokenDisplay({
	inputTokens,
	outputTokens,
	color,
}: {
	inputTokens: number;
	outputTokens: number;
	color: string;
}): React.JSX.Element {
	return (
		<Text color={color}>
			<Text dimColor>{formatNum(inputTokens)}</Text>
			<Text dimColor>↓</Text>
			<Text> </Text>
			<Text dimColor>{formatNum(outputTokens)}</Text>
			<Text dimColor>↑</Text>
		</Text>
	);
}

function TaskIndicator({count}: {count: number}): React.JSX.Element {
	const {theme} = useTheme();
	return (
		<Box>
			<Text color={theme.colors.info}>{theme.icons.inProgress}</Text>
			<Text dimColor> {count} task{count !== 1 ? 's' : ''}</Text>
		</Box>
	);
}

function McpIndicator({count}: {count: number}): React.JSX.Element {
	const {theme} = useTheme();
	return (
		<Box>
			<Text color={theme.colors.permission}>{theme.icons.dot}</Text>
			<Text dimColor> {count} MCP</Text>
		</Box>
	);
}

export function StatusBar({
	status,
	tasks,
	activeToolName,
}: {
	status: Record<string, unknown>;
	tasks: TaskSnapshot[];
	activeToolName?: string;
}): React.JSX.Element {
	const {theme} = useTheme();
	const model = String(status.model ?? 'unknown');
	const mode = String(status.permission_mode ?? 'default');
	const taskCount = tasks.length;
	const mcpCount = Number(status.mcp_connected ?? 0);
	const inputTokens = Number(status.input_tokens ?? 0);
	const outputTokens = Number(status.output_tokens ?? 0);
	const isPlanMode = mode === 'plan' || mode === 'Plan Mode';
	const isAutoMode = mode === 'full_auto' || mode === 'auto';

	return (
		<Box flexDirection="column" marginTop={1}>
			<Box flexDirection="row">
				<Text dimColor>{'─'.repeat(60)}</Text>
			</Box>
			<Box flexDirection="row" alignItems="center">
				<Text color={theme.colors.muted} dimColor>{model}</Text>
				{(inputTokens > 0 || outputTokens > 0) ? (
					<>
						<Text dimColor>{SEP}</Text>
						<TokenDisplay inputTokens={inputTokens} outputTokens={outputTokens} color={theme.colors.muted} />
					</>
				) : null}
				{!isPlanMode && mode !== 'default' ? (
					<>
						<Text dimColor>{SEP}</Text>
						<Text dimColor>{mode}</Text>
					</>
				) : null}
				{taskCount > 0 ? (
					<>
						<Text dimColor>{SEP}</Text>
						<TaskIndicator count={taskCount} />
					</>
				) : null}
				{mcpCount > 0 ? (
					<>
						<Text dimColor>{SEP}</Text>
						<McpIndicator count={mcpCount} />
					</>
				) : null}
				<Box flexGrow={1} />
				{isAutoMode ? <AutoModeIndicator /> : null}
				{isPlanMode ? <PlanModeIndicator mode={mode} activeToolName={activeToolName} /> : null}
			</Box>
		</Box>
	);
}

function formatNum(n: number): string {
	if (n >= 1000000) {
		return `${(n / 1000000).toFixed(1)}M`;
	}
	if (n >= 1000) {
		return `${(n / 1000).toFixed(1)}k`;
	}
	return String(n);
}
