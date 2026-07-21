import type { Metadata } from "next";
import "@/styles/globals.css";
import { Providers } from "@/app/providers";

export const metadata: Metadata = {
  title: "안심루프 — HUG X 아이엔",
  description:
    "계약 전 위험진단부터 계약 중 모니터링, 사고 후 HUG 채권회수까지 하나의 루프로 잇는 전세 생애주기 안심 플랫폼",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className="h-full antialiased">
      <head>
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
      </head>
      <body className="min-h-full flex flex-col">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
