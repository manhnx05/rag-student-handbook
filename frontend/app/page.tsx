'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/providers/AuthProvider';
import { Button } from '@/components/ui/button';
import { Menu, MessageSquare } from 'lucide-react';

import { useChatStream } from '@/features/chat/hooks/useChatStream';
import { ChatSidebar } from '@/features/chat/components/ChatSidebar';
import { MessageBubble } from '@/features/chat/components/MessageBubble';
import { ChatInput } from '@/features/chat/components/ChatInput';

export default function ChatPage() {
  const { user, token, logout, loading } = useAuth();
  const router = useRouter();

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const {
    sessions,
    activeSessionId,
    setActiveSessionId,
    messages,
    input,
    setInput,
    isTyping,
    handleNewChat,
    handleSendMessage,
  } = useChatStream(token);

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login');
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  if (loading) {
    return <div className="flex h-screen items-center justify-center">Loading...</div>;
  }

  if (!user) {
    return null;
  }

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900 overflow-hidden">
      <ChatSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        sidebarOpen={sidebarOpen}
        user={user}
        onSelectSession={setActiveSessionId}
        onNewChat={handleNewChat}
        onLogout={logout}
      />

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
                <MessageBubble key={msg.id} msg={msg} />
              ))}
            </div>
          )}
        </div>

        <ChatInput
          input={input}
          isTyping={isTyping}
          onInputChange={setInput}
          onSubmit={handleSendMessage}
        />
      </div>
    </div>
  );
}
