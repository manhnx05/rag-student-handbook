'use client'

import { useState, useRef, useEffect } from 'react'
import { ChatSidebar } from '@/components/chat/ChatSidebar'
import { MessageBubble } from '@/components/chat/MessageBubble'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Send, Loader2 } from 'lucide-react'
import axios from 'axios'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Xin chào! Tôi là trợ lý AI Hỗ trợ Sinh viên. Bạn cần hỏi gì về quy chế, học vụ hay sổ tay sinh viên không?'
    }
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isLoading])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setIsLoading(true)

    try {
      // In the future this will be replaced with SSE Streaming
      const response = await axios.post('http://localhost:8000/api/chat', {
        question: userMsg
      })
      setMessages(prev => [...prev, { role: 'assistant', content: response.data.answer || response.data }])
    } catch (error) {
      console.error(error)
      setMessages(prev => [...prev, { role: 'assistant', content: '**Lỗi:** Có lỗi xảy ra khi kết nối tới máy chủ, vui lòng thử lại sau.' }])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex h-screen bg-white dark:bg-gray-950">
      <ChatSidebar />
      
      <main className="flex-1 flex flex-col h-full relative">
        <div className="flex-1 overflow-hidden relative">
          <ScrollArea className="h-full px-4 py-6 md:px-8">
            <div className="max-w-3xl mx-auto space-y-6 pb-24">
              {messages.map((msg, index) => (
                <MessageBubble key={index} role={msg.role} content={msg.content} />
              ))}
              {isLoading && (
                <div className="flex items-center gap-2 p-6 text-gray-500">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span className="text-sm">Agent is thinking...</span>
                </div>
              )}
              <div ref={scrollRef} />
            </div>
          </ScrollArea>
        </div>

        <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-white via-white dark:from-gray-950 dark:via-gray-950 to-transparent">
          <div className="max-w-3xl mx-auto">
            <form onSubmit={handleSubmit} className="relative flex items-center shadow-lg rounded-xl border bg-white dark:bg-gray-900 overflow-hidden focus-within:ring-1 focus-within:ring-ring">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Message Handbook Assistant..."
                className="border-0 focus-visible:ring-0 rounded-none h-14 text-base shadow-none bg-transparent flex-1 px-4"
                disabled={isLoading}
              />
              <div className="pr-2">
                <Button 
                  type="submit" 
                  size="icon"
                  disabled={!input.trim() || isLoading}
                  className="rounded-lg w-10 h-10 transition-all"
                >
                  <Send className="w-5 h-5" />
                  <span className="sr-only">Send</span>
                </Button>
              </div>
            </form>
            <div className="text-center mt-2">
              <span className="text-xs text-gray-400">AI can make mistakes. Check important information.</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
