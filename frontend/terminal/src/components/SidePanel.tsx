import React from 'react';
import {Box, Text} from 'ink';

import {useTheme} from '../theme/ThemeContext.js';
import type {BridgeSessionSnapshot, McpServerSnapshot, TaskSnapshot} from '../types.js';

export function SidePanel({
	status,
	tasks,
	commands,
	commandHints,
	mcpServers,
	bridgeSessions,
}: {
	status: Record<string, unknown>;
	tasks: TaskSnapshot[];
	commands: string[];
	commandHints: string[];
	mcpServers: McpServerSnapshot[];
	bridgeSessions: BridgeSessionSnapshot[];
}): React.JSX.Element {
	const {theme} = useTheme();

	return (
		<Box flexDirection="column" width="32%">
			<StatusPanel status={status} theme={theme} />
			<TaskPanel tasks={tasks} theme={theme} />
			<McpPanel servers={mcpServers} theme={theme} />
			<BridgePanel sessions={bridgeSessions} theme={theme} />
			<CommandPanel commands={commands} hints={commandHints} theme={theme} />
		</Box>
	);
}

function StatusPanel({status, theme}: {status: Record<string, unknown>; theme: ReturnType<typeof useTheme>['theme']}): React.JSX.Element {
	return (
		<>
			<Box marginBottom={1}>
				<Text color={theme.colors.primary} bold>{theme.icons.chevron} Status</Text>
			</Box>
			<Box flexDirection="column" borderStyle="round" borderColor={theme.colors.muted} paddingX={1} marginBottom={1}>
				<Text><Text dimColor>model:</Text> <Text color={theme.colors.accent}>{String(status.model ?? 'unknown')}</Text></Text>
				<Text><Text dimColor>provider:</Text> <Text color={theme.colors.accent}>{String(status.provider ?? 'unknown')}</Text></Text>
				<Text><Text dimColor>auth:</Text> <Text color={theme.colors.accent}>{String(status.auth_status ?? 'unknown')}</Text></Text>
				<Text><Text dimColor>permission:</Text> <Text color={theme.colors.accent}>{String(status.permission_mode ?? 'unknown')}</Text></Text>
				<Text><Text dimColor>cwd:</Text> <Text color={theme.colors.accent}>{String(status.cwd ?? '.')}</Text></Text>
				<Text><Text dimColor>language:</Text> <Text color={theme.colors.accent}>{String(status.ui_language ?? 'zh-CN')}</Text></Text>
				<Text><Text dimColor>fast:</Text> <Text color={theme.colors.accent}>{String(Boolean(status.fast_mode))}</Text></Text>
				<Text><Text dimColor>effort:</Text> <Text color={theme.colors.accent}>{String(status.effort ?? 'medium')}</Text></Text>
				<Text><Text dimColor>passes:</Text> <Text color={theme.colors.accent}>{String(status.passes ?? 1)}</Text></Text>
			</Box>
		</>
	);
}

function TaskPanel({tasks, theme}: {tasks: TaskSnapshot[]; theme: ReturnType<typeof useTheme>['theme']}): React.JSX.Element {
	const visible = tasks.slice(0, 6);
	return (
		<>
			<Box marginBottom={1}>
				<Text color={theme.colors.primary} bold>{theme.icons.chevron} Tasks</Text>
			</Box>
			<Box flexDirection="column" borderStyle="round" borderColor={theme.colors.muted} paddingX={1} marginBottom={1}>
				{visible.length === 0 ? (
					<Text dimColor>(none)</Text>
				) : (
					visible.map((task) => (
						<Box key={task.id} flexDirection="column" marginBottom={1}>
							<Text>
								<Text color={theme.colors.accent}>{task.id}</Text>
								<Text dimColor> [{task.status}] </Text>
								<Text>{task.description}</Text>
							</Text>
							<Text dimColor>
								type={task.type} progress={task.metadata.progress ?? '-'} note={task.metadata.status_note ?? '-'}
							</Text>
						</Box>
					))
				)}
			</Box>
		</>
	);
}

function McpPanel({servers, theme}: {servers: McpServerSnapshot[]; theme: ReturnType<typeof useTheme>['theme']}): React.JSX.Element {
	return (
		<>
			<Box marginBottom={1}>
				<Text color={theme.colors.primary} bold>{theme.icons.chevron} MCP</Text>
			</Box>
			<Box flexDirection="column" borderStyle="round" borderColor={theme.colors.muted} paddingX={1} marginBottom={1}>
				{servers.length === 0 ? (
					<Text dimColor>(none)</Text>
				) : (
					servers.slice(0, 5).map((server) => (
						<Box key={server.name} flexDirection="column" marginBottom={1}>
							<Text>
								<Text color={theme.colors.accent}>{server.name}</Text>
								<Text dimColor> [{server.state}] </Text>
								<Text>{server.transport ?? 'unknown'}</Text>
							</Text>
							<Text dimColor>
								auth={String(Boolean(server.auth_configured))} tools={String(server.tool_count ?? 0)} resources=
								{String(server.resource_count ?? 0)}
							</Text>
							{server.detail ? <Text dimColor>{server.detail}</Text> : null}
						</Box>
					))
				)}
			</Box>
		</>
	);
}

function BridgePanel({sessions, theme}: {sessions: BridgeSessionSnapshot[]; theme: ReturnType<typeof useTheme>['theme']}): React.JSX.Element {
	return (
		<>
			<Box marginBottom={1}>
				<Text color={theme.colors.primary} bold>{theme.icons.chevron} Bridge</Text>
			</Box>
			<Box flexDirection="column" borderStyle="round" borderColor={theme.colors.muted} paddingX={1} marginBottom={1}>
				{sessions.length === 0 ? (
					<Text dimColor>(none)</Text>
				) : (
					sessions.slice(0, 4).map((session) => (
						<Box key={session.session_id} flexDirection="column" marginBottom={1}>
							<Text>
								<Text color={theme.colors.accent}>{session.session_id}</Text>
								<Text dimColor> [{session.status}] pid={session.pid}</Text>
							</Text>
							<Text dimColor>{session.command}</Text>
						</Box>
					))
				)}
			</Box>
		</>
	);
}

function CommandPanel({
	commands,
	hints,
	theme,
}: {
	commands: string[];
	hints: string[];
	theme: ReturnType<typeof useTheme>['theme'];
}): React.JSX.Element {
	return (
		<>
			<Box marginBottom={1}>
				<Text color={theme.colors.primary} bold>{theme.icons.chevron} Commands</Text>
			</Box>
			<Box flexDirection="column" borderStyle="round" borderColor={theme.colors.muted} paddingX={1}>
				{hints.length > 0 ? (
					hints.map((command, index) => (
						<Text key={command} color={index === 0 ? theme.colors.accent : theme.colors.text}>
							{command}
							{index === 0 ? <Text dimColor>  [tab]</Text> : ''}
						</Text>
					))
				) : commands.length > 0 ? (
					<Text dimColor>type / for commands</Text>
				) : (
					<Text dimColor>(none)</Text>
				)}
			</Box>
		</>
	);
}
