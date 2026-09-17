import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1", "localhost", "ec2-3-27-40-249.ap-southeast-2.compute.amazonaws.com"],
  images: {
    remotePatterns: [{ protocol: "https", hostname: "image.tving.com", pathname: "/ntgs/sports/kbo/**" }],
  },
};

export default nextConfig;
