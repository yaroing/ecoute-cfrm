import js from "@eslint/js";
import globals from "globals";
export default [
  { ignores: ["dist/**"] },
  js.configs.recommended,
  {
    files: ["src/**/*.{js,jsx}"],
    languageOptions: {
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: { jsx: true },
      },
    },
    rules: { "no-unused-vars": "off", "no-empty": "error" },
  },
];
