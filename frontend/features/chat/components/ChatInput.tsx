import React from 'react';
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Send } from "lucide-react";

interface ChatInputProps {
  input: string;
  isTyping: boolean;
  onInputChange: (val: string) => void;
  onSubmit: (e: React.FormEvent) => void;
}

export function ChatInput({ input, isTyping, onInputChange, onSubmit }: ChatInputProps) {
  return (
    <div className="p-4 bg-white dark:bg-gray-900 border-t">
      <form
        onSubmit={onSubmit}
        className="max-w-3xl mx-auto relative flex items-center"
      >
        <Input
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
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
  );
}
