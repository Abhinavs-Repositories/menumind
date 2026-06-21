// Theme assembly + provider. Wrap the app in <ThemeProvider> and read tokens
// anywhere via useTheme(). Follows the system light/dark setting.
import {
  createContext,
  useContext,
  useMemo,
  type ReactNode,
} from 'react';
import { useColorScheme, type ViewStyle } from 'react-native';

import { dark, light, type Palette } from './colors';
import { fonts, fontSize, radius, spacing } from './tokens';

export type ThemeMode = 'light' | 'dark';

export type Theme = {
  mode: ThemeMode;
  colors: Palette;
  spacing: typeof spacing;
  radius: typeof radius;
  fonts: typeof fonts;
  fontSize: typeof fontSize;
  /** Elevation presets. Soft shadows in light; near-flat (border-led) in dark. */
  shadow: { card: ViewStyle; float: ViewStyle };
};

function buildShadows(mode: ThemeMode): Theme['shadow'] {
  if (mode === 'dark') {
    // Shadows are invisible on dark surfaces; lean on borders for separation.
    return {
      card: { elevation: 0 },
      float: { elevation: 2 },
    };
  }
  return {
    card: {
      shadowColor: '#000',
      shadowOpacity: 0.06,
      shadowRadius: 8,
      shadowOffset: { width: 0, height: 2 },
      elevation: 2,
    },
    float: {
      shadowColor: '#000',
      shadowOpacity: 0.12,
      shadowRadius: 16,
      shadowOffset: { width: 0, height: 6 },
      elevation: 8,
    },
  };
}

export function buildTheme(mode: ThemeMode): Theme {
  return {
    mode,
    colors: mode === 'dark' ? dark : light,
    spacing,
    radius,
    fonts,
    fontSize,
    shadow: buildShadows(mode),
  };
}

const ThemeContext = createContext<Theme>(buildTheme('light'));

export function ThemeProvider({ children }: { children: ReactNode }) {
  const scheme: ThemeMode = useColorScheme() === 'dark' ? 'dark' : 'light';
  const theme = useMemo(() => buildTheme(scheme), [scheme]);
  return <ThemeContext.Provider value={theme}>{children}</ThemeContext.Provider>;
}

export const useTheme = (): Theme => useContext(ThemeContext);

export type { Palette };
