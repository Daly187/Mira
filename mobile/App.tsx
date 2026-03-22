/**
 * Mira Mobile — Main App with bottom tab navigation
 *
 * Three tabs: Home (status), Capture (voice/photo/text), Settings
 * Initialises foreground audio service and location tracking on mount.
 */
import React, {useEffect, useState} from 'react';
import {StatusBar, Platform} from 'react-native';
import {NavigationContainer} from '@react-navigation/native';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

import HomeScreen from './src/screens/HomeScreen';
import CaptureScreen from './src/screens/CaptureScreen';
import SettingsScreen from './src/screens/SettingsScreen';
import AudioService from './src/services/AudioService';
import LocationService from './src/services/LocationService';
import {COLORS} from './src/utils/theme';

const Tab = createBottomTabNavigator();

const TAB_ICONS: Record<string, string> = {
  Home: 'brain',
  Capture: 'microphone-plus',
  Settings: 'cog-outline',
};

const App: React.FC = () => {
  const [audioRunning, setAudioRunning] = useState(false);

  useEffect(() => {
    // Start foreground audio capture service
    AudioService.start()
      .then(() => setAudioRunning(true))
      .catch(err => console.warn('Audio service failed to start:', err));

    // Start passive location tracking
    LocationService.startTracking();

    return () => {
      AudioService.stop();
      LocationService.stopTracking();
    };
  }, []);

  return (
    <>
      <StatusBar
        barStyle="light-content"
        backgroundColor={COLORS.backgroundDark}
      />
      <NavigationContainer>
        <Tab.Navigator
          screenOptions={({route}) => ({
            tabBarIcon: ({color, size}) => (
              <Icon
                name={TAB_ICONS[route.name] ?? 'circle'}
                size={size}
                color={color}
              />
            ),
            tabBarActiveTintColor: COLORS.primary,
            tabBarInactiveTintColor: COLORS.textMuted,
            tabBarStyle: {
              backgroundColor: COLORS.backgroundDark,
              borderTopColor: COLORS.border,
              borderTopWidth: 1,
              paddingBottom: Platform.OS === 'android' ? 4 : 20,
              height: Platform.OS === 'android' ? 60 : 80,
            },
            headerStyle: {
              backgroundColor: COLORS.backgroundDark,
              elevation: 0,
              shadowOpacity: 0,
            },
            headerTintColor: COLORS.textPrimary,
            headerTitleStyle: {fontWeight: '700', fontSize: 18},
          })}>
          <Tab.Screen
            name="Home"
            component={HomeScreen}
            options={{title: 'Mira'}}
          />
          <Tab.Screen
            name="Capture"
            component={CaptureScreen}
            options={{title: 'Capture'}}
          />
          <Tab.Screen
            name="Settings"
            component={SettingsScreen}
            options={{title: 'Settings'}}
          />
        </Tab.Navigator>
      </NavigationContainer>
    </>
  );
};

export default App;
