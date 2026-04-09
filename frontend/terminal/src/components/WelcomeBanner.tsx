import React from 'react';
import {Box, Text} from 'ink';

import type {UiLanguage} from '../i18n.js';
import {t} from '../i18n.js';
import {useTheme} from '../theme/ThemeContext.js';

const VERSION = '0.1.0';

export function WelcomeBanner({language}: {language: UiLanguage}): React.JSX.Element {
	const {theme} = useTheme();

	return (
		<Box flexDirection="column" marginBottom={1}>
			<Box flexDirection="column" paddingX={1}>
				<Text> </Text>
				<Text color={theme.colors.primary} bold>{'  ___ _     _    _   _ ____ ___ ___  _   _ '}</Text>
				<Text color={theme.colors.primary} bold>{' |_ _| |   | |  | | | / ___|_ _/ _ \| \ | |'}</Text>
				<Text color={theme.colors.primary} bold>{'  | || |   | |  | | | \___ \| | | | |  \| |'}</Text>
				<Text color={theme.colors.primary} bold>{'  | || |___| |__| |_| |___) | | |_| | |\  |'}</Text>
				<Text color={theme.colors.primary} bold>{' |___|_____|_____\___/|____/___\___/|_| \_|'}</Text>
				<Text color={theme.colors.primary} bold>{'   ____ ___  ____  _____ '}</Text>
				<Text color={theme.colors.primary} bold>{'  / ___/ _ \|  _ \| ____|'}</Text>
				<Text color={theme.colors.primary} bold>{' | |  | | | | | | |  _|  '}</Text>
				<Text color={theme.colors.primary} bold>{' | |__| |_| | |_| | |___ '}</Text>
				<Text color={theme.colors.primary} bold>{'  \____\___/|____/|_____|'}</Text>
				<Text color={theme.colors.muted}>
					{'  '}{t(language, 'welcomeSub')}{' v'}{VERSION}
				</Text>
				<Text> </Text>
				<Box flexDirection="row">
					<Text color={theme.colors.muted}>{'  '}</Text>
					<Text color={theme.colors.primary}>/help</Text>
					<Text color={theme.colors.muted}>{` ${t(language, 'commands')}  `}</Text>
					<Text color={theme.colors.primary}>/language</Text>
					<Text color={theme.colors.muted}>{' switch  '}</Text>
					<Text color={theme.colors.primary}>/model</Text>
					<Text color={theme.colors.muted}>{' switch  '}</Text>
					<Text color={theme.colors.primary}>Ctrl+C</Text>
					<Text color={theme.colors.muted}>{` ${t(language, 'exit')}`}</Text>
				</Box>
				<Text> </Text>
			</Box>
		</Box>
	);
}
