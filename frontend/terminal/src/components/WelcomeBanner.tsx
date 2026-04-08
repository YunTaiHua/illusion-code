import React from 'react';
import {Box, Text} from 'ink';

import {useTheme} from '../theme/ThemeContext.js';

const VERSION = '0.1.0';

export function WelcomeBanner(): React.JSX.Element {
	const {theme} = useTheme();

	return (
		<Box flexDirection="column" marginBottom={1}>
			<Box flexDirection="column" paddingX={1}>
				<Text> </Text>
				<Text color={theme.colors.primary} bold>
					{'  ILLUSION CODE'}
				</Text>
				<Text color={theme.colors.muted}>
					{'  An AI-powered coding assistant v'}{VERSION}
				</Text>
				<Text> </Text>
				<Box flexDirection="row">
					<Text color={theme.colors.muted}>{'  '}</Text>
					<Text color={theme.colors.primary}>/help</Text>
					<Text color={theme.colors.muted}>{' commands  '}</Text>
					<Text color={theme.colors.primary}>/model</Text>
					<Text color={theme.colors.muted}>{' switch  '}</Text>
					<Text color={theme.colors.primary}>Ctrl+C</Text>
					<Text color={theme.colors.muted}>{' exit'}</Text>
				</Box>
				<Text> </Text>
			</Box>
		</Box>
	);
}
