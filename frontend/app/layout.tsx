
import './globals.css'
import { Geist } from "next/font/google";
import { cn } from "@/lib/utils";

const geist = Geist({subsets:['latin'],variable:'--font-sans'});

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
    <html lang="vi" className={cn("font-sans", geist.variable)}>
      <body>{children}</body>
    </html>
  )
}
