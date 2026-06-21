module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      [
        'feat',
        'fix',
        'refactor',
        'docs',
        'test',
        'chore',
        'style',
        'perf',
        'ci',
        'revert',
      ],
    ],
    'type-empty': [1, 'never'], // warning instead of error — allows "v0.3" style tags
    'subject-case': [0], // disabled — allows any case
    'subject-empty': [1, 'never'],
    'scope-case': [2, 'always', 'lower-case'],
  },
};
