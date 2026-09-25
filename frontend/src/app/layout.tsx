import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import Link from "next/link";

const geist = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Synapse - Railway ETA Intelligence",
  description: "Live delay prediction for Indian Railways",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${geist.className} min-h-screen`} style={{ background: "#f5f4f0" }}>
        {/* Top bar */}
        <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-neutral-200/80">
          <div className="max-w-[1280px] mx-auto px-8 h-16 flex items-center justify-between">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-3 group">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "#0f1f3d" }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
                  <path d="M3 17h18M5 17V8a2 2 0 012-2h10a2 2 0 012 2v9" />
                  <circle cx="8" cy="19" r="2" />
                  <circle cx="16" cy="19" r="2" />
                  <path d="M5 12h14" />
                </svg>
              </div>
              <span className="text-base font-semibold tracking-tight" style={{ color: "#0f1f3d" }}>
                Synapse
              </span>
            </Link>

            {/* Nav */}
            <nav className="flex items-center">
              <NavLink href="/">Track Train</NavLink>
              <NavLink href="/network">Network</NavLink>
            </nav>
          </div>
        </header>

        {/* Page content */}
        <main>
          <div className="max-w-[1280px] mx-auto px-8 py-10">
            {children}
          </div>
        </main>
      </body>
    </html>
  );
}

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="px-4 py-2 text-base font-medium rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
    >
      {children}
    </Link>
  );
}
