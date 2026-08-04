/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true,
    remotePatterns: [
      {
        protocol: "https",
        hostname: "cdn.grofers.com",
        pathname: "/**",
      },
    ],
  },
};

module.exports = nextConfig;
