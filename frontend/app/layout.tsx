import type { Metadata } from "next";
import { Source_Serif_4 } from "next/font/google";
import "@/styles/globals.css";
import { Providers } from "@/app/providers";

const sourceSerif = Source_Serif_4({
  variable: "--font-source-serif",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "HUG 안심전세 체인",
  description: "계약 전 위험진단부터 계약 중 모니터링, 사고 후 HUG 채권관리까지 연결하는 주거안전 인프라",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className={`${sourceSerif.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
