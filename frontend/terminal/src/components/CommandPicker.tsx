import React from 'react';
import {Box, Text} from 'ink';

import {useTheme} from '../theme/ThemeContext.js';

export function CommandPicker({
	hints,
	selectedIndex,
}: {
	hints: string[];
	selectedIndex: number;
}): React.JSX.Element | null {
	const {theme} = useTheme();

	if (hints.length === 0) {
		return null;
	}

	return (
		<Box flexDirection="column" borderStyle="round" borderColor={theme.colors.accent} paddingX={1} marginBottom={0}>
			<Box marginBottom={1}>
				<Text color={theme.colors.accent} bold>{theme.icons.chevron} Commands</Text>
			</Box>
			{hints.map((hint, i) => {
				const isSelected = i === selectedIndex;
				return (
					<Box key={hint} marginLeft={1}>
						<Text color={isSelected ? theme.colors.accent : theme.colors.muted}>
							{isSelected ? `${theme.icons.chevron} ` : '  '}
						</Text>
						<Text color={isSelected ? theme.colors.accent : undefined} bold={isSelected}>
							{hint}
						</Text>
						{isSelected ? <Text dimColor> [enter]</Text> : null}
					</Box>
				);
			})}
			<Box marginTop={1}>
				<Text dimColor>
					<Text color={theme.colors.muted}>↑↓</Text> navigate
					<Text>  </Text>
					<Text color={theme.colors.muted}>↵</Text> select
					<Text>  </Text>
					<Text color={theme.colors.muted}>esc</Text> dismiss
				</Text>
			</Box>
		</Box>
	);
}
