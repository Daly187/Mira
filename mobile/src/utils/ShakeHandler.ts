/**
 * ShakeHandler — Detects device shake gesture to pause/resume all capture.
 *
 * Uses react-native-shake to listen for shake events and toggles
 * the audio foreground service + location tracking.
 */
import RNShake from 'react-native-shake';
import AsyncStorage from '@react-native-async-storage/async-storage';
import AudioService from '../services/AudioService';
import LocationService from '../services/LocationService';
import NotificationService from '../services/NotificationService';

class ShakeHandler {
  private listening = false;
  private paused = false;

  /**
   * Start listening for shake events.
   */
  async start(): Promise<void> {
    const enabled = await AsyncStorage.getItem('@shake_enabled');
    if (enabled === 'false') return;

    if (this.listening) return;

    RNShake.addListener(() => {
      this.toggle();
    });

    this.listening = true;
  }

  /**
   * Stop listening for shake events.
   */
  stop(): void {
    RNShake.removeAllListeners();
    this.listening = false;
  }

  /**
   * Toggle pause state for all capture services.
   */
  private async toggle(): Promise<void> {
    if (this.paused) {
      // Resume
      await AudioService.start();
      await LocationService.startTracking();
      NotificationService.showLocal('Mira Resumed', 'All capture services active');
      this.paused = false;
    } else {
      // Pause
      await AudioService.stop();
      LocationService.stopTracking();
      NotificationService.showLocal('Mira Paused', 'Shake again to resume', true);
      this.paused = true;
    }
  }

  isPaused(): boolean {
    return this.paused;
  }
}

const shakeHandler = new ShakeHandler();
export default shakeHandler;
