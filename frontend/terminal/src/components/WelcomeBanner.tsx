import React from 'react';
import {Box, Text} from 'ink';

import {useTheme} from '../theme/ThemeContext.js';

export function WelcomeBanner({language}: {language?: string}): React.JSX.Element {
	const {theme} = useTheme();

	return (
		<Box flexDirection="column" marginBottom={1}>
			<Box flexDirection="column">
				<Text color={theme.colors.illusion}>{' ██ ██      ██      ██    ██ ████████ ██      ██      ██      ██'}</Text>
				<Text color={theme.colors.illusion}>{' ██ ██      ██      ██    ██ ██      ██      ██      ██      ██'}</Text>
				<Text color={theme.colors.illusion}>{' ██ ██      ██      ██    ██ ██████  ██      ██      ██      ██'}</Text>
				<Text color={theme.colors.illusion}>{' ██ ██      ██      ██    ██ ██      ██      ██      ██      ██'}</Text>
				<Text color={theme.colors.illusion}>{' ██ ███████ ███████  ██████  ████████ ███████ ███████ ███████ ██'}</Text>
			</Box>
			<Box marginTop={1}>
				<Text color={theme.colors.illusion} bold>{'  Illusion Code · AI Coding Assistant'}</Text>
			</Box>
			<Box marginTop={1} flexDirection="column">
				<Text dimColor>{`  ${theme.icons.pointer} `}<Text color={theme.colors.suggestion}>/help</Text>{' view all commands'}</Text>
				<Text dimColor>{`  ${theme.icons.pointer} `}<Text color={theme.colors.suggestion}>/model</Text>{' switch model'}</Text>
				<Text dimColor>{`  ${theme.icons.pointer} `}<Text color={theme.colors.suggestion}>/theme</Text>{' switch theme'}</Text>
				<Text dimColor>{`  ${theme.icons.pointer} `}<Text color={theme.colors.suggestion}>/language</Text>{' switch language'}</Text>
			</Box>
		</Box>
	);
}
