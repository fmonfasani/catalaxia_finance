import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Transpila packages del monorepo
  transpilePackages: ["@catalaxia/ui", "@catalaxia/types"],

  // Headers de seguridad
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },

  // Logging de rutas en desarrollo
  logging: {
    fetches: {
      fullUrl: process.env.NODE_ENV === "development",
    },
  },

  // Imágenes externas permitidas
  images: {
    remotePatterns: [
      { hostname: "assets.catalaxia.com" },
      { hostname: "logo.clearbit.com" },      // logos de empresas
    ],
  },

  // Output standalone para Docker
  output: process.env.DOCKER_BUILD === "1" ? "standalone" : undefined,
};

export default nextConfig;
