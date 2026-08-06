import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  eslint: {
    // O build nunca lintou de fato (o eslint.config.mjs antigo nem carregava e o
    // Next pulava a etapa em silêncio). Com o config consertado, o lint passou a
    // rodar no build e a REPROVAR por 22 problemas pré-existentes no código.
    // Mantemos o comportamento anterior do build; o lint roda como passo próprio
    // (`npm run lint`) e a dívida fica visível lá, sem bloquear a imagem.
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
