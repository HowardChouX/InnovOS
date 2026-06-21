module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      [
        'feat',     // 新功能
        'fix',      // 修复
        'refactor', // 重构
        'docs',     // 文档
        'test',     // 测试
        'chore',    // 工具/构建
        'style',    // 格式
        'perf',     // 性能
        'ci',       // CI/CD
        'revert',   // 回滚
      ],
    ],
    'scope-case': [2, 'always', 'lower-case'],
    'subject-case': [2, 'never', ['sentence-case', 'start-case', 'pascal-case', 'upper-case']],
    'subject-empty': [2, 'never'],
  },
};
