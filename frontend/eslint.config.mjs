import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

// eslint-config-next 15.x publica configs no formato LEGADO (eslintrc); o import
// direto de "eslint-config-next/core-web-vitals" só existe a partir da v16.
// FlatCompat é o padrão oficial do Next 15 para usar esses presets no flat config.
const compat = new FlatCompat({
  baseDirectory: dirname(fileURLToPath(import.meta.url)),
});

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    ignores: [
      // Default ignores of eslint-config-next:
      ".next/**",
      "out/**",
      "build/**",
      "next-env.d.ts",
      // Artefatos de execução dos testes E2E:
      "test-results/**",
      "playwright-report/**",
    ],
  },
];

export default eslintConfig;
