import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 로컬 개발: /api/* 를 파이썬 엔진 서버(:8531)로 프록시 —
  // `python3 api/solve.py`만 띄우면 NEXT_PUBLIC_API_BASE 설정 불필요.
  // 프로덕션(Vercel): api/solve.py가 same-origin /api/solve로 직접 서빙되므로 프록시 없음.
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8531/api/:path*",
      },
    ];
  },
};

export default nextConfig;
