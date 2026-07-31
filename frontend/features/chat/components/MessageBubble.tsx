import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import ReactMarkdown from 'react-markdown'

interface MessageBubbleProps {
  role: 'user' | 'assistant'
  content: string
}

export function MessageBubble({ role, content }: MessageBubbleProps) {
  const isUser = role === 'user'

  return (
    <div className={`flex w-full gap-4 p-6 ${isUser ? '' : 'bg-gray-50 dark:bg-gray-800/50 rounded-lg'}`}>
      <Avatar className="w-8 h-8 border shadow-sm">
        {isUser ? (
          <AvatarFallback className="bg-blue-600 text-white font-medium text-xs">U</AvatarFallback>
        ) : (
          <AvatarFallback className="bg-green-600 text-white font-medium text-xs">AI</AvatarFallback>
        )}
      </Avatar>
      <div className="flex-1 space-y-2 overflow-hidden">
        <div className="font-semibold text-sm text-gray-800 dark:text-gray-200">
          {isUser ? 'You' : 'Handbook Assistant'}
        </div>
        <div className="prose prose-sm dark:prose-invert max-w-none text-gray-700 dark:text-gray-300 leading-relaxed">
          <ReactMarkdown>{content}</ReactMarkdown>
        </div>
      </div>
    </div>
  )
}
