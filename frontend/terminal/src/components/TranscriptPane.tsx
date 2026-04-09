import React from 'react';
import {Box, Text} from 'ink';

import {useTheme} from '../theme/ThemeContext.js';
import type {TranscriptItem} from '../types.js';

const MAX_VISIBLE_ITEMS = 30;

export function TranscriptPane({
	items,
	assistantBuffer,
}: {
	items: TranscriptItem[];
	assistantBuffer: string;
}): React.JSX.Element {
	const {theme} = useTheme();
	const visible = items.slice(-MAX_VISIBLE_ITEMS);

	return (
		<Box flexDirection="column" width="68%" paddingRight={1}>
			<Box marginBottom={1}>
				<Text color={theme.colors.primary} bold>{theme.icons.chevron} Transcript</Text>
			</Box>
			<Box flexDirection="column" borderStyle="round" borderColor={theme.colors.muted} paddingX={1} minHeight={24}>
				{visible.map((item, index) => (
					<Box key={`${index}-${item.role}`} flexDirection="row">
						<Text color={roleColor(item.role, theme)} bold>
							{labelFor(item.role, theme)}{' '}
						</Text>
						<Text color={roleColor(item.role, theme)}>{item.text}</Text>
					</Box>
				))}
				{assistantBuffer ? (
					<Box flexDirection="row">
						<Text color={theme.colors.success} bold>{theme.icons.assistant} </Text>
						<Text color={theme.colors.success}>{assistantBuffer}</Text>
					</Box>
				) : null}
			</Box>
		</Box>
	);
}

function labelFor(role: TranscriptItem['role'], theme: ReturnType<typeof useTheme>['theme']): string {
	switch (role) {
		case 'user':
			return theme.icons.user;
		case 'assistant':
			return theme.icons.assistant;
		case 'tool':
			return theme.icons.tool;
		case 'tool_result':
			return theme.icons.check;
		case 'system':
			return theme.icons.system;
		case 'log':
			return theme.icons.bullet;
		default:
			return theme.icons.dot;
	}
}

function roleColor(role: TranscriptItem['role'], theme: ReturnType<typeof useTheme>['theme']): string {
	switch (role) {
		case 'assistant':
			return theme.colors.success;
		case 'tool':
			return theme.colors.accent;
		case 'tool_result':
			return theme.colors.warning;
		case 'system':
			return theme.colors.info;
		case 'log':
			return theme.colors.muted;
		default:
			return theme.colors.text;
	}
}
