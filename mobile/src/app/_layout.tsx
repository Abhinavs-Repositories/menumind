import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { KeyboardProvider } from 'react-native-keyboard-controller';

export default function RootLayout() {
  return (
    <KeyboardProvider>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: '#fff' },
          headerTitleStyle: { fontWeight: '700' },
          headerTintColor: '#c0392b',
        }}
      >
        <Stack.Screen name="index" options={{ title: 'MenuMind' }} />
        <Stack.Screen name="chat" options={{ title: 'Chat' }} />
        <Stack.Screen name="add-menu" options={{ title: 'Add a menu' }} />
      </Stack>
    </KeyboardProvider>
  );
}
