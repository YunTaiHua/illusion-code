import React from 'react';
import {Box, Text} from 'ink';

import {useTheme} from '../theme/ThemeContext.js';

export type SelectOption = {
	value: string;
	label: string;
	description?: string;
	active?: boolean;
};

export function SelectModal({
	title,
	options,
	selectedIndex,
}: {
	title: string;
	options: SelectOption[];
	selectedIndex: number;
}): React.JSX.Element {
	const {theme} = useTheme();

	return (
		<Box flexDirection="column" marginTop={1}>
			<Box>
				<Text color={theme.colors.permission}>{theme.icons.pointer} </Text>
				<Text bold>{title}</Text>
			</Box>
			{options.map((opt, i) => {
				const isSelected = i === selectedIndex;
				const isCurrent = opt.active;
				return (
					<Box key={opt.value}>
						<Text color={isSelected ? theme.colors.suggestion : theme.colors.muted}>
							{isSelected ? `${theme.icons.pointer} ` : '  '}
						</Text>
						<Text color={isSelected ? theme.colors.suggestion : undefined} bold={isSelected} dimColor={!isSelected}>
							{opt.label}
						</Text>
						{isCurrent ? (
							<Box marginLeft={1}>
								<Text color={theme.colors.success} dimColor>(current)</Text>
							</Box>
						) : null}
						{opt.description ? (
							<Box marginLeft={1}>
								<Text dimColor>{theme.icons.middleDot} {opt.description}</Text>
							</Box>
						) : null}
					</Box>
				);
			})}
			<Box>
				<Text dimColor>
					<Text color={theme.colors.muted}>↑↓</Text> navigate
					<Text> {theme.icons.middleDot} </Text>
					<Text color={theme.colors.muted}>↵</Text> select
					<Text> {theme.icons.middleDot} </Text>
					<Text color={theme.colors.muted}>esc</Text> cancel
				</Text>
			</Box>
		</Box>
	);
}
