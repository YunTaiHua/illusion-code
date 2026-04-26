import {useStdout} from 'ink';

export function useTerminalSize(): {columns: number; rows: number} {
	const {stdout} = useStdout();
	return {
		columns: stdout?.columns ?? 80,
		rows: stdout?.rows ?? 24,
	};
}
