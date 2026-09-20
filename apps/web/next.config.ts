import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Local tooling / browser sometimes uses 127.0.0.1 while `next dev` binds localhost.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
