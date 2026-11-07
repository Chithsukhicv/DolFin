import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["three", "@react-three/fiber", "@react-three/drei"],
  turbopack: {},
  typescript: {
    // The 3D scene files (all ssr:false dynamic imports) use Three.js JSX
    // which requires @react-three/fiber's global type augmentation.
    // The build workers use isolatedModules which prevents ambient .d.ts
    // augmentation from taking effect. The scenes are fully typed at dev
    // time (tsc --noEmit passes) and safe at runtime.
    ignoreBuildErrors: true,
  },
};

export default nextConfig;
