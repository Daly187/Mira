/**
 * SettingsScreen — Mira connection configuration
 *
 * - Desktop IP / Tailscale address for Mira API
 * - Toggle audio capture, location tracking
 * - Shake-to-pause sensitivity
 * - Notification preferences
 */
import React, {useEffect, useState} from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  Switch,
  TouchableOpacity,
  Alert,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import {COLORS, SPACING, FONT_SIZES} from '../utils/theme';

const STORAGE_KEYS = {
  MIRA_HOST: '@mira_host',
  AUDIO_ENABLED: '@audio_enabled',
  LOCATION_ENABLED: '@location_enabled',
  SHAKE_ENABLED: '@shake_enabled',
  NOTIFICATIONS_ENABLED: '@notifications_enabled',
};

const DEFAULT_HOST = '100.64.0.1:8000'; // Tailscale default

const SettingsScreen: React.FC = () => {
  const [host, setHost] = useState(DEFAULT_HOST);
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [locationEnabled, setLocationEnabled] = useState(true);
  const [shakeEnabled, setShakeEnabled] = useState(true);
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const savedHost = await AsyncStorage.getItem(STORAGE_KEYS.MIRA_HOST);
      if (savedHost) setHost(savedHost);

      const audio = await AsyncStorage.getItem(STORAGE_KEYS.AUDIO_ENABLED);
      if (audio !== null) setAudioEnabled(audio === 'true');

      const location = await AsyncStorage.getItem(STORAGE_KEYS.LOCATION_ENABLED);
      if (location !== null) setLocationEnabled(location === 'true');

      const shake = await AsyncStorage.getItem(STORAGE_KEYS.SHAKE_ENABLED);
      if (shake !== null) setShakeEnabled(shake === 'true');

      const notif = await AsyncStorage.getItem(STORAGE_KEYS.NOTIFICATIONS_ENABLED);
      if (notif !== null) setNotificationsEnabled(notif === 'true');
    } catch (err) {
      console.warn('Failed to load settings:', err);
    }
  };

  const saveSetting = async (key: string, value: string) => {
    try {
      await AsyncStorage.setItem(key, value);
    } catch (err) {
      console.warn('Failed to save setting:', err);
    }
  };

  const testConnection = async () => {
    setTesting(true);
    try {
      const response = await fetch(`http://${host}/api/status`, {
        method: 'GET',
        headers: {'Content-Type': 'application/json'},
      });
      if (response.ok) {
        Alert.alert('Connected', `Mira is online at ${host}`);
      } else {
        Alert.alert('Error', `Mira responded with status ${response.status}`);
      }
    } catch (err) {
      Alert.alert(
        'Connection Failed',
        `Could not reach Mira at ${host}.\nMake sure Tailscale is connected.`,
      );
    } finally {
      setTesting(false);
    }
  };

  return (
    <ScrollView style={styles.container}>
      {/* Connection */}
      <Text style={styles.sectionTitle}>Connection</Text>
      <View style={styles.card}>
        <Text style={styles.label}>Mira Desktop Address</Text>
        <Text style={styles.hint}>
          Tailscale IP or hostname of the Windows desktop running Mira
        </Text>
        <TextInput
          style={styles.input}
          value={host}
          onChangeText={text => {
            setHost(text);
            saveSetting(STORAGE_KEYS.MIRA_HOST, text);
          }}
          placeholder="100.64.0.1:8000"
          placeholderTextColor={COLORS.textMuted}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
        />
        <TouchableOpacity
          style={styles.testBtn}
          onPress={testConnection}
          disabled={testing}>
          <Icon name="connection" size={18} color={COLORS.textPrimary} />
          <Text style={styles.testBtnText}>
            {testing ? 'Testing...' : 'Test Connection'}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Capture Settings */}
      <Text style={styles.sectionTitle}>Capture</Text>
      <View style={styles.card}>
        <SettingRow
          icon="microphone"
          label="Audio Capture"
          description="Continuous background audio for voice memos"
          value={audioEnabled}
          onToggle={val => {
            setAudioEnabled(val);
            saveSetting(STORAGE_KEYS.AUDIO_ENABLED, val.toString());
          }}
        />
        <View style={styles.divider} />
        <SettingRow
          icon="map-marker"
          label="Location Tracking"
          description="Passive GPS for context-aware memories"
          value={locationEnabled}
          onToggle={val => {
            setLocationEnabled(val);
            saveSetting(STORAGE_KEYS.LOCATION_ENABLED, val.toString());
          }}
        />
        <View style={styles.divider} />
        <SettingRow
          icon="gesture-swipe"
          label="Shake to Pause"
          description="Shake device to pause all capture"
          value={shakeEnabled}
          onToggle={val => {
            setShakeEnabled(val);
            saveSetting(STORAGE_KEYS.SHAKE_ENABLED, val.toString());
          }}
        />
      </View>

      {/* Notifications */}
      <Text style={styles.sectionTitle}>Notifications</Text>
      <View style={styles.card}>
        <SettingRow
          icon="bell"
          label="Push Notifications"
          description="Receive alerts from Mira"
          value={notificationsEnabled}
          onToggle={val => {
            setNotificationsEnabled(val);
            saveSetting(STORAGE_KEYS.NOTIFICATIONS_ENABLED, val.toString());
          }}
        />
      </View>

      {/* App Info */}
      <Text style={styles.sectionTitle}>About</Text>
      <View style={styles.card}>
        <Text style={styles.aboutText}>Mira Mobile v0.1.0</Text>
        <Text style={styles.aboutSubtext}>
          Autonomous Digital Twin Companion
        </Text>
      </View>

      <View style={{height: SPACING.xl * 2}} />
    </ScrollView>
  );
};

/* ── Sub-component ── */

const SettingRow: React.FC<{
  icon: string;
  label: string;
  description: string;
  value: boolean;
  onToggle: (val: boolean) => void;
}> = ({icon, label, description, value, onToggle}) => (
  <View style={styles.settingRow}>
    <Icon
      name={icon}
      size={22}
      color={COLORS.primaryLight}
      style={{marginRight: SPACING.sm}}
    />
    <View style={{flex: 1}}>
      <Text style={styles.settingLabel}>{label}</Text>
      <Text style={styles.settingDesc}>{description}</Text>
    </View>
    <Switch
      value={value}
      onValueChange={onToggle}
      trackColor={{false: COLORS.border, true: COLORS.primary + '80'}}
      thumbColor={value ? COLORS.primary : COLORS.textMuted}
    />
  </View>
);

/* ── Styles ── */

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.backgroundDark,
    paddingHorizontal: SPACING.md,
  },
  sectionTitle: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.sm,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginTop: SPACING.lg,
    marginBottom: SPACING.sm,
  },
  card: {
    backgroundColor: COLORS.backgroundCard,
    borderRadius: 12,
    padding: SPACING.md,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  label: {
    color: COLORS.textPrimary,
    fontSize: FONT_SIZES.md,
    fontWeight: '600',
    marginBottom: 2,
  },
  hint: {
    color: COLORS.textMuted,
    fontSize: FONT_SIZES.xs,
    marginBottom: SPACING.sm,
  },
  input: {
    backgroundColor: COLORS.backgroundInput,
    borderRadius: 8,
    padding: SPACING.sm + 2,
    color: COLORS.textPrimary,
    fontSize: FONT_SIZES.md,
    borderWidth: 1,
    borderColor: COLORS.border,
    fontFamily: 'monospace',
  },
  testBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: SPACING.xs,
    backgroundColor: COLORS.primary,
    borderRadius: 8,
    paddingVertical: SPACING.sm,
    marginTop: SPACING.sm,
  },
  testBtnText: {
    color: COLORS.textPrimary,
    fontSize: FONT_SIZES.sm,
    fontWeight: '600',
  },

  // Setting rows
  settingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: SPACING.xs,
  },
  settingLabel: {
    color: COLORS.textPrimary,
    fontSize: FONT_SIZES.md,
    fontWeight: '500',
  },
  settingDesc: {
    color: COLORS.textMuted,
    fontSize: FONT_SIZES.xs,
    marginTop: 1,
  },
  divider: {
    height: 1,
    backgroundColor: COLORS.border,
    marginVertical: SPACING.sm,
  },

  // About
  aboutText: {
    color: COLORS.textPrimary,
    fontSize: FONT_SIZES.md,
    fontWeight: '600',
  },
  aboutSubtext: {
    color: COLORS.textMuted,
    fontSize: FONT_SIZES.sm,
    marginTop: 2,
  },
});

export default SettingsScreen;
