import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: string;
  content: string;
}

export function useChatStream(token: string | null) {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);

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
    if (activeSessionId) {
      setMessages(initialMessages);
    } else {
      setMessages([]);
    }
  }, [initialMessages, activeSessionId]);

  const handleNewChat = () => {
    setActiveSessionId(null);
    setMessages([]);
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isTyping || !token) return;

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

  return {
    sessions,
    activeSessionId,
    setActiveSessionId,
    messages,
    input,
    setInput,
    isTyping,
    handleNewChat,
    handleSendMessage,
  };
}
