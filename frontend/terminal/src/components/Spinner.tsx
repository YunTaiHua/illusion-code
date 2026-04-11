import React, {useEffect, useMemo, useState} from 'react';
import {Box, Text} from 'ink';

import {useTheme} from '../theme/ThemeContext.js';
import type {TodoItemSnapshot} from '../types.js';

const VERBS = [
	'Thinking',
	'Processing',
	'Analyzing',
	'Reasoning',
	'Working',
	'Computing',
	'Evaluating',
	'Considering',
	'Crafting',
	'Generating',
	'Pondering',
	'Deliberating',
	'Synthesizing',
	'Contemplating',
	'Calculating',
	'Inferring',
	'Orchestrating',
	'Architecting',
	'Iterating',
	'Refining',
];

export function Spinner({label, todoItems}: {label?: string; todoItems?: TodoItemSnapshot[]}): React.JSX.Element {
	const {theme} = useTheme();
	const frames = theme.icons.spinner;
	const [frame, setFrame] = useState(0);
	const [verbIndex, setVerbIndex] = useState(0);

	useEffect(() => {
		const timer = setInterval(() => {
			setFrame((f) => (f + 1) % frames.length);
		}, 220);
		return () => clearInterval(timer);
	}, [frames.length]);

	useEffect(() => {
		const timer = setInterval(() => {
			setVerbIndex((v) => (v + 1) % VERBS.length);
		}, 3000);
		return () => clearInterval(timer);
	}, []);

	// 从todo列表中获取当前in_progress任务的activeForm
	const currentTodo = todoItems?.find((t) => t.status === 'in_progress');
	const nextTodo = todoItems?.find((t) => t.status === 'pending');
	const verb = label ?? (currentTodo?.activeForm ? `${currentTodo.activeForm}...` : `${VERBS[verbIndex]}...`);

	return (
		<Box flexDirection="column">
			<Box>
				<Box width={2}>
					<Text color={theme.colors.illusion}>{frames[frame]}</Text>
				</Box>
				<Text color={theme.colors.muted}>{verb}</Text>
			</Box>
			{nextTodo && !currentTodo ? (
				<Box marginLeft={2}>
					<Text dimColor>Next: {nextTodo.content}</Text>
				</Box>
			) : null}
		</Box>
	);
}
