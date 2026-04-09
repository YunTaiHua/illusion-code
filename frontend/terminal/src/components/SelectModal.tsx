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
		<Box flexDirection="column" marginTop={1} borderStyle="round" borderColor={theme.colors.accent} paddingX={1}>
			<Box marginBottom={1}>
				<Text color={theme.colors.accent} bold>{theme.icons.chevron} {title}</Text>
			</Box>
			{options.map((opt, i) => {
				const isSelected = i === selectedIndex;
				const isCurrent = opt.active;
				return (
					<Box key={opt.value} flexDirection="row" marginLeft={1}>
						<Text color={isSelected ? theme.colors.accent : theme.colors.muted}>
							{isSelected ? `${theme.icons.chevron} ` : '  '}
						</Text>
						<Text color={isSelected ? theme.colors.accent : undefined} bold={isSelected}>
							{opt.label}
						</Text>
						{isCurrent ? (
							<Box marginLeft={1}>
								<Text color={theme.colors.success} dimColor>(current)</Text>
							</Box>
						) : null}
						{opt.description ? (
							<Box marginLeft={1}>
								<Text dimColor>{opt.description}</Text>
							</Box>
						) : null}
					</Box>
				);
			})}
			<Box marginTop={1}>
				<Text dimColor>
					<Text color={theme.colors.muted}>↑↓</Text> navigate
					<Text>  </Text>
					<Text color={theme.colors.muted}>↵</Text> select
					<Text>  </Text>
					<Text color={theme.colors.muted}>esc</Text> cancel
				</Text>
			</Box>
		</Box>
	);
}
