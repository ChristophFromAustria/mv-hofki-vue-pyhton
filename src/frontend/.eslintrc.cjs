module.exports = {
  root: true,
  env: {
    browser: true,
    es2022: true,
  },
  extends: ["eslint:recommended", "plugin:vue/vue3-recommended"],
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
  },
  rules: {
    "vue/multi-word-component-names": "off",
    "vue/singleline-html-element-content-newline": "off",
    "vue/max-attributes-per-line": "off",
    "vue/html-self-closing": "off",
    "vue/html-closing-bracket-newline": "off",
    "vue/html-indent": "off",
  },
  overrides: [
    {
      files: ["vite.config.js", "vitest.config.js"],
      env: {
        node: true,
      },
    },
  ],
};
