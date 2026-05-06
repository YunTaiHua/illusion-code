import React, {useEffect, useRef, useState} from 'react';
import {Box, Text} from 'ink';

import type {ThemeConfig} from '../theme/ThemeContext.js';
import {useTheme} from '../theme/ThemeContext.js';
import type {TodoItemSnapshot} from '../types.js';

/** 所有任务完成后自动隐藏的延迟时间（毫秒） */
const HIDE_DELAY_MS = 5000;

/** 最近完成任务的高亮时间（毫秒） */
const RECENT_COMPLETED_TTL_MS = 30_000;

export function TodoPanel({items}: {items: TodoItemSnapshot[]}): React.JSX.Element {
	const theme = useTheme();
	const [hidden, setHidden] = useState(false);
	const hideTimerRef = useRef<NodeJS.Timeout | null>(null);
	const completionTimeRef = useRef<Record<string, number>>({});

	if (items.length === 0 || hidden) {
		return <></>;
	}

	const completed = items.filter((t) => t.status === 'completed').length;
	const inProgress = items.filter((t) => t.status === 'in_progress').length;
	const pending = items.filter((t) => t.status === 'pending').length;
	const allDone = completed === items.length && items.length > 0;

	// 跟踪任务完成时间
	const now = Date.now();
	for (const item of items) {
		if (item.status === 'completed' && !(item.content in completionTimeRef.current)) {
			completionTimeRef.current[item.content] = now;
		}
	}

	// 所有任务完成后延迟隐藏
	useEffect(() => {
		if (allDone) {
			if (hideTimerRef.current === null) {
				hideTimerRef.current = setTimeout(() => {
					setHidden(true);
					hideTimerRef.current = null;
				}, HIDE_DELAY_MS);
			}
		} else {
			setHidden(false);
			if (hideTimerRef.current !== null) {
				clearTimeout(hideTimerRef.current);
				hideTimerRef.current = null;
			}
		}
		return () => {
			if (hideTimerRef.current !== null) {
				clearTimeout(hideTimerRef.current);
				hideTimerRef.current = null;
			}
		};
	}, [allDone]);

	// 排序：最近完成 > in_progress > pending > 较早完成
	const sorted = [...items].sort((a, b) => {
		const aRecent = a.status === 'completed' && (now - (completionTimeRef.current[a.content] ?? 0)) < RECENT_COMPLETED_TTL_MS;
		const bRecent = b.status === 'completed' && (now - (completionTimeRef.current[b.content] ?? 0)) < RECENT_COMPLETED_TTL_MS;
		const order = (item: TodoItemSnapshot, isRecent: boolean): number => {
			if (item.status === 'in_progress') return 0;
			if (isRecent) return 1;
			if (item.status === 'pending') return 2;
			return 3;
		};
		return order(a, aRecent) - order(b, bRecent);
	});

	return (
		<Box flexDirection="column" marginTop={1}>
			<Box marginBottom={0}>
				<Text color={theme.colors.illusion} bold>{theme.icons.pointer} </Text>
				<Text bold>Tasks</Text>
				<Text dimColor>{` ${completed}/${items.length} done`}</Text>
				{inProgress > 0 ? <Text color={theme.colors.info}>{` ${theme.icons.middleDot} ${inProgress} active`}</Text> : null}
				{pending > 0 ? <Text dimColor>{` ${theme.icons.middleDot} ${pending} open`}</Text> : null}
			</Box>
			{sorted.map((item, i) => (
				<TodoRow key={i} item={item} theme={theme} now={now} completionTimes={completionTimeRef.current} />
			))}
		</Box>
	);
}

function TodoRow({item, theme, now, completionTimes}: {item: TodoItemSnapshot; theme: ThemeConfig; now: number; completionTimes: Record<string, number>}): React.JSX.Element {
	let icon: string;
	let color: string;

	switch (item.status) {
		case 'completed':
			icon = theme.icons.check;
			color = theme.colors.success;
			break;
		case 'in_progress':
			icon = theme.icons.inProgress;
			color = theme.colors.illusion;
			break;
		default:
			icon = theme.icons.pending;
			color = theme.colors.muted;
			break;
	}

	const isCompleted = item.status === 'completed';
	// 最近完成的任务不高亮（不dim）
	const isRecentCompleted = isCompleted && (now - (completionTimes[item.content] ?? 0)) < RECENT_COMPLETED_TTL_MS;

	return (
		<Box>
			<Text color={color}>{icon} </Text>
			<Text
				color={isCompleted && !isRecentCompleted ? theme.colors.muted : undefined}
				dimColor={isCompleted && !isRecentCompleted}
				strikethrough={isCompleted}
				bold={item.status === 'in_progress'}
			>
				{item.content}
			</Text>
		</Box>
	);
}
