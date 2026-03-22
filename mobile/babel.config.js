module.exports = {
  presets: ['module:@react-native/babel-preset'],
  plugins: [
    [
      'module-resolver',
      {
        root: ['./'],
        alias: {
          '@screens': './src/screens',
          '@services': './src/services',
          '@components': './src/components',
          '@utils': './src/utils',
        },
      },
    ],
  ],
};
