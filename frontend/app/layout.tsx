import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AppHeader } from "@/components/AppHeader";
import { PulseProvider } from "@/components/PulseProvider";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Paytm Pulse — AI workforce",
  description:
    "Mission-based AI teammates for customer resolution and merchant acquisition. Prototype with a simulated Paytm integration boundary.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${inter.variable} h-full`}>
      <body className="flex min-h-full flex-col bg-canvas text-ink antialiased">
        <PulseProvider>
          <AppHeader />
          <main className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-6">
            {children}
          </main>
          <footer className="border-t border-hairline bg-surface">
            <div className="mx-auto max-w-[1400px] px-6 py-3 text-[11px] leading-relaxed text-muted">
              Prototype · Simulated Paytm integration boundary. No production
              Paytm access. All customer, merchant and transaction records are
              fictional demo data. The ₹1,000 approval threshold is a
              configurable demo policy, not Paytm&rsquo;s production policy.
            </div>
          </footer>
        </PulseProvider>
      </body>
    </html>
  );
}
