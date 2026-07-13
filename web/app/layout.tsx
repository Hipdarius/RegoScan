import "./globals.css";
import type { Metadata } from "next";
import { Chakra_Petch, Azeret_Mono } from "next/font/google";
import { ThemeProvider } from "@/components/ThemeProvider";
import { NavBar } from "@/components/NavBar";
import { ScrollProgress } from "@/components/ScrollProgress";
import { SmoothScroll } from "@/components/SmoothScroll";

const fontDisplay = Chakra_Petch({
  subsets: ["latin"],
  weight: ["500", "600"],
  variable: "--font-display",
  display: "swap",
});

const fontMono = Azeret_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "VERA Mission Console",
  description:
    "VIS/NIR + 405 nm LIF probe for in-situ lunar regolith mineral classification",
  icons: {
    icon: "/favicon.svg",
    apple: "/logo/vera-mark.svg",
  },
  openGraph: {
    title: "VERA — Visible & Emission Regolith Assessment",
    description:
      "Handheld VIS/NIR + SWIR + LIF probe for real-time lunar regolith mineralogy.",
    type: "website",
    siteName: "VERA",
    images: [
      {
        url: "/logo/vera-wordmark-dark.svg",
        width: 240,
        height: 300,
        alt: "VERA logo",
      },
    ],
  },
  twitter: {
    card: "summary",
    title: "VERA — Visible & Emission Regolith Assessment",
    description:
      "Handheld VIS/NIR + SWIR + LIF probe for real-time lunar regolith mineralogy.",
    images: ["/logo/vera-wordmark-dark.svg"],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`dark ${fontDisplay.variable} ${fontMono.variable}`}
      suppressHydrationWarning
    >
      <body className="min-h-screen antialiased">
        <ThemeProvider>
          <SmoothScroll />
          <ScrollProgress />
          <div className="relative z-10">
            <NavBar />
            {children}
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
