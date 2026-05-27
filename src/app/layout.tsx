import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "K-ETS 가격전망 · PLANiT Institute",
  description: "한국 배출권거래제 가격전망 및 정책 시나리오 분석",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className="h-full antialiased">
      <head>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body className="min-h-full" style={{ fontFamily: "'Pretendard', 'Inter', system-ui, sans-serif" }}>
        {children}
      </body>
    </html>
  );
}
