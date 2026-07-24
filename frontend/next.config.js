/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Required for the multi-stage Docker build to produce a self-contained
  // server bundle in .next/standalone that can be run with `node server.js`.
  output: 'standalone',
}

module.exports = nextConfig
