
import './globals.css'

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
    <html lang="vi">
      <body>{children}</body>
    </html>
  )
}
