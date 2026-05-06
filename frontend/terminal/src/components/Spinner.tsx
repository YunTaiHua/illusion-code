import React, {useEffect, useMemo, useState} from 'react';
import {Box, Text} from 'ink';

import type {UiLanguage} from '../i18n.js';
import {t} from '../i18n.js';
import {useTheme} from '../theme/ThemeContext.js';
import type {TodoItemSnapshot} from '../types.js';

export function Spinner({label, todoItems, language, toolName}: {label?: string; todoItems?: TodoItemSnapshot[]; language?: UiLanguage; toolName?: string}): React.JSX.Element {
	const theme = useTheme();
	const frames = theme.icons.spinner;
	const [frame, setFrame] = useState(0);
	const [verbIndex, setVerbIndex] = useState(0);

	// 从 i18n 获取动词列表
	const verbs = useMemo(() => {
		if (!language) return ['Thinking'];
		return t(language, 'spinnerVerbs').split(',');
	}, [language]);

	useEffect(() => {
		const timer = setInterval(() => {
			setFrame((f) => (f + 1) % frames.length);
		}, 220);
		return () => clearInterval(timer);
	}, [frames.length]);

	useEffect(() => {
		const timer = setInterval(() => {
			setVerbIndex((v) => (v + 1) % verbs.length);
		}, 3000);
		return () => clearInterval(timer);
	}, [verbs.length]);

	// 从todo列表中获取当前in_progress任务的activeForm
	const currentTodo = todoItems?.find((t) => t.status === 'in_progress');
	const nextTodo = todoItems?.find((t) => t.status === 'pending');

	// 构建显示文本：优先使用 label，其次使用 todo activeForm，再次使用工具名，最后轮换动词
	const displayText = label ?? (currentTodo?.activeForm
		? `${currentTodo.activeForm}...`
		: toolName && language
			? `${t(language, 'spinnerToolAction')} ${toolName}...`
			: `${verbs[verbIndex]}...`);

	return (
		<Box flexDirection="column">
			<Box>
				<Box width={3}>
					<Text color={theme.colors.illusion}>{frames[frame]}</Text>
				</Box>
				<Text color={theme.colors.illusionShimmer}>{displayText}</Text>
			</Box>
			{nextTodo && !currentTodo ? (
				<Box marginTop={1} marginLeft={3}>
					<Text dimColor>Next: {nextTodo.content}</Text>
				</Box>
			) : null}
		</Box>
	);
}
