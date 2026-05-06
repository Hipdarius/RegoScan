/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  typedRoutes: false,
  // The Python serverless function lives at /api/predict and is wired
  // up by vercel.json. In local dev `next dev` does not run the Python
  // function — point NEXT_PUBLIC_API_BASE at a running uvicorn instead
  // (see web/README.md).
};

module.exports = nextConfig;
