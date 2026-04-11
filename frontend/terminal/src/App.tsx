import React, {useEffect, useMemo, useState} from 'react';
import {Box, Text, useApp, useInput} from 'ink';

import {ComposerController} from './components/ComposerController.js';
import {ConversationView} from './components/ConversationView.js';
import {ModalHost} from './components/ModalHost.js';
import {SelectModal, type SelectOption} from './components/SelectModal.js';
import {StatusBar} from './components/StatusBar.js';
import {SwarmPanel} from './components/SwarmPanel.js';
import {TodoPanel} from './components/TodoPanel.js';
import {useBackendSession} from './hooks/useBackendSession.js';
import {normalizeLanguage, t} from './i18n.js';
import {ThemeProvider, useTheme} from './theme/ThemeContext.js';
import type {FrontendConfig} from './types.js';

const rawReturnSubmit = process.env.ILLUSION_FRONTEND_RAW_RETURN === '1';
const scriptedSteps = (() => {
	const raw = process.env.ILLUSION_FRONTEND_SCRIPT;
	if (!raw) {
		return [] as string[];
	}
	try {
		const parsed = JSON.parse(raw);
		return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string') : [];
	} catch {
		return [];
	}
})();

const PERMISSION_MODES: SelectOption[] = [
	{value: 'default', label: 'Default', description: 'Ask before write/execute operations'},
	{value: 'full_auto', label: 'Auto', description: 'Allow all tools automatically'},
	{value: 'plan', label: 'Plan Mode', description: 'Block all write operations'},
];

type SelectModalState = {
	title: string;
	options: SelectOption[];
	onSelect: (value: string) => void;
} | null;

const PERMISSION_PROMPT_OPTIONS: SelectOption[] = [
	{value: 'allow', label: 'Allow', description: 'Approve this tool execution'},
	{value: 'always', label: 'Always Allow', description: 'Always allow this tool without asking again'},
	{value: 'deny', label: 'Deny', description: 'Reject this tool execution'},
];

export function App({config}: {config: FrontendConfig}): React.JSX.Element {
	const initialTheme = String((config as Record<string, unknown>).theme ?? 'default');
	return (
		<ThemeProvider initialTheme={initialTheme}>
			<AppInner config={config} />
		</ThemeProvider>
	);
}

function AppInner({config}: {config: FrontendConfig}): React.JSX.Element {
	const {exit} = useApp();
	const {theme, setThemeName} = useTheme();
	const [modalInput, setModalInput] = useState('');
	const [scriptIndex, setScriptIndex] = useState(0);
	const [selectModal, setSelectModal] = useState<SelectModalState>(null);
	const [selectIndex, setSelectIndex] = useState(0);
	const [permissionIndex, setPermissionIndex] = useState(2);
	const [pendingPermissionAck, setPendingPermissionAck] = useState(false);
	const [showThinking, setShowThinking] = useState(false);
	const session = useBackendSession(config, () => exit());
	const isPermissionModal = session.modal?.kind === 'permission';
	const language = normalizeLanguage(session.status.ui_language);
	const permissionRequestId =
		isPermissionModal && typeof session.modal?.request_id === 'string' ? String(session.modal.request_id) : '';
	const localizedPermissionOptions = PERMISSION_PROMPT_OPTIONS.map((opt) => {
		if (opt.value === 'allow') {
			return {...opt, label: t(language, 'allow')};
		}
		if (opt.value === 'always') {
			return {...opt, label: t(language, 'alwaysAllow')};
		}
		return {...opt, label: t(language, 'deny')};
	});

	// Current tool name for spinner
	const currentToolName = useMemo(() => {
		for (let i = session.transcript.length - 1; i >= 0; i--) {
			const item = session.transcript[i];
			if (item.role === 'tool') {
				return item.tool_name ?? 'tool';
			}
			if (item.role === 'tool_result' || item.role === 'assistant') {
				break;
			}
		}
		return undefined;
	}, [session.transcript]);

	const showComposer = session.ready && !session.modal && !selectModal && !pendingPermissionAck;

	const conversationNode = useMemo(
		() => (
			<ConversationView
				items={session.transcript}
				assistantBuffer={session.assistantBuffer}
				showWelcome={session.ready}
				language={language}
				showThinking={showThinking}
			/>
		),
		[language, session.assistantBuffer, session.ready, session.transcript, showThinking]
	);

	const todoNode = useMemo(() => {
		if (!session.ready || session.todoItems.length === 0) {
			return null;
		}
		return <TodoPanel items={session.todoItems} />;
	}, [session.ready, session.todoItems]);

	const swarmNode = useMemo(() => {
		if (!session.ready || (session.swarmTeammates.length === 0 && session.swarmNotifications.length === 0)) {
			return null;
		}
		return <SwarmPanel teammates={session.swarmTeammates} notifications={session.swarmNotifications} />;
	}, [session.ready, session.swarmNotifications, session.swarmTeammates]);

	const statusNode = useMemo(() => {
		if (!session.ready) {
			return null;
		}
		return <StatusBar status={session.status} tasks={session.tasks} activeToolName={session.busy ? currentToolName : undefined} />;
	}, [currentToolName, session.busy, session.ready, session.status, session.tasks]);

	// Handle backend-initiated select requests (e.g. /resume session list)
	useEffect(() => {
		if (!session.selectRequest) {
			return;
		}
		const req = session.selectRequest;
		if (req.options.length === 0) {
			session.setSelectRequest(null);
			return;
		}
		setSelectIndex(0);
		setSelectModal({
			title: req.title,
			options: req.options.map((o) => ({value: o.value, label: o.label, description: o.description})),
			onSelect: (value) => {
				session.sendRequest({type: 'apply_select_command', command: req.command, value});
				session.setBusy(true);
				setSelectModal(null);
			},
		});
		session.setSelectRequest(null);
	}, [session.selectRequest]);

	useEffect(() => {
		if (!isPermissionModal) {
			setPendingPermissionAck(false);
			return;
		}
		setPermissionIndex(1);
		setPendingPermissionAck(false);
	}, [permissionRequestId, isPermissionModal]);

	// Intercept special commands that need interactive UI
	const handleCommand = (cmd: string): boolean => {
		const trimmed = cmd.trim();

		// /theme set <name> → switch theme locally
		const themeMatch = /^\/theme\s+set\s+(\S+)$/.exec(trimmed);
		if (themeMatch) {
			setThemeName(themeMatch[1]);
			return true;
		}

		// /permissions → show mode picker
		if (trimmed === '/permissions' || trimmed === '/permissions show') {
			const currentMode = String(session.status.permission_mode ?? 'default');
			const options = PERMISSION_MODES.map((opt) => ({
				...opt,
				active: opt.value === currentMode,
			}));
			const initialIndex = options.findIndex((o) => o.active);
			setSelectIndex(initialIndex >= 0 ? initialIndex : 0);
			setSelectModal({
				title: 'Permission Mode',
				options,
				onSelect: (value) => {
					session.sendRequest({type: 'submit_line', line: `/permissions set ${value}`});
					session.setBusy(true);
					setSelectModal(null);
				},
			});
			return true;
		}

		if (trimmed === '/language' || trimmed === '/language show') {
			const current = normalizeLanguage(session.status.ui_language);
			const options: SelectOption[] = [
				{value: 'set zh-CN', label: t(current, 'langZh'), description: '中文界面', active: current === 'zh-CN'},
				{value: 'set en', label: t(current, 'langEn'), description: 'English UI', active: current === 'en'},
			];
			const initialIndex = options.findIndex((o) => o.active);
			setSelectIndex(initialIndex >= 0 ? initialIndex : 0);
			setSelectModal({
				title: t(current, 'language'),
				options,
				onSelect: (value) => {
					session.sendRequest({type: 'submit_line', line: `/language ${value}`});
					session.setBusy(true);
					setSelectModal(null);
				},
			});
			return true;
		}

		// /plan → toggle plan mode
		if (trimmed === '/plan') {
			const currentMode = String(session.status.permission_mode ?? 'default');
			if (currentMode === 'plan') {
				session.sendRequest({type: 'submit_line', line: '/plan off'});
			} else {
				session.sendRequest({type: 'submit_line', line: '/plan on'});
			}
			session.setBusy(true);
			return true;
		}

		// /resume → request session list from backend (will trigger select_request)
		if (trimmed === '/resume') {
			session.sendRequest({type: 'list_sessions'});
			return true;
		}

		return false;
	};

	useInput((chunk, key) => {
		// Ctrl+C → 如果正在执行任务则停止，否则退出
		if (key.ctrl && chunk === 'c') {
			if (session.busy) {
				session.sendRequest({type: 'stop'});
				return;
			}
			session.sendRequest({type: 'shutdown'});
			exit();
			return;
		}
		// Ctrl+X → 停止当前任务（与busy时的Ctrl+C等效）
		if (key.ctrl && chunk.toLowerCase() === 'x') {
			session.sendRequest({type: 'stop'});
			return;
		}
		if (key.ctrl && chunk.toLowerCase() === 't') {
			setShowThinking((value) => !value);
			return;
		}


		// --- Select modal (permissions picker etc.) ---
		if (selectModal) {
			if (key.upArrow) {
				setSelectIndex((i) => Math.max(0, i - 1));
				return;
			}
			if (key.downArrow) {
				setSelectIndex((i) => Math.min(selectModal.options.length - 1, i + 1));
				return;
			}
			if (key.return) {
				const selected = selectModal.options[selectIndex];
				if (selected) {
					selectModal.onSelect(selected.value);
				}
				return;
			}
			if (key.escape) {
				setSelectModal(null);
				return;
			}
			// Number keys for quick selection
			const num = parseInt(chunk, 10);
			if (num >= 1 && num <= selectModal.options.length) {
				const selected = selectModal.options[num - 1];
				if (selected) {
					selectModal.onSelect(selected.value);
				}
				return;
			}
			return;
		}

		// --- Scripted raw return (question modal only) ---
		if (rawReturnSubmit && key.return && session.modal?.kind === 'question') {
			session.sendRequest({
				type: 'question_response',
				request_id: session.modal.request_id,
				answer: modalInput,
			});
			session.setModal(null);
			setModalInput('');
			return;
		}

		// --- Permission modal (MUST be before busy check — modal appears while busy) ---
		if (isPermissionModal) {
			if (pendingPermissionAck) {
				return;
			}
			if (key.upArrow || key.downArrow) {
				setPermissionIndex((i) => {
					if (key.upArrow) return i <= 0 ? 2 : i - 1;
					return i >= 2 ? 0 : i + 1;
				});
				return;
			}
			if (key.return || key.escape) {
				if (!permissionRequestId) {
					return;
				}
				const selected = key.escape ? 'deny' : localizedPermissionOptions[permissionIndex]?.value;
				const allowed = selected === 'allow' || selected === 'always';
				session.sendRequest({
					type: 'permission_response',
					request_id: permissionRequestId,
					allowed,
					always_allow: selected === 'always',
					tool_name: String(session.modal?.tool_name ?? ''),
				});
				setPendingPermissionAck(true);
				return;
			}
			return;
		}

		// --- Question modal (also appears while busy) ---
		if (session.modal?.kind === 'question') {
			return;
		}

		// --- Ignore input while busy ---
		if (session.busy) {
			return;
		}

	});

	const onSubmit = (value: string): void => {
		const trimmed = value.trim();
		if (session.modal?.kind === 'question') {
			session.sendRequest({
				type: 'question_response',
				request_id: session.modal.request_id,
				answer: trimmed,
			});
			session.setModal(null);
			setModalInput('');
			return;
		}
		if (!trimmed || session.busy || !session.ready) {
			return;
		}
		// Check if it's an interactive command
		if (handleCommand(trimmed)) {
			return;
		}
		session.sendRequest({type: 'submit_line', line: trimmed});
		session.setBusy(true);
	};

	// Scripted automation
	useEffect(() => {
		if (scriptIndex >= scriptedSteps.length) {
			return;
		}
		if (session.busy || session.modal || selectModal) {
			return;
		}
		const step = scriptedSteps[scriptIndex];
		const timer = setTimeout(() => {
			onSubmit(step);
			setScriptIndex((index) => index + 1);
		}, 200);
		return () => clearTimeout(timer);
	}, [scriptIndex, session.busy, session.modal, selectModal]);

	return (
		<Box flexDirection="column" paddingX={1} height="100%">
			{/* Conversation area — overflow:hidden + flexShrink prevent Ink output
			    from exceeding terminal height, which causes cursor-up to scroll
			    the viewport (frame alternation + scrollbar jumping). */}
			<Box flexDirection="column" flexGrow={1} flexShrink={1} overflow="hidden">
				{conversationNode}
			</Box>

			{/* Permission confirm modal */}
			{isPermissionModal ? (
				<SelectModal
					title={`Allow ${String(session.modal?.tool_name ?? 'tool')}?`}
					options={localizedPermissionOptions}
					selectedIndex={permissionIndex}
				/>
			) : null}

			{/* Backend modal (question, mcp auth) */}
			{session.modal && !isPermissionModal ? (
				<ModalHost
					modal={session.modal}
					modalInput={modalInput}
					setModalInput={setModalInput}
					onSubmit={onSubmit}
					language={language}
				/>
			) : null}

			{/* Frontend select modal (permissions picker, etc.) */}
			{selectModal ? (
				<SelectModal
					title={selectModal.title}
					options={selectModal.options}
					selectedIndex={selectIndex}
				/>
			) : null}

			{/* Todo panel */}
			{todoNode}

			{/* Swarm panel */}
			{swarmNode}

			{/* Status bar (only after backend is ready) */}
			{statusNode}

			{/* Input — show loading indicator until backend is ready */}
			{!session.ready ? (
				<Box>
					<Text color={theme.colors.warning}>{t(language, 'connecting')}</Text>
				</Box>
			) : showComposer ? (
				<ComposerController
					commands={session.commands}
					busy={session.busy}
					disabled={Boolean(session.modal || selectModal || pendingPermissionAck)}
					language={language}
					todoItems={session.todoItems}
					toolName={session.busy ? currentToolName : undefined}
					onSubmit={onSubmit}
				/>
			) : null}

			{/* Keyboard hints (only after backend is ready) */}
			{session.ready && !session.modal && !session.busy && !selectModal && !pendingPermissionAck ? (
				<Box>
					<Text dimColor>
						<Text color={theme.colors.muted}>enter</Text> {t(language, 'send')}
						<Text> {theme.icons.middleDot} </Text>
						<Text color={theme.colors.muted}>/</Text> {t(language, 'commands')}
						<Text> {theme.icons.middleDot} </Text>
						<Text color={theme.colors.muted}>ctrl+t</Text> {showThinking ? t(language, 'hideThinking') : t(language, 'showThinking')}
						<Text> {theme.icons.middleDot} </Text>
						<Text color={theme.colors.muted}>ctrl+c</Text> {t(language, 'exit')}
					</Text>
				</Box>
			) : session.ready && session.busy && !session.modal && !selectModal ? (
				<Box>
					<Text dimColor>
						<Text color={theme.colors.muted}>ctrl+c</Text> {t(language, 'exit')}
						<Text> {theme.icons.middleDot} </Text>
						<Text color={theme.colors.muted}>ctrl+x</Text> {t(language, 'stopTask')}
						<Text> {theme.icons.middleDot} </Text>
						<Text color={theme.colors.muted}>ctrl+t</Text> {showThinking ? t(language, 'hideThinking') : t(language, 'showThinking')}
					</Text>
				</Box>
			) : null}
		</Box>
	);
}
