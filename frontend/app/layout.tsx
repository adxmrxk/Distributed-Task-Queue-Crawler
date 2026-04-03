import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import { ToastProvider } from "@/components/toast";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Web Crawler",
  description: "Distributed web crawler for broken link detection",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased bg-zinc-950 text-zinc-100 min-h-screen`}>
        <ToastProvider>
        <header className="border-b border-zinc-800 px-6 py-4">
          <div className="max-w-5xl mx-auto flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2 font-semibold text-white hover:text-zinc-300 transition-colors">
              <span className="text-emerald-400">⬡</span>
              WebCrawler
            </Link>
            <div className="flex items-center gap-5">
              <Link href="/search" className="text-sm text-zinc-400 hover:text-white transition-colors">
                Search
              </Link>
              <Link href="/jobs" className="text-sm text-zinc-400 hover:text-white transition-colors">
                All Jobs
              </Link>
            </div>
          </div>
        </header>
        <main className="max-w-5xl mx-auto px-6 py-10">
          {children}
        </main>
        </ToastProvider>
      </body>
    </html>
  );
}
