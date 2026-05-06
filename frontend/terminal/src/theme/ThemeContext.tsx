import React, {createContext, useContext} from 'react';

import {type ThemeConfig, defaultTheme} from './builtinThemes.js';

export type {ThemeConfig};

const ThemeContext = createContext<ThemeConfig>(defaultTheme);

export function ThemeProvider({children}: {children: React.ReactNode}): React.JSX.Element {
	return (
		<ThemeContext.Provider value={defaultTheme}>
			{children}
		</ThemeContext.Provider>
	);
}

export function useTheme(): ThemeConfig {
	return useContext(ThemeContext);
}
