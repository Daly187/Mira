/**
 * NotificationService — Push notification handling for Mira alerts.
 *
 * Receives push notifications from the Mira desktop agent and displays
 * them as Android notifications. Also registers the device token with
 * the Mira API so the agent can send targeted pushes.
 */
import PushNotification, {
  ReceivedNotification,
} from 'react-native-push-notification';
import MiraApi from './MiraApi';

const CHANNEL_ID_ALERTS = 'mira_alerts';
const CHANNEL_ID_ACTIONS = 'mira_actions';

class NotificationServiceManager {
  private configured = false;

  /**
   * Must be called once at app startup (before AppRegistry).
   */
  configure(): void {
    if (this.configured) return;

    PushNotification.configure({
      // Called when a remote or local notification is opened or received
      onNotification: (notification: ReceivedNotification) => {
        console.log('Notification received:', notification);
        this.handleNotification(notification);
      },

      // Called when the device registers for push
      onRegister: (tokenData: {token: string}) => {
        console.log('Push token:', tokenData.token);
        // Register with Mira backend so it can send us notifications
        MiraApi.registerPushToken(tokenData.token).catch(err =>
          console.warn('Failed to register push token:', err),
        );
      },

      // Android-specific settings
      popInitialNotification: true,
      requestPermissions: true,
    });

    // Create notification channels (Android 8+)
    PushNotification.createChannel(
      {
        channelId: CHANNEL_ID_ALERTS,
        channelName: 'Mira Alerts',
        channelDescription: 'Important alerts from Mira',
        importance: 4, // HIGH
        vibrate: true,
        playSound: true,
      },
      (created: boolean) =>
        console.log(`Alert channel created: ${created}`),
    );

    PushNotification.createChannel(
      {
        channelId: CHANNEL_ID_ACTIONS,
        channelName: 'Mira Actions',
        channelDescription: 'Autonomous action notifications',
        importance: 3, // DEFAULT
        vibrate: false,
        playSound: false,
      },
      (created: boolean) =>
        console.log(`Action channel created: ${created}`),
    );

    this.configured = true;
  }

  /**
   * Show a local notification (used for in-app alerts).
   */
  showLocal(title: string, message: string, isAlert = false): void {
    PushNotification.localNotification({
      channelId: isAlert ? CHANNEL_ID_ALERTS : CHANNEL_ID_ACTIONS,
      title,
      message,
      smallIcon: 'ic_notification',
      largeIcon: 'ic_launcher',
      color: '#7C3AED', // Mira purple
      vibrate: isAlert,
      playSound: isAlert,
    });
  }

  /**
   * Cancel all displayed notifications.
   */
  clearAll(): void {
    PushNotification.cancelAllLocalNotifications();
  }

  // ── Internal ──

  private handleNotification(notification: ReceivedNotification): void {
    const data = notification.data as Record<string, any> | undefined;

    // Handle different notification types from Mira
    const type = data?.type ?? 'generic';

    switch (type) {
      case 'trade_alert':
        this.showLocal(
          'Trade Alert',
          data?.message ?? 'Mira executed a trade',
          true,
        );
        break;
      case 'briefing':
        this.showLocal('Daily Briefing', data?.message ?? 'Briefing ready');
        break;
      case 'action_log':
        this.showLocal(
          'Mira Action',
          data?.message ?? 'Autonomous action completed',
        );
        break;
      default:
        // Generic handling — notification already displayed by system
        break;
    }
  }
}

const NotificationService = new NotificationServiceManager();
export default NotificationService;
