import "./globals.css";
import type { Metadata } from "next";
import { Chakra_Petch, Azeret_Mono } from "next/font/google";
import { ThemeProvider } from "@/components/ThemeProvider";
import { NavBar } from "@/components/NavBar";

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
          <div className="relative z-10">
            <NavBar />
            {children}
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
