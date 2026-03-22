/**
 * Basic smoke test for Mira Mobile App
 */
import 'react-native';
import React from 'react';
import App from '../App';
import renderer from 'react-test-renderer';

it('renders without crashing', () => {
  renderer.create(<App />);
});
