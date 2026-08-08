'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/providers/AuthProvider';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Send, Menu, Plus, LogOut, MessageSquare } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { motion } from 'framer-motion';
import React from 'react';
import { cn } from '@/lib/utils';

interface ChatSession {
  id: string;
  title: string;
  created_at: string;
}

interface ChatMessage {
  id: string;
  role: string;
  content: string;
}

const ChatMessageItem = React.memo(({ msg }: { msg: ChatMessage }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={cn(
        "flex gap-4 w-full",
        msg.role === 'user' ? "justify-end" : "justify-start"
      )}
    >
      {msg.role === 'ai' && (
        <Avatar className="w-8 h-8 mt-1 shrink-0 bg-blue-600">
          <AvatarFallback className="text-white">AI</AvatarFallback>
        </Avatar>
      )}
      <div
        className={cn(
          "px-4 py-3 rounded-2xl max-w-[85%]",
          msg.role === 'user'
            ? "bg-blue-600 text-white rounded-tr-sm"
            : "bg-white dark:bg-gray-800 shadow-sm border rounded-tl-sm text-gray-800 dark:text-gray-200"
        )}
      >
        {msg.role === 'user' ? (
          <p className="whitespace-pre-wrap">{msg.content}</p>
        ) : (
          <div className="prose prose-sm max-w-none dark:prose-invert">
            {msg.content ? (
              <ReactMarkdown
                components={{
                  code({node, inline, className, children, ...props}: any) {
                    const match = /language-(\w+)/.exec(className || '')
                    return !inline && match ? (
                      <SyntaxHighlighter
                        {...props}
                        style={vscDarkPlus as any}
                        language={match[1]}
                        PreTag="div"
                      >
                        {String(children).replace(/\n$/, '')}
                      </SyntaxHighlighter>
                    ) : (
                      <code {...props} className={cn("bg-gray-100 dark:bg-gray-700 rounded px-1 py-0.5", className)}>
                        {children}
                      </code>
                    )
                  }
                }}
              >
                {msg.content}
              </ReactMarkdown>
            ) : (
              <span className="flex items-center gap-1 h-6">
                <motion.span 
                  animate={{ y: [0, -4, 0] }} 
                  transition={{ repeat: Infinity, duration: 0.6, delay: 0 }} 
                  className="w-2 h-2 bg-gray-400 rounded-full"
                />
                <motion.span 
                  animate={{ y: [0, -4, 0] }} 
                  transition={{ repeat: Infinity, duration: 0.6, delay: 0.2 }} 
                  className="w-2 h-2 bg-gray-400 rounded-full"
                />
                <motion.span 
                  animate={{ y: [0, -4, 0] }} 
                  transition={{ repeat: Infinity, duration: 0.6, delay: 0.4 }} 
                  className="w-2 h-2 bg-gray-400 rounded-full"
                />
              </span>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
});

export default function ChatPage() {
  const { user, token, logout, loading } = useAuth();
  const router = useRouter();

  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: sessions = [], refetch: refetchSessions } = useQuery<ChatSession[]>({
    queryKey: ['sessions'],
    queryFn: async () => {
      const response = await api.get('/sessions');
      return response.data;
    },
    enabled: !!token,
  });

  const { data: initialMessages = [] } = useQuery<ChatMessage[]>({
    queryKey: ['messages', activeSessionId],
    queryFn: async () => {
      const response = await api.get(`/sessions/${activeSessionId}/messages`);
      return response.data;
    },
    enabled: !!activeSessionId,
  });

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login');
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (activeSessionId) {
      setMessages(initialMessages);
    } else {
      setMessages([]);
    }
  }, [initialMessages, activeSessionId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping]);


  const handleNewChat = () => {
    setActiveSessionId(null);
    setMessages([]);
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isTyping) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    const aiMessageId = (Date.now() + 1).toString();
    setMessages((prev) => [...prev, { id: aiMessageId, role: 'ai', content: '' }]);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || '/api';
      const response = await fetch(`${apiUrl}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ question: userMessage.content, session_id: activeSessionId })
      });

      if (!response.ok) throw new Error('Failed to fetch response');

      const returnedSessionId = response.headers.get('X-Session-ID');
      if (returnedSessionId && returnedSessionId !== activeSessionId) {
        setActiveSessionId(returnedSessionId);
        setTimeout(refetchSessions, 1000);
      }

      const reader = response.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      let aiContent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        aiContent += chunk;

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === aiMessageId ? { ...msg, content: aiContent } : msg
          )
        );
      }
    } catch (err) {
      console.error(err);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === aiMessageId ? { ...msg, content: 'Error occurred while fetching response.' } : msg
        )
      );
    } finally {
      setIsTyping(false);
    }
  };

  if (loading) {
    return <div className="flex h-screen items-center justify-center">Loading...</div>;
  }

  if (!user) {
    return null;
  }

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900 overflow-hidden">
      {/* Sidebar */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 bg-gray-900 text-white transition-transform duration-300 ease-in-out md:relative",
          sidebarOpen ? "translate-x-0" : "-translate-x-full hidden md:flex"
        )}
      >
        <div className="flex flex-col h-full">
          <div className="p-4 flex items-center justify-between">
            <Button
              variant="ghost"
              className="w-full justify-start gap-2 hover:bg-gray-800 text-white"
              onClick={handleNewChat}
            >
              <Plus className="w-5 h-5" />
              New Chat
            </Button>
          </div>
          <ScrollArea className="flex-1 px-2">
            <div className="space-y-2">
              {sessions.map((session) => (
                <button
                  key={session.id}
                  onClick={() => setActiveSessionId(session.id)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-left transition-colors",
                    activeSessionId === session.id
                      ? "bg-gray-800 text-white"
                      : "text-gray-400 hover:bg-gray-800 hover:text-white"
                  )}
                >
                  <MessageSquare className="w-4 h-4 shrink-0" />
                  <span className="truncate">{session.title}</span>
                </button>
              ))}
            </div>
          </ScrollArea>
          <div className="p-4 border-t border-gray-800">
            <div className="flex items-center gap-3 mb-4">
              <Avatar className="w-8 h-8">
                <AvatarFallback>{user.email[0].toUpperCase()}</AvatarFallback>
              </Avatar>
              <div className="text-sm truncate max-w-[150px]">{user.email}</div>
            </div>
            <Button
              variant="ghost"
              className="w-full justify-start gap-2 hover:bg-gray-800 text-red-400 hover:text-red-300"
              onClick={logout}
            >
              <LogOut className="w-5 h-5" />
              Log out
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col h-full relative w-full">
        <header className="flex h-14 items-center gap-4 border-b bg-white dark:bg-gray-900 px-6">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            <Menu className="w-5 h-5" />
          </Button>
          <h1 className="text-lg font-semibold">Student Handbook Assistant</h1>
        </header>

        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6"
        >
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
              <div className="w-16 h-16 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mb-4">
                <MessageSquare className="w-8 h-8" />
              </div>
              <h2 className="text-2xl font-semibold">How can I help you today?</h2>
              <p className="text-gray-500 max-w-md">
                Ask me anything about the Student Handbook, courses, graduation requirements, or university policies.
              </p>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-6">
              {messages.map((msg) => (
                <ChatMessageItem key={msg.id} msg={msg} />
              ))}
            </div>
          )}
        </div>

        <div className="p-4 bg-white dark:bg-gray-900 border-t">
          <form
            onSubmit={handleSendMessage}
            className="max-w-3xl mx-auto relative flex items-center"
          >
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Message Student Handbook Assistant..."
              className="pr-12 py-6 rounded-full border-gray-300 focus-visible:ring-blue-500 shadow-sm"
              disabled={isTyping}
            />
            <Button
              type="submit"
              size="icon"
              className="absolute right-2 rounded-full w-10 h-10 bg-blue-600 hover:bg-blue-700 text-white"
              disabled={!input.trim() || isTyping}
            >
              <Send className="w-4 h-4" />
            </Button>
          </form>
          <div className="text-center mt-2 text-xs text-gray-400">
            AI can make mistakes. Consider verifying important information.
          </div>
        </div>
      </div>
    </div>
  );
}
