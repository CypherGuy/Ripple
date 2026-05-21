import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ripple - Live Scan",
  description:
    "Real-time codebase pattern detection grounded in production incident history",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
