import React from 'react';
import {Box, Text} from 'ink';

import {useTheme} from '../theme/ThemeContext.js';

const MAX_VISIBLE = 6;

export function CommandPicker({
	hints,
	selectedIndex,
}: {
	hints: string[];
	selectedIndex: number;
	totalCommands?: number;
}): React.JSX.Element | null {
	const theme = useTheme();

	if (hints.length === 0) {
		return null;
	}

	const startIndex = Math.max(
		0,
		Math.min(
			selectedIndex - Math.floor(MAX_VISIBLE / 2),
			hints.length - MAX_VISIBLE,
		),
	);
	const endIndex = Math.min(startIndex + MAX_VISIBLE, hints.length);
	const visible = hints.slice(startIndex, endIndex);

	return (
		<Box flexDirection="column" marginTop={1}>
			{visible.map((hint, vi) => {
				const actualIndex = startIndex + vi;
				const isSelected = actualIndex === selectedIndex;
				return (
					<Box key={hint}>
						<Text color={isSelected ? theme.colors.suggestion : theme.colors.muted}>
							{isSelected ? `${theme.icons.pointer} ` : '  '}
						</Text>
						<Text color={isSelected ? theme.colors.suggestion : undefined} bold={isSelected} dimColor={!isSelected}>
							{hint}
						</Text>
						{isSelected ? <Text dimColor>{' [enter]'}</Text> : null}
					</Box>
				);
			})}
			<Box marginTop={0}>
				<Text dimColor>
					<Text color={theme.colors.muted}>↑↓</Text> navigate
					<Text> {theme.icons.middleDot} </Text>
					<Text color={theme.colors.muted}>↵</Text> select
					<Text> {theme.icons.middleDot} </Text>
					<Text color={theme.colors.muted}>tab</Text> complete
					<Text> {theme.icons.middleDot} </Text>
					<Text color={theme.colors.muted}>esc</Text> dismiss
				</Text>
			</Box>
		</Box>
	);
}
