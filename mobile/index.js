/**
 * Mira Mobile — Android app entry point
 */
import {AppRegistry} from 'react-native';
import App from './App';
import {name as appName} from './app.json';
import NotificationService from './src/services/NotificationService';

// Initialize push notification handling
NotificationService.configure();

AppRegistry.registerComponent(appName, () => App);
