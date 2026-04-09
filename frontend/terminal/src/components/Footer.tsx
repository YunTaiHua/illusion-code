import React from 'react';
import {Box, Text} from 'ink';

import {useTheme} from '../theme/ThemeContext.js';

export function Footer({status, taskCount}: {status: Record<string, unknown>; taskCount: number}): React.JSX.Element {
	const {theme} = useTheme();

	return (
		<Box marginTop={1} borderStyle="single" borderColor={theme.colors.muted} paddingX={1}>
			<Text dimColor>
				<Text color={theme.colors.primary}>model</Text>={String(status.model ?? 'unknown')}{' '}
				<Text color={theme.colors.primary}>provider</Text>={String(status.provider ?? 'unknown')}{' '}
				<Text color={theme.colors.primary}>auth</Text>={String(status.auth_status ?? 'unknown')}{' '}
				<Text color={theme.colors.primary}>permission</Text>={String(status.permission_mode ?? 'unknown')}{' '}
				<Text color={theme.colors.primary}>tasks</Text>={String(taskCount)}{' '}
				<Text color={theme.colors.primary}>mcp</Text>={String(status.mcp_connected ?? 0)}/{String(status.mcp_failed ?? 0)}{' '}
				<Text color={theme.colors.primary}>bridge</Text>={String(status.bridge_sessions ?? 0)}{' '}
				<Text color={theme.colors.primary}>language</Text>={String(status.ui_language ?? 'zh-CN')}{' '}
				<Text color={theme.colors.primary}>effort</Text>={String(status.effort ?? 'medium')}{' '}
				<Text color={theme.colors.primary}>passes</Text>={String(status.passes ?? 1)}
			</Text>
		</Box>
	);
}
