import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "EEA-2026 HUD", description: "Sistema Operativo Cognitivo Local" };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="es"><body>{children}</body></html>;
}
