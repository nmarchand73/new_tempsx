// Contrôle statique du front : npx eslint -c ui/eslint.config.mjs ui/js   (nécessite eslint et globals)
import globals from 'globals';

export default [
  {
    files: ['js/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.browser, marked: 'readonly', DOMPurify: 'readonly' },
    },
    rules: {
      'no-undef': 'error',
      'no-import-assign': 'error',
      'no-const-assign': 'error',
      'no-unused-vars': ['warn', { args: 'none', caughtErrors: 'none' }],
    },
  },
];
