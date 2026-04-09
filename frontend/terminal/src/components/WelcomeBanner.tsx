import React from 'react';
import {Box, Text} from 'ink';

import type {UiLanguage} from '../i18n.js';
import {useTheme} from '../theme/ThemeContext.js';

export function WelcomeBanner({language}: {language: UiLanguage}): React.JSX.Element {
	const {theme} = useTheme();

	const welcomeText = language === 'zh-CN' ? '欢迎使用 Illusion Code' : 'Welcome to Illusion Code';
	const helpText = language === 'zh-CN'
		? '输入 /help 查看命令列表，或开始输入您的请求'
		: 'Type /help for commands or start typing your request';

	return (
		<Box flexDirection="column" borderStyle="double" borderColor={theme.colors.primary} paddingX={2} paddingY={1} marginBottom={1}>
			<Box>
				<Text color={theme.colors.primary} bold>
					{theme.icons.chevron}{' '}
				</Text>
				<Text color={theme.colors.primary} bold>
					{welcomeText}
				</Text>
			</Box>
			<Box marginTop={1}>
				<Text color={theme.colors.muted}>{helpText}</Text>
			</Box>
			<Box marginTop={1}>
				<Text dimColor>
					<Text color={theme.colors.accent}>model</Text> /model set {'<name>'}{' '}
					<Text color={theme.colors.accent}>theme</Text> /theme set {'<name>'}{' '}
					<Text color={theme.colors.accent}>lang</Text> /lang set zh-CN|en-US
				</Text>
			</Box>
		</Box>
	);
}
