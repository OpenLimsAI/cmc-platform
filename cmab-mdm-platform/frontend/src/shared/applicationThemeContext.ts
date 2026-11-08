import { createContext, useContext } from 'react';

export const ApplicationThemeContext = createContext({ dark: false, toggleTheme: () => {} });

export function useApplicationTheme() { return useContext(ApplicationThemeContext); }
