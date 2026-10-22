import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Intellex – Multi-Agent Autonomous Research Platform",
  description: "Autonomous Research Operating System with multi-agent orchestration and verification.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <div className="app-container" suppressHydrationWarning>
          {children}
        </div>
      </body>
    </html>
  );
}
