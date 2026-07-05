
import './globals.css'

export const metadata = {
  title: 'Medi-Chatbot',
  description: 'A RAG-based medical chatbot',
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
