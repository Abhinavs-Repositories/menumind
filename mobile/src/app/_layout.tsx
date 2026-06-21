import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { KeyboardProvider } from 'react-native-keyboard-controller';

import { ThemeProvider, useTheme } from '@/theme';

function Navigator() {
  const t = useTheme();
  return (
    <>
      <StatusBar style={t.mode === 'dark' ? 'light' : 'dark'} />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: t.colors.surface },
          headerTitleStyle: {
            fontFamily: t.fonts.display,
            fontWeight: '700',
            color: t.colors.text,
          },
          headerTintColor: t.colors.brand,
          headerShadowVisible: false,
          contentStyle: { backgroundColor: t.colors.bg },
        }}
      >
        <Stack.Screen name="index" options={{ title: 'MenuMind' }} />
        <Stack.Screen name="chat" options={{ title: 'Chat' }} />
        <Stack.Screen name="add-menu" options={{ title: 'Add a menu' }} />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <KeyboardProvider>
        <ThemeProvider>
          <Navigator />
        </ThemeProvider>
      </KeyboardProvider>
    </GestureHandlerRootView>
  );
}
