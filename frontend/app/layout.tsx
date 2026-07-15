
import './globals.css'
import { Inter } from "next/font/google";
import { cn } from "@/lib/utils";

const inter = Inter({subsets:['latin'],variable:'--font-sans'});

export const metadata = {
  title: 'Student Handbook',
  description: 'A RAG-based student handbook',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="vi" className={cn("font-sans", inter.variable)}>
      <body>{children}</body>
    </html>
  )
}
