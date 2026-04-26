import type {Tokens} from 'marked';
import React from 'react';
import {Text} from 'ink';
import {useTerminalSize} from '../hooks/useTerminalSize.js';
import {padAligned, stringWidth, stripAnsi, wrapText} from '../utils/markdown.js';

const SAFETY_MARGIN = 4;
const MIN_COLUMN_WIDTH = 3;
const MAX_ROW_LINES = 4;

type CellData = {text: string; tokens: Array<{text: string}>};

type Props = {
	token: Tokens.Table;
	forceWidth?: number;
};

function cellText(cell: CellData | undefined | null): string {
	return cell?.text ?? '';
}

function cellMinWidth(cell: CellData | undefined | null): number {
	const text = cellText(cell);
	const words = text.split(/\s+/).filter((w) => w.length > 0);
	if (words.length === 0) return MIN_COLUMN_WIDTH;
	return Math.max(...words.map((w) => stringWidth(w)), MIN_COLUMN_WIDTH);
}

function cellIdealWidth(cell: CellData | undefined | null): number {
	return Math.max(stringWidth(cellText(cell)), MIN_COLUMN_WIDTH);
}

export function MarkdownTable({token, forceWidth}: Props): React.JSX.Element {
	const {columns: actualTerminalWidth} = useTerminalSize();
	const terminalWidth = forceWidth ?? actualTerminalWidth;

	const headerCells = token.header as unknown as CellData[];
	const rowsCells = token.rows as unknown as CellData[][];

	const minWidths = headerCells.map((_h, colIndex) => {
		let mw = cellMinWidth(headerCells[colIndex]);
		for (const row of rowsCells) {
			mw = Math.max(mw, cellMinWidth(row[colIndex]));
		}
		return mw;
	});
	const idealWidths = headerCells.map((_h, colIndex) => {
		let iw = cellIdealWidth(headerCells[colIndex]);
		for (const row of rowsCells) {
			iw = Math.max(iw, cellIdealWidth(row[colIndex]));
		}
		return iw;
	});

	const numCols = headerCells.length;
	const borderOverhead = 1 + numCols * 3;
	const availableWidth = Math.max(terminalWidth - borderOverhead - SAFETY_MARGIN, numCols * MIN_COLUMN_WIDTH);

	const totalMin = minWidths.reduce((s, w) => s + w, 0);
	const totalIdeal = idealWidths.reduce((s, w) => s + w, 0);

	let needsHardWrap = false;
	let columnWidths: number[];
	if (totalIdeal <= availableWidth) {
		columnWidths = idealWidths;
	} else if (totalMin <= availableWidth) {
		const extraSpace = availableWidth - totalMin;
		const overflows = idealWidths.map((ideal, i) => ideal - minWidths[i]!);
		const totalOverflow = overflows.reduce((s, o) => s + o, 0);
		columnWidths = minWidths.map((min, i) => {
			if (totalOverflow === 0) return min;
			return min + Math.floor((overflows[i]! / totalOverflow) * extraSpace);
		});
	} else {
		needsHardWrap = true;
		const scaleFactor = availableWidth / totalMin;
		columnWidths = minWidths.map((w) => Math.max(Math.floor(w * scaleFactor), MIN_COLUMN_WIDTH));
	}

	function renderRowLines(cells: Array<CellData | undefined>, isHeader: boolean): string[] {
		const cellLines = cells.map((cell, colIndex) => {
			const text = cellText(cell);
			return wrapText(text, columnWidths[colIndex]!, {hard: needsHardWrap});
		});
		const maxLines = Math.max(...cellLines.map((ls) => ls.length), 1);
		const verticalOffsets = cellLines.map((ls) => Math.floor((maxLines - ls.length) / 2));
		const result: string[] = [];
		for (let lineIdx = 0; lineIdx < maxLines; lineIdx++) {
			let line = '│';
			for (let colIndex = 0; colIndex < cells.length; colIndex++) {
				const ls = cellLines[colIndex]!;
				const offset = verticalOffsets[colIndex]!;
				const cIdx = lineIdx - offset;
				const lineText = cIdx >= 0 && cIdx < ls.length ? ls[cIdx]! : '';
				const width = columnWidths[colIndex]!;
				const align = isHeader ? 'center' : (token.align?.[colIndex] as 'left' | 'center' | 'right' | undefined) ?? 'left';
				const displayW = stringWidth(stripAnsi(lineText));
				line += ' ' + padAligned(lineText, displayW, width, align) + ' │';
			}
			result.push(line);
		}
		return result;
	}

	function renderBorderLine(type: 'top' | 'middle' | 'bottom'): string {
		const [left, mid, cross, right] = {
			top: ['┌', '─', '┬', '┐'],
			middle: ['├', '─', '┼', '┤'],
			bottom: ['└', '─', '┴', '┘'],
		}[type] as [string, string, string, string];
		let line = left;
		columnWidths.forEach((width, colIndex) => {
			line += mid.repeat(width + 2);
			line += colIndex < columnWidths.length - 1 ? cross : right;
		});
		return line;
	}

	function calculateMaxRowLines(): number {
		let maxLines = 1;
		for (let i = 0; i < headerCells.length; i++) {
			const wrapped = wrapText(cellText(headerCells[i]), columnWidths[i]!, {hard: needsHardWrap});
			maxLines = Math.max(maxLines, wrapped.length);
		}
		for (const row of rowsCells) {
			for (let i = 0; i < row.length; i++) {
				const wrapped = wrapText(cellText(row[i]), columnWidths[i]!, {hard: needsHardWrap});
				maxLines = Math.max(maxLines, wrapped.length);
			}
		}
		return maxLines;
	}

	const maxRowLines = calculateMaxRowLines();
	const useVerticalFormat = maxRowLines > MAX_ROW_LINES;

	function renderVerticalFormat(): string {
		const lines: string[] = [];
		const headers = headerCells.map((h) => cellText(h));
		const separator = '─'.repeat(Math.min(terminalWidth - 1, 40));
		rowsCells.forEach((row, rowIndex) => {
			if (rowIndex > 0) lines.push(separator);
			row.forEach((cell, colIndex) => {
				const label = headers[colIndex] ?? `Column ${colIndex + 1}`;
				const value = cellText(cell).replace(/\n+/g, ' ').replace(/\s+/g, ' ').trim();
				const firstLineWidth = Math.max(terminalWidth - stringWidth(label) - 3, 10);
				const wrappedValue = wrapText(value, firstLineWidth);
				lines.push(`${label}: ${wrappedValue[0] ?? ''}`);
				for (let i = 1; i < wrappedValue.length; i++) {
					const l = wrappedValue[i]!;
					if (!l.trim()) return;
					lines.push(`  ${l}`);
				}
			});
		});
		return lines.join('\n');
	}

	if (useVerticalFormat) {
		return <Text>{renderVerticalFormat()}</Text>;
	}

	const tableLines: string[] = [];
	tableLines.push(renderBorderLine('top'));
	tableLines.push(...renderRowLines(headerCells, true));
	tableLines.push(renderBorderLine('middle'));
	rowsCells.forEach((row, rowIndex) => {
		tableLines.push(...renderRowLines(row, false));
		if (rowIndex < rowsCells.length - 1) {
			tableLines.push(renderBorderLine('middle'));
		}
	});
	tableLines.push(renderBorderLine('bottom'));

	const maxLineWidth = Math.max(...tableLines.map((l) => stringWidth(stripAnsi(l))));
	if (maxLineWidth > terminalWidth - SAFETY_MARGIN) {
		return <Text>{renderVerticalFormat()}</Text>;
	}

	return <Text>{tableLines.join('\n')}</Text>;
}
